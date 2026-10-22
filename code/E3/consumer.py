"""Independent R/F/S consumers with shared DFL, coordinates and NMS.

S never invokes F and never constructs full FLOAT32 bbox tensors.
"""
import time
import cv2
import numpy as np

DFL_WEIGHTS=np.arange(16,dtype=np.float32).reshape(1,1,16)

def exact_scale(prop):
    if prop['quantiType']!=2 or prop['scaleLen']!=1 or prop['zeroPointLen'] or prop['shiftLen']:
        raise ValueError('Unsupported or unverified quantization ABI')
    return np.array(prop['scaleFp32Bits'],dtype='<u4').view('<f4')[0]

def check_abi(props,strategy):
    expected={f'{kind}{head}' for head in range(3) for kind in ['bbox','score','class']}
    if set(props)!=expected: raise ValueError('Nine named outputs required')
    for name,p in props.items():
        if p['layout']!=2 or p['validShape'][0]!=1:raise ValueError('Verified NCHW ABI required')
        shape=p['validShape'];stride=p['stride'][:len(shape)]
        itemsize=2 if p['dtype']=='INT16' else 4
        if stride[-1]!=itemsize or sum((s-1)*v for s,v in zip(shape,stride))+itemsize>p['alignedByteSize']:
            raise ValueError('Invalid byte stride / allocation boundary')
        if name.startswith('bbox'):
            if p['dtype']!=('FLOAT32' if strategy=='R' else 'INT16'):raise ValueError('Wrong model for strategy')
            if strategy!='R':exact_scale(p)
        elif p['dtype']!='FLOAT32':raise ValueError('score/class ABI changed')

def dfl(logits):
    values=logits.reshape(-1,4,16)
    numerator=np.exp(values-np.max(values,axis=-1,keepdims=True))
    probs=numerator/np.sum(numerator,axis=-1,keepdims=True)
    return np.sum(probs*DFL_WEIGHTS,axis=-1)

