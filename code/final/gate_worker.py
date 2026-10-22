"""Frozen functional/COCO worker; shared native consumers are not modified."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import argparse,hashlib,json,signal,sys,time,traceback
from pathlib import Path
import cv2,numpy as np
from bridge import SDK
from consumer import consume,exact_scale
from cpu_control_v6 import T,digest,save_new
from p1_process import signature
from pass_accounting import snapshot
import rdk_x5_yolo11_9head_eval as legacy
import overnight_support as support


def barrier(phase):
 print('PILOT_EVENT '+json.dumps({'phase':phase,'pid':os.getpid(),'monotonic_ns':time.perf_counter_ns()}),flush=True)
 assert sys.stdin.readline().strip()=='ACK'


def stride_probe(views,props,out):
 checks=[]
 for head in [1,2]:
  name=f'bbox{head}';p=props[name];view=views[name];h,w=p['validShape'][-2:]
  assert view.dtype==np.dtype('<i2') and p['alignedShape'][-1]>w
  flat=np.ndarray((p['alignedByteSize']//2,),dtype='<i2',buffer=view.base)
  ys,xs=np.divmod(np.arange(h*w,dtype=np.intp),w)
  dc,dy,dx=[v//2 for v in p['stride'][1:4]]
  indices=ys[:,None]*dy+xs[:,None]*dx+np.arange(64,dtype=np.intp)[None,:]*dc
  gathered=np.take(flat,indices);valid=np.ascontiguousarray(view[0].reshape(64,-1).T)
  assert np.array_equal(gathered,valid)
  (out/(name+'_native_allocation.bin')).open('xb').write(bytes(view.base))
  checks.append({'head':head,'valid_elements':int(valid.size),'bitwise_mismatches':0,
    'byte_stride':p['stride'],'alignedShape':p['alignedShape'],'validShape':p['validShape']})
 save_new(out/'padded_stride_probe.json',{'status':'PASS','heads':checks,'extra_forwards':0})


class Output:
 def __init__(self,name,array):self.name=name;self.buffer=array


def quality_result(mode,views,props,image,item):
 nv,scale,left,top=legacy.preprocess(image,640)
 return nv,{'scale_first_frame':scale,'pad_left_first_frame':left,'pad_top_first_frame':top,
  'source_width':item['width'],'source_height':item['height']}


def main(index):
 cv2.setNumThreads(1)
 plan=json.loads((T/'inputs/design_frozen.json').read_text());entry=plan['reference_order'][index];mode=entry['strategy'];kind=plan['kind']
 out=T/'capture'/('correctness_'+mode);out.mkdir()
 save_new(out/'STARTED.json',{'pid':os.getpid(),'time_ns':time.time_ns(),'strategy':mode})
 state={'status':'RUNNING','strategy':mode,'kind':kind,'frames':0,'model_load_attempts':0,'model_loads':0,'errors':[]}
 records=[];warm=[];arrays=[];sdk=None;account={'setup_begin':snapshot()};error=None
 try:
  assert np.__version__==plan['numpy'] and cv2.__version__==plan['opencv']
  for item in plan['frozen_sources']:assert digest(item['path'])==item['sha256'],item['path']
  model=plan['models'][mode];assert digest(model['path'])==model['sha256'];state['model_load_attempts']=1
  sdk=SDK(T/'code/libbaselinebridge.so',model['path'],mode);state['model_loads']=1
  assert sdk.lib.p1_sdk_version().decode()==plan['sdk']
  assert sdk.props==json.loads((T/'inputs'/('expected_ABI_'+mode+'.json')).read_text())
  save_new(out/'actual_abi.json',sdk.props);account['setup_end']=snapshot();barrier('AFTER_SETUP');barrier('FORMAL_BEGIN');account['formal_begin']=snapshot()
  if kind=='functional':
   assert digest(plan['input']['path'])==plan['input']['sha256'];meta=json.loads((T/'inputs/coordinate_metadata.json').read_text())
   with Path(plan['input']['path']).open('rb') as video:
    for frame in range(plan['frames_per_pass']):
     raw=video.read(614400);assert len(raw)==614400;sdk.prepare(raw);sdk.forward();views=sdk.outputs()
     final,trace=consume(mode,views,sdk.props,meta,.3,.5)
     if frame==0:stride_probe(views,sdk.props,out)
     k=len(final['candidate_indices']);item={'frame':frame,'signature':signature(final),'candidates':k,'detections':len(final['final_boxes'])}
     warm.append(item);arrays.append(tuple(final[x] for x in ['final_boxes','final_scores','final_classes']))
     records.append({'frame':frame,'K':k,'detections':item['detections'],'head_candidates':[int(np.count_nonzero(final['candidate_indices'][:,0]==h)) for h in range(3)]})
     state['frames']+=1
   save_new(out/'warmup.json',{'status':'PASS','frames':warm})
   np.savez(out/'final_detections.npz',**{f'r{i:04}_{key}':a for i,row in enumerate(arrays) for key,a in zip(['boxes','scores','classes'],row)})
   save_new(out/'frame_counts.json',records)
  else:
   entries=json.loads((T/'inputs/manifest_5000.json').read_text());assert len(entries)==5000
   assert digest(T/'inputs/manifest_5000.json')==plan['manifest_sha256']
   total_passes=plan['quality_warmup_passes']+plan['quality_formal_passes'];baseline=None
   for pass_id in range(total_passes):
    predictions=[];per_image=[];is_warmup=pass_id<plan['quality_warmup_passes'];label='warmup' if is_warmup else 'formal_'+str(pass_id-plan['quality_warmup_passes']+1)
    with (out/(label+'_image_status.jsonl')).open('x') as journal:
     for i,item in enumerate(entries,1):
      image=support.read_image(item);nv,meta=quality_result(mode,None,None,image,item);raw=nv.tobytes(order='C')
      sdk.prepare(raw);sdk.forward();views=sdk.outputs()
      final,trace=consume(mode,views,sdk.props,meta,.001,.5)
      boxes,scores,classes=[final[k] for k in ['pre_nms_boxes','pre_nms_scores','pre_nms_classes']]
      keep=legacy.nms(boxes,scores,classes,.5,.001);boxes,scores,classes=support.final_limit(boxes[keep],scores[keep],classes[keep],100)
      prediction=legacy.to_coco_records(item['image_id'],boxes,scores,classes,'coco2017',0)
      if mode=='R':
       wrapped=[Output(f'{k}{h}',views[f'{k}{h}']) for h in range(3) for k in ['bbox','score','class']]
       b,s,c,_=legacy.run_postprocess(wrapped,conf_threshold=.001,nms_iou_threshold=.5,score_mode='logits',scale=meta['scale_first_frame'],pad_left=meta['pad_left_first_frame'],pad_top=meta['pad_top_first_frame'],orig_w=item['width'],orig_h=item['height'])
       b,s,c=support.final_limit(b,s,c,100)
       assert prediction==legacy.to_coco_records(item['image_id'],b,s,c,'coco2017',0),'R decoder differs from Table3 decoder'
      predictions.extend(prediction);per_image.append({'image_id':item['image_id'],'prediction_sha256':hashlib.sha256(json.dumps(prediction,separators=(',',':'),allow_nan=False).encode()).hexdigest()})
      journal.write(json.dumps({'index':i,'image_id':item['image_id'],'status':'PASS','nv12_sha256':hashlib.sha256(raw).hexdigest(),'jpeg_sha256':item['sha256'],'K':len(final['candidate_indices']),'detections':len(prediction)},allow_nan=False)+'\n');journal.flush()
      state['frames']+=1
      if i%100==0:print('QUALITY_PROGRESS '+json.dumps({'strategy':mode,'pass':label,'completed':i,'monotonic_ns':time.perf_counter_ns()}),flush=True)
    save_new(out/(label+'_predictions.json'),predictions);save_new(out/(label+'_by_image.json'),per_image)
    if baseline is None:baseline=per_image
    else:assert baseline==per_image,'COCO repeated passes differ'
    if not is_warmup and label=='formal_1':save_new(out/'predictions.json',predictions)
   state['prediction_count']=len(predictions);state['images_per_pass']=5000
  account['formal_end']=snapshot();barrier('FORMAL_END')
  for item in plan['frozen_sources']:assert digest(item['path'])==item['sha256']
  state['status']='PASS'
 except BaseException as exc:
  error=exc;state['status']='FAILED_STOP';state['errors'].append({'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
 finally:
  if sdk:state.update(sdk.counts());sdk.close()
  account['process_end']=snapshot();save_new(out/'accounting.json',account);save_new(out/'state.json',state)
  if error and arrays:np.savez(out/'partial_final_detections.npz',**{f'r{i:04}_{key}':a for i,row in enumerate(arrays) for key,a in zip(['boxes','scores','classes'],row)})
 print(json.dumps(state),flush=True)
 if error:raise error

if __name__=='__main__':
 signal.signal(signal.SIGTERM,lambda s,f:(_ for _ in ()).throw(InterruptedError('Gate worker terminated')))
 p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('--index',type=int,required=True);main(p.parse_args().index)
