"""E6 only. Latency includes queue wait; throughput is measured stream FPS."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import argparse,csv,hashlib,json,signal,sys,time,traceback
from pathlib import Path
T=Path(__file__).resolve().parents[1];P1=Path('<HOME>/p1_rfs_A_20261012_224112')
sys.path.insert(1,str(P1/'code/revision_20261013'));sys.path.insert(2,str(P1/'code'))
from p1_process import signature
from pass_accounting import snapshot
from pipeline_engine import run_pipeline
def load(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False)
def barrier(name):
 print('PILOT_EVENT '+json.dumps({'phase':name,'pid':os.getpid(),'monotonic_ns':time.perf_counter_ns()}),flush=True)
 assert sys.stdin.readline().strip()=='ACK'
def main(index):
 import numpy as np,cv2
 from bridge import SDK
 from consumer import consume
 plan=load(T/'protocol_frozen.json');ticket=load(T/'reports/execution_ticket.json');d=plan['design'];entry=plan['order'][index];mode=entry['strategy'];condition=entry['condition'];N=d['frames_per_pass']
 assert ticket['parent_pid']==os.getppid() and ticket['plan_sha256']==sha(T/'protocol_frozen.json')
 out=T/'run'/f'process_{index+1:02}_{condition}_{mode}';out.mkdir();save(out/'STARTED.json',{'pid':os.getpid(),'parent_pid':os.getppid(),'monotonic_ns':time.perf_counter_ns()})
 state={'status':'RUNNING','pid':os.getpid(),'index':index,'condition':condition,'strategy':mode,'NUMERIC_GUARD':'NOT_RUN','errors':[],'model_load_attempts':0,'model_loads':0,'affinity':sorted(os.sched_getaffinity(0)),'python_switch_interval_seconds':sys.getswitchinterval(),'SDK_context_slots':2}
 save(out/'state_initial.json',state);sdk=[];rows=[];warm=[];expected=[];detections=[];error=None;account={'setup_begin':snapshot(),'per_pass':[]}
 try:
  assert np.__version__==plan['numpy'] and cv2.__version__==plan['opencv'];cv2.setNumThreads(1)
  for item in plan['immutable_files']:assert sha(item['path'])==item['sha256'],item['path']
  for slot in range(2):
   state['model_load_attempts']+=1;sdk.append(SDK(plan['original_protocol']['library'],plan['models'][mode]['path'],mode));state['model_loads']+=1
   assert sdk[slot].lib.p1_sdk_version().decode()==plan['sdk']
   assert sdk[slot].props==load(T/'capture'/('correctness_'+mode)/'actual_abi.json')
  assert sdk[0].props==sdk[1].props
  spans=[]
  for slot,context in enumerate(sdk):
   for name,prop in context.props.items():
    address=context.lib.p1_output_pointer(context.ctx,context.indices[name]);spans.append({'slot':slot,'name':name,'begin':address,'end':address+prop['alignedByteSize']})
  for a in spans:
   for b in spans:
    if a['slot']!=b['slot']:assert min(a['end'],b['end'])<=max(a['begin'],b['begin']),'SDK output allocations alias between slots'
  save(out/'actual_abi.json',sdk[0].props);save(out/'slot_allocations.json',{'nonoverlapping_between_slots':True,'output_virtual_address_ranges':spans})
  previous=load(T/'capture'/('correctness_'+mode)/'warmup.json')['frames'];metadata=load(Path(plan['original_protocol']['coordinate_metadata_path']))
  account['setup_end']=snapshot();barrier('AFTER_SETUP');account['warmup_begin']=snapshot()
  def warm_result(final,row,views):
   f=row['frame'];item={'frame':f,'signature':signature(final),'candidates':row['candidates'],'detections':row['detections']}
   if item!=previous[f]:
    save(out/('warmup_mismatch_'+str(f)+'.json'),{'expected':previous[f],'actual':item})
    np.savez(out/('warmup_mismatch_'+str(f)+'.npz'),**final)
    raise RuntimeError('Pipeline warmup differs at frame '+str(f))
   # Final detection arrays must remain independent of reused SDK buffers.
   for name in ['final_boxes','final_scores','final_classes']:
    assert not any(np.shares_memory(final[name],v) for v in views.values())
   warm.append(item);expected.append(tuple(final[k] for k in ['final_boxes','final_scores','final_classes']))
  with Path(plan['original_protocol']['input']['path']).open('rb') as video:
   warm_threads=run_pipeline(video,sdk,consume,mode,metadata,N,1,warm_result)
   save(out/'warmup.json',{'status':'PASS','frames':warm});account['warmup_end']=snapshot();barrier('FORMAL_BEGIN');account['formal_begin']=snapshot()
   def formal_result(final,row,views):
    row.update(condition=condition,block=entry['block'],index=index,strategy=mode)
    assert row['candidates']==warm[row['frame']]['candidates'] and row['detections']==warm[row['frame']]['detections']
    assert row['full_float_bbox_elements']==(537600 if mode=='F' else 0) and row['selected_integer_bbox_elements']==0
    rows.append(row);detections.append(tuple(final[k] for k in ['final_boxes','final_scores','final_classes']))
   formal_threads=run_pipeline(video,sdk,consume,mode,metadata,N,3,formal_result)
   account['formal_end']=snapshot();barrier('FORMAL_END')
  assert len(rows)==3*N and len(warm)==N
  for i,arrays in enumerate(detections):
   for key,left,right in zip(['boxes','scores','classes'],expected[i%N],arrays):
    if not (left.dtype==right.dtype and left.shape==right.shape and np.array_equal(np.ascontiguousarray(left).view(np.uint8),np.ascontiguousarray(right).view(np.uint8))):
     save(out/'numeric_failure.json',{'record':i,'field':key,'expected_dtype':str(left.dtype),'actual_dtype':str(right.dtype),'expected_shape':list(left.shape),'actual_shape':list(right.shape)})
     np.savez(out/'numeric_failure_arrays.npz',expected=left,actual=right)
     raise RuntimeError('Pipeline formal prediction mismatch')
  np.savez(out/'formal_detections.npz',**{f'r{i:04}_{key}':array for i,arrays in enumerate(detections) for key,array in zip(['boxes','scores','classes'],arrays)})
  save(out/'numeric.json',{'status':'PASS','formal_frames':len(rows),'bitwise_final_arrays_equal':True,'slot_output_buffers_nonoverlapping':True,'warmup_all_fields_exact':True})
  save(out/'thread_roles.json',{'warmup':warm_threads,'formal':formal_threads})
  start=rows[0]['t0_ns'];end=rows[-1]['t_final_ns'];fps=len(rows)/((end-start)/1e9)
  overlaps=0
  for r in rows:
   overlaps+=sum(max(0,min(r['t_final_ns'],q['t_forward_ns'])-max(r['t_post_start_ns'],q['t_read_ns'])) for q in rows)
  save(out/'pipeline_throughput.json',{'formal_frames':len(rows),'first_input_ns':start,'last_result_ns':end,'stream_seconds':(end-start)/1e9,'measured_FPS':fps,
   'SDK_interval_CPU_post_service_overlap_seconds':overlaps/1e9,'contexts':2,'queue_capacity':2,'latency_definition':'input read start through result ready, including measured queue wait','SDK_scope':'unchanged external C SDK call envelope, includes Python scheduling/GIL reacquisition on return','post_service_excludes_queue_wait':True})
  for item in plan['immutable_files']:assert sha(item['path'])==item['sha256']
  state['status']='COMPLETE';state['NUMERIC_GUARD']='PASS'
 except BaseException as exc:
  error=exc;state['status']='FAILED';state['errors'].append({'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
 finally:
  if detections and not (out/'formal_detections.npz').exists():np.savez(out/'partial_formal_detections.npz',**{f'r{i:04}_{key}':array for i,arrays in enumerate(detections) for key,array in zip(['boxes','scores','classes'],arrays)})
  counts=[s.counts() for s in sdk];state.update(forward_attempts=sum(x['forward_attempts'] for x in counts),forward_completions=sum(x['forward_completions'] for x in counts),warmup_frames=len(warm),formal_records=len(rows))
  active_sdk_threads=bool(getattr(error,'do_not_close_contexts',False))
  if active_sdk_threads:state['contexts_not_freed_while_in_use']=True
  else:
   for s in sdk:s.close()
  account['process_end']=snapshot();save(out/'accounting.json',account)
  fields=list(rows[0]) if rows else ['condition','pass','frame','Pre_ms','SDK_ms','Post_ms','Total_ms']
  with (out/'formal.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
  state['csv_sha256']=sha(out/'formal.csv');save(out/'state.json',state)
 print('PILOT_RESULT '+json.dumps(state),flush=True)
 if active_sdk_threads:os._exit(2)
 if error:raise error
if __name__=='__main__':
 signal.signal(signal.SIGTERM,lambda s,f:(_ for _ in ()).throw(InterruptedError('Pipeline worker terminated')));p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);main(p.parse_args().index)
