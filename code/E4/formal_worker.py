"""One authorized formal process: original full warmup and three timed passes.

Production frame_step is unchanged. The shared bridge supports actual 6/9 outputs. Only three final
detection-array references are retained after t_final; no per-frame copies,
hashing, telemetry or output writes occur during the measured frame work.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import signal
import time
import traceback
import resource
from pass_accounting import snapshot

T=Path(__file__).resolve().parents[1]
P1=Path('<HOME>/p1_rfs_A_20261012_224112')
sys.path.insert(0,str(P1/'code/revision_20261013'))
sys.path.insert(1,str(P1/'code'))
sys.path.insert(0,str(T/'code'))
from p1_process import frame_step,signature,compare_abi
from p1_contract import FIELDS

def load(p):return json.loads(Path(p).read_text())
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def barrier(phase):
    print('PILOT_EVENT '+json.dumps({'phase':phase,'pid':os.getpid(),'monotonic_ns':time.perf_counter_ns()}),flush=True)
    require(sys.stdin.readline().strip()=='ACK','Controller barrier failed')

def main(index):
    def interrupted(signum,frame):raise InterruptedError('Owned pilot process interrupted: '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    plan=load(T/'protocol_frozen.json');ticket=load(T/'reports/execution_ticket.json')
    require(ticket['parent_pid']==os.getppid() and ticket['plan_sha256']==digest(T/'protocol_frozen.json'),'Not launched by owning pilot controller')
    N=plan['design']['frames_per_pass'];PASSES=plan['design']['formal_passes']
    entry=plan['order'][index];mode=entry['strategy'];condition=entry['condition']
    out=T/'run'/f"process_{index+1:02}_{condition}_{mode}"
    out.mkdir(exist_ok=False)
    save(out/'STARTED.json',{'pid':os.getpid(),'parent_pid':os.getppid(),'monotonic_ns':time.perf_counter_ns()})
    state={'status':'RUNNING','index':index,'condition':condition,'strategy':mode,'pid':os.getpid(),
           'block':entry['block'],'position':entry['position'],'warmup_frames':0,'formal_records':0,'model_load_attempts':0,'model_loads':0,
           'forward_attempts':0,'forward_completions':0,'NUMERIC_GUARD':'NOT_RUN','errors':[],
           'plan_sha256':ticket['plan_sha256'],'affinity':sorted(os.sched_getaffinity(0)),
           'scheduler_policy':os.sched_getscheduler(0),'nice':os.getpriority(os.PRIO_PROCESS,0)}
    save(out/'state_initial.json',state)
    sdk=None;warmup=[];rows=[];detections=[];expected=[];error=None
    accounting={'setup_begin':snapshot(),'per_pass':[]}
    try:
        import numpy as np
        import cv2
        from bridge import SDK
        from consumer import consume
        require(np.__version__==plan['numpy'] and cv2.__version__==plan['opencv'],'Math runtime changed')
        cv2.setNumThreads(1);require(cv2.getNumThreads()==1,'OpenCV threading mismatch')
        original=plan['original_protocol']
        for item in plan['immutable_files']:
            require(digest(item['path'])==item['sha256'],'Immutable source changed: '+item['path'])
        state['model_load_attempts']=1
        model=plan['models'][mode]['path']
        sdk=SDK(plan['original_protocol']['library'],model,mode);state['model_loads']=1
        require(sdk.lib.p1_sdk_version().decode()==plan['sdk'],'SDK changed')
        require(sdk.props==load(T/'capture'/('correctness_'+mode)/'actual_abi.json'),'Correctness-stage ABI changed')
        save(out/'actual_abi.json',sdk.props)
        previous=load(T/'capture'/('correctness_'+mode)/'warmup.json')['frames']
        require(len(previous)==N,'Archived full-video numeric reference missing')
        metadata=load(original['coordinate_metadata_path'])
        accounting['setup_end']=snapshot()
        barrier('AFTER_SETUP')
        accounting['warmup_begin']=snapshot()
        with Path(original['input']['path']).open('rb') as video:
            for frame in range(N):
                final,row=frame_step(video,sdk,consume,mode,metadata)
                item={'frame':frame,'signature':signature(final),'candidates':row['candidates'],'detections':row['detections']}
                if item!=previous[frame]:
                    save(out/f'warmup_mismatch_{frame:03}.json',{'expected':previous[frame],'actual':item})
                    np.savez(out/f'warmup_mismatch_{frame:03}.npz',**final)
                    raise RuntimeError('Warmup differs from verified same-model full-video signature')
                warmup.append(item)
                expected.append(tuple(final[k] for k in ('final_boxes','final_scores','final_classes')))
            save(out/'warmup.json',{'status':'PASS','reference':'same-model correctness capture; R/F additionally verified against archived P1','frames':warmup})
            accounting['warmup_end']=snapshot()
            barrier('FORMAL_BEGIN')
            accounting['formal_begin']=snapshot()
            next_release=time.perf_counter_ns()
            period_ns=int(1e9/entry['fps']) if entry.get('fps') else 0
            for pass_id in range(1,PASSES+1):
                pass_before=snapshot() if plan['design'].get('record_per_pass') else None
                video.seek(0)
                for frame in range(N):
                    pace_start=time.perf_counter_ns() if period_ns else 0
                    target=next_release if period_ns else 0
                    if period_ns and target>pace_start:time.sleep((target-pace_start)/1e9)
                    release=time.perf_counter_ns() if period_ns else 0
                    final,row=frame_step(video,sdk,consume,mode,metadata)
                    if plan['measurement_version']=='profile':
                        row.update(sdk.timing());row['SDKOther_ms']=row['SDK_ms']-sum(row[k] for k in ['SDKCopy_ms','SDKClean_ms','SDKSubmit_ms','SDKWait_ms','SDKInvalidate_ms','SDKRelease_ms'])
                        require(row['SDKOther_ms']>=0,'SDK substage accounting failed')
                    row.update(condition=condition,block=entry['block'],index=index,strategy=mode,**{'pass':pass_id,'frame':frame})
                    if period_ns:
                        row.update(pacing_wait_ns=release-pace_start,release_target_ns=target,start_lateness_ns=max(0,release-target),arrival_to_result_ms=(row['t_final_ns']-target)/1e6)
                        next_release+=period_ns
                    else:row.update(pacing_wait_ns=0,release_target_ns=0,start_lateness_ns=0,arrival_to_result_ms=row['Total_ms'])
                    rows.append(row)
                    # Retain only already-owned detection arrays, without copies.
                    detections.append(tuple(final[k] for k in ('final_boxes','final_scores','final_classes')))
                    require(row['candidates']==warmup[frame]['candidates'] and row['detections']==warmup[frame]['detections'],
                            'Formal candidate/detection count differs from warmup')
                if pass_before is not None:accounting['per_pass'].append({'pass':pass_id,'before':pass_before,'after':snapshot()})
            accounting['formal_end']=snapshot()
            barrier('FORMAL_END')
        comparisons=0;max_error=0.0;mismatches=[];nonfinite=0
        for i,arrays in enumerate(detections):
            for key,left,right in zip(('boxes','scores','classes'),expected[i%N],arrays):
                left=np.ascontiguousarray(left);right=np.ascontiguousarray(right)
                require(left.dtype==right.dtype and left.shape==right.shape,'Formal detection shape/dtype changed')
                if np.issubdtype(right.dtype,np.floating):
                    nonfinite+=int(np.count_nonzero(~np.isfinite(right)))
                    if right.size:max_error=max(max_error,float(np.max(np.abs(left.astype(np.float64)-right.astype(np.float64)))))
                bad=np.argwhere(left.view(np.uint8)!=right.view(np.uint8))
                if bad.size:mismatches.append({'record':i,'field':key,'byte_mismatch_count':len(bad),'byte_positions':bad.tolist()})
                comparisons+=1
        np.savez(out/'formal_detections.npz',**{f'r{i:04}_{key}':array for i,arrays in enumerate(detections)
                 for key,array in zip(('boxes','scores','classes'),arrays)})
        save(out/'numeric.json',{'status':'PASS' if not mismatches and not nonfinite else 'FAIL',
             'formal_arrays_compared':comparisons,'formal_frames':len(detections),'max_absolute_error':max_error,
             'nonfinite_count':nonfinite,'bitwise_differences':mismatches,
             'warmup_all_fields_exact_against_same_model_correctness_capture':True,
             'RF_correctness_reference_additionally_matches_archived_P1':mode!='M6',
             'formal_scope':'All final boxes/scores/classes, against same-frame exact warmup; counts also checked after t_final',
             'formal_loop_instrumentation':'Only scalar rows and references to three final arrays; no copies/hash/telemetry/writes'})
        require(not mismatches and not nonfinite,'Formal output differs from the verified same-video reference')
        state['NUMERIC_GUARD']='PASS'
        for item in plan['immutable_files']:require(digest(item['path'])==item['sha256'],'Immutable file changed after run')
        require(len(warmup)==N and len(rows)==PASSES*N and sdk.counts()['forward_completions']==(PASSES+1)*N,'Pilot forward budget mismatch')
        state['status']='COMPLETE'
    except BaseException as e:
        error=e;state['status']='FAILED';state['errors'].append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})
    finally:
        # Preserve all available owned detection arrays even after interruption.
        # This is outside production frame_step and adds no model forwards.
        if detections and not (out/'formal_detections.npz').exists():
            try:
                import numpy as np
                np.savez(out/'partial_formal_detections.npz',**{f'r{i:04}_{key}':array for i,arrays in enumerate(detections)
                     for key,array in zip(('boxes','scores','classes'),arrays)})
            except BaseException as e:
                state['errors'].append({'stage':'preserve_partial_arrays','error':str(e)})
        if sdk:
            state.update(sdk.counts())
            try:sdk.close();state['sdk_closed']=True
            except BaseException as e:error=error or e;state['status']='FAILED';state['errors'].append({'stage':'close','error':str(e)})
        state.update(warmup_frames=len(warmup),formal_records=len(rows))
        accounting['process_end']=snapshot();save(out/'accounting.json',accounting)
        with (out/'formal.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['condition']+FIELDS+['pacing_wait_ns','release_target_ns','start_lateness_ns','arrival_to_result_ms']+(['SDKCopy_ms','SDKClean_ms','SDKSubmit_ms','SDKWait_ms','SDKInvalidate_ms','SDKRelease_ms','SDKOther_ms'] if plan['measurement_version']=='profile' else []));w.writeheader();w.writerows(rows)
        state['csv_sha256']=digest(out/'formal.csv')
        save(out/'state.json',state)
    print('PILOT_RESULT '+json.dumps(state),flush=True)
    if error:raise error

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);args=p.parse_args()
    require(0<=args.index<len(load(T/'protocol_frozen.json')['order']),'Index outside frozen order');main(args.index)