def consume(strategy,views,props,metadata,conf=0.3,iou=0.5):
    if strategy not in ['M6','R','F','S','CID_MAX','CID_INDEX']:raise ValueError('Independent strategy R/F/S required')
    restore_ns=select_ns=dfl_coord_ns=0
    full={};full_elements=selected_elements=0
    # This branch is reached only for F. S has no reference to full recovery.
    if strategy=='F':
        start=time.perf_counter_ns()
        for head in range(3):
            name=f'bbox{head}'
            full[name]=np.multiply(views[name].astype(np.float32),exact_scale(props[name]),dtype=np.float32)
            full_elements+=int(full[name].size)
        restore_ns+=time.perf_counter_ns()-start
    candidates=[];selected=[];ltrbs=[];boxes=[];scores=[];classes=[]
    threshold=np.log(conf/(1.0-conf))
    for head,stride in enumerate([8,16,32]):
        start=time.perf_counter_ns()
        name=f'bbox{head}'
        if strategy in ['CID_MAX','CID_INDEX']:
            cls_channels=(views[f'cls{head}'].reshape(-1,80).T if props[f'cls{head}']['layoutName']=='NHWC' else views[f'cls{head}'].reshape(80,-1))
            class_values=views[f'class{head}'].reshape(-1)
            h,w=(props[f'class{head}']['validShape'][1:3] if props[f'class{head}']['layoutName']=='NHWC' else props[f'class{head}']['validShape'][-2:])
            if strategy=='CID_MAX':score_logits=np.max(cls_channels,axis=0)
            else:score_logits=np.take_along_axis(cls_channels,class_values.astype(np.int64)[None,:],axis=0).reshape(-1)
        elif strategy=='M6':
            cls=views[f'cls{head}'][0]
            score_logits=np.max(cls,axis=2).reshape(-1)
            h,w=cls.shape[:2]
        else:
            score_logits=views[f'score{head}'].reshape(-1)
            class_values=views[f'class{head}'].reshape(-1)
            h,w=props[f'score{head}']['validShape'][-2:]
        ids=np.flatnonzero(score_logits>threshold)
        ys,xs=np.divmod(ids,w)
        candidates.append(np.column_stack([np.full(ids.size,head,dtype=np.int64),ys,xs]))
        select_ns+=time.perf_counter_ns()-start
        start=time.perf_counter_ns()
        if strategy=='S':
            # Native tensor view honors padded H/W strides. Only candidate
            # integer values are gathered, then those values are converted.
            integer=np.stack([views[name][0,c,ys,xs] for c in range(64)],axis=1)
            if integer.dtype!=np.dtype('<i2'):raise ValueError('S must read real INT16')
            logits=np.multiply(integer.astype(np.float32),exact_scale(props[name]),dtype=np.float32)
            selected_elements+=int(integer.size)
        elif strategy in ['CID_MAX','CID_INDEX'] and props[name]['layoutName']=='NHWC':
            logits=views[name].reshape(-1,64)[ids]
        elif strategy=='M6':
            logits=views[name].reshape(-1,64)[ids]
        else:
            source=views[name] if strategy in ['R','CID_MAX','CID_INDEX'] else full[name]
            logits=source.reshape(64,-1).transpose(1,0)[ids]
        restore_ns+=time.perf_counter_ns()-start
        start=time.perf_counter_ns()
        selected.append(logits)
        distances=dfl(logits);ltrbs.append(distances)
        score=(1.0/(1.0+np.exp(-score_logits[ids]))).astype(np.float32)
        center=(np.column_stack([xs,ys]).astype(np.float32)+np.float32(0.5))*stride
        scale=metadata['scale_first_frame'];left=metadata['pad_left_first_frame'];top=metadata['pad_top_first_frame']
        coord=np.stack([(center[:,0]-distances[:,0]*stride-left)/scale,
                        (center[:,1]-distances[:,1]*stride-top)/scale,
                        (center[:,0]+distances[:,2]*stride-left)/scale,
                        (center[:,1]+distances[:,3]*stride-top)/scale],axis=1)
        coord[:,[0,2]]=np.clip(coord[:,[0,2]],0,metadata['source_width'])
        coord[:,[1,3]]=np.clip(coord[:,[1,3]],0,metadata['source_height'])
        boxes.append(coord);scores.append(score);classes.append((np.argmax(cls.reshape(-1,80)[ids],axis=1) if strategy=='M6' else class_values[ids]).astype(np.int32))
        dfl_coord_ns+=time.perf_counter_ns()-start
    start=time.perf_counter_ns()
    result={'candidate_indices':np.concatenate(candidates),
            'selected_bbox_logits':np.concatenate(selected),'LTRB':np.concatenate(ltrbs),
            'pre_nms_boxes':np.concatenate(boxes),'pre_nms_scores':np.concatenate(scores),
            'pre_nms_classes':np.concatenate(classes)}
    b=result['pre_nms_boxes'];s=result['pre_nms_scores']
    if b.size:
        xywh=np.column_stack([b[:,0],b[:,1],b[:,2]-b[:,0],b[:,3]-b[:,1]]).astype(np.float32)
        keep=np.asarray(cv2.dnn.NMSBoxes(xywh.tolist(),s.tolist(),conf,iou),dtype=np.int32).reshape(-1)
    else:keep=np.empty(0,dtype=np.int32)
    result.update({'nms_keep_indices':keep,'final_boxes':b[keep],
                   'final_scores':s[keep],'final_classes':result['pre_nms_classes'][keep]})
    nms_ns=time.perf_counter_ns()-start
    return result,{'Select_ns':select_ns,'RestoreGather_ns':restore_ns,
                   'DFLCoordinates_ns':dfl_coord_ns,'NMSAssemble_ns':nms_ns,
                   'full_float_bbox_elements':full_elements,
                   'selected_integer_bbox_elements':selected_elements}

def compare_arrays(name,left,right,destination):
    left=np.ascontiguousarray(left);right=np.ascontiguousarray(right)
    if left.dtype!=right.dtype or left.shape!=right.shape:
        return {'name':name,'status':'FAIL','shape_or_dtype_mismatch':True,
                'left_shape':list(left.shape),'right_shape':list(right.shape),
                'left_dtype':str(left.dtype),'right_dtype':str(right.dtype)}
    if np.issubdtype(left.dtype,np.floating):
        mismatch=left.view(np.dtype('u'+str(left.dtype.itemsize)))!=right.view(np.dtype('u'+str(right.dtype.itemsize)))
        finite=np.isfinite(left)&np.isfinite(right)
        nonfinite=int(np.count_nonzero(~np.isfinite(left)))+int(np.count_nonzero(~np.isfinite(right)))
        error=float(np.max(np.abs(left[finite].astype(np.float64)-right[finite].astype(np.float64)))) if finite.any() else 0.0
    else:
        mismatch=left!=right;nonfinite=0
        error=float(np.max(np.abs(left.astype(np.int64)-right.astype(np.int64)))) if left.size else 0.0
    positions=np.argwhere(mismatch)
    indices=tuple(positions.T) if positions.size else tuple(np.array([],dtype=np.int64) for _ in left.shape)
    filename=name.replace('/','_')+'_differences.npz'
    np.savez_compressed(destination/filename,positions=positions,left=left[indices],right=right[indices])
    return {'name':name,'status':'PASS' if not positions.size and nonfinite==0 else 'FAIL',
            'shape':list(left.shape),'dtype':str(left.dtype),'elements':int(left.size),
            'bitwise_mismatch_count':int(np.count_nonzero(mismatch)),
            'max_absolute_error':error,'nonfinite_count':nonfinite,'difference_positions':filename}
