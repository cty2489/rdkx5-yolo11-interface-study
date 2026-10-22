"""Two Python role threads, two independent SDK contexts, bounded slot ownership."""
import os,queue,threading,time,traceback
from pathlib import Path
def run_pipeline(video,sdk,consume,mode,metadata,frames,passes,on_result):
 free=queue.Queue(maxsize=2);free.put(0);free.put(1);ready=queue.Queue(maxsize=2)
 stop=threading.Event();errors=[];threads=[];events=[]
 def boundary(role,phase):
  tid=threading.get_native_id();base=Path('<PROC_ROOT>',str(os.getpid()),'task',str(tid))
  item={'role':role,'phase':phase,'tid':tid,'monotonic_ns':time.perf_counter_ns(),'affinity':sorted(os.sched_getaffinity(0))}
  for n in ['stat','sched']:
   try:item[n+'_raw']=(base/n).read_text()
   except OSError as e:item[n+'_error']=type(e).__name__
  events.append(item)
 def get(q):
  while not stop.is_set():
   try:return q.get(timeout=.1)
   except queue.Empty:pass
  raise InterruptedError('Pipeline stopped')
 def put(q,item):
  while not stop.is_set():
   try:q.put(item,timeout=.1);return
   except queue.Full:pass
  raise InterruptedError('Pipeline stopped')
 def fail(e):errors.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()});stop.set()
 def producer():
  boundary('inference','begin')
  try:
   for p in range(1,passes+1):
    video.seek(0)
    for f in range(frames):
     slot=get(free);t0=time.perf_counter_ns();raw=video.read(614400)
     if len(raw)!=614400:raise ValueError('Short NV12 frame')
     t_read=time.perf_counter_ns();sdk[slot].prepare(raw);t_prepare=time.perf_counter_ns();sdk[slot].forward();t_forward=time.perf_counter_ns()
     put(ready,(slot,p,f,t0,t_read,t_prepare,t_forward))
   put(ready,None)
  except BaseException as e:fail(e)
  finally:boundary('inference','end')
 def postprocessor():
  boundary('postprocessing','begin')
  try:
   while True:
    item=get(ready)
    if item is None:break
    slot,p,f,t0,t_read,t_prepare,t_forward=item
    t_post_start=time.perf_counter_ns();views=sdk[slot].outputs();t_outputs=time.perf_counter_ns()
    final,trace=consume(mode,views,sdk[slot].props,metadata,.3,.5);t_final=time.perf_counter_ns()
    row={'pass':p,'frame':f,'slot':slot,'t0_ns':t0,'t_read_ns':t_read,'t_prepare_ns':t_prepare,'t_forward_ns':t_forward,'t_post_start_ns':t_post_start,'t_outputs_ns':t_outputs,'t_final_ns':t_final,
     'Pre_ms':(t_read-t0)/1e6,'SDK_ms':(t_forward-t_read)/1e6,'Post_ms':(t_final-t_post_start)/1e6,'Total_ms':(t_final-t0)/1e6,
     'QueueWait_ms':(t_post_start-t_forward)/1e6,'InputPrepare_ms':(t_prepare-t_read)/1e6,'ForwardSync_ms':(t_forward-t_prepare)/1e6,
     'OutputAccess_ms':(t_outputs-t_post_start)/1e6,'Consumer_ms':(t_final-t_outputs)/1e6,'Unclassified_ms':0.0,
     'candidates':len(final['candidate_indices']),'detections':len(final['final_boxes']),
     'full_float_bbox_elements':trace['full_float_bbox_elements'],'selected_integer_bbox_elements':trace['selected_integer_bbox_elements']}
    for key in ['Select_ns','RestoreGather_ns','DFLCoordinates_ns','NMSAssemble_ns']:row[key.replace('_ns','_ms')]=trace[key]/1e6
    row['ConsumerUnclassified_ms']=row['Consumer_ms']-sum(row[k] for k in ['Select_ms','RestoreGather_ms','DFLCoordinates_ms','NMSAssemble_ms'])
    # End of actual result-ready latency. Callback is only validation/retention.
    # Slot is not returned until every SDK-backed read has completed.
    on_result(final,row,views)
    put(free,slot)
  except BaseException as e:fail(e)
  finally:boundary('postprocessing','end')
 threads=[threading.Thread(target=producer,daemon=True),threading.Thread(target=postprocessor,daemon=True)]
 try:
  for thread in threads:thread.start()
  while any(t.is_alive() for t in threads):
   for thread in threads:thread.join(.1)
   if errors:stop.set()
  if errors:raise RuntimeError(errors[0])
 finally:
  stop.set()
  for thread in threads:thread.join(2)
  if any(t.is_alive() for t in threads):
   error=RuntimeError('Pipeline SDK thread failed to terminate; do not free in-use contexts')
   error.do_not_close_contexts=True
   raise error
 return {'thread_boundaries':events,'slots':2,'dedicated_inference_threads':1,'dedicated_post_threads':1,'all_threads_joined':True}
