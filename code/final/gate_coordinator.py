"""Single short overhead gate and optional prespecified diagnostic; restore always."""
import contextlib,json,os,pwd,signal,subprocess,sys,time,traceback
from pathlib import Path
from formal_coordinator import check_boundary,dev_static,watchdog,stop_child,dump_monitor
from board_inspect import inspect
from cpu_control_v6 import T,save_new,settings,comparable,digest,set_condition,restore
from pilot_monitor_v6 import Monitor,boundary_capture,residency_snapshot
def require(ok,s):
 if not ok:raise RuntimeError(s)
def main(stage):
 require(os.getuid()==0,'Root required');require(not (T/('run_'+stage)).exists(),'Cannot replay a gate/diagnostic attempt')
 plan=json.loads((T/'inputs/design_frozen.json').read_text())
 entries=plan['reference_order']
 initial=inspect();require(not initial['concurrent_known_sdk_jobs'] and not initial['unreadable_proc_maps'],'Device not idle')
 original=settings();backup=T/'reports/cpu_settings_before.json'
 if backup.exists():require(comparable(original)==comparable(json.loads(backup.read_text())),'Original configuration not restored')
 else:save_new(backup,original)
 for item in [plan['input'],*plan['models'].values()]:require(digest(item['path'])==item['sha256'],'Identity changed')
 save_new(T/'reports'/(stage+'_frozen.json'),{'design_sha256':digest(T/'inputs/design_frozen.json'),'entries':entries,'initial':initial,'code_hashes':{p.name:digest(p) for p in sorted((T/'code').glob('*')) if p.is_file()}})
 ac=pwd.getpwnam('<USER>');run=T/('run_'+stage);run.mkdir();os.chown(run,ac.pw_uid,ac.pw_gid)
 state={'status':'RUNNING','stage':stage,'launched':0,'completed':0,'processes':[],'errors':[]};save_new(T/'reports'/(stage+'_STARTED.json'),{'pid':os.getpid(),'monotonic_ns':time.perf_counter_ns()})
 mon=None;child=None;boundaries=[];residencies=[];starts=[];watch,log=watchdog(stage)
 try:
  mon=Monitor();mon.start()
  for i,e in enumerate(entries):
   mon.pause();set_condition(e['condition']);mon.mode=e['condition'];mon.pid=None
   stable=[]
   for _ in range(3):
    s=boundary_capture(None,'policy_stable');check_boundary(s,e['condition'],initial);stable.append(s);time.sleep(.1)
   # Same frozen start-temperature band as v6, with bounded passive cooling.
   deadline=time.monotonic()+60
   while True:
    snap=boundary_capture(None,'before_child');check_boundary(snap,e['condition'],initial)
    temp={k:v for k,v in snap['values'].items() if k.endswith('/temp')}
    if not starts or all(abs(v-starts[0][k])<=2000 for k,v in temp.items()):break
    require(time.monotonic()<deadline,'Start temperature failed 2C band');time.sleep(1)
   starts.append(temp)
   child=subprocess.Popen([sys.executable,'-B','-u',str(T/'code/gate_worker.py'),stage,'--index',str(i)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,user=ac.pw_uid,group=ac.pw_gid,extra_groups=os.getgrouplist('<USER>',ac.pw_gid),env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
   text=Path('<PROC_ROOT>',str(child.pid),'stat').read_text();active={'pid':child.pid,'starttime_ticks':text[text.rfind(')')+2:].split()[19],'monotonic_ns':time.perf_counter_ns(),'index':i}
   tempdest=T/'reports/active_child.json.tmp';tempdest.write_text(json.dumps(active));os.replace(tempdest,T/'reports/active_child.json')
   state['launched']+=1;mon.pid=child.pid;mon.label=f'{stage}_{i+1:02}_{e["condition"]}_{e["strategy"]}_{e["variant"]}';mon.phase='setup';mon.resume()
   with (run/f'process_{i+1:02}.stdout.raw').open('xb') as out:
    for line in child.stdout:
     out.write(line);out.flush()
     if line.startswith(b'QUALITY_PROGRESS '):
      active['monotonic_ns']=time.perf_counter_ns();tempdest.write_text(json.dumps(active));os.replace(tempdest,T/'reports/active_child.json')
     if line.startswith(b'PILOT_EVENT '):
      event=json.loads(line[len(b'PILOT_EVENT '):]);mon.pause();require(mon.error is None,mon.error or 'Monitor failed')
      s=boundary_capture(child.pid,event['phase']);check_boundary(s,e['condition'],initial);boundaries.append({'index':i,**e,'event':event,'snapshot':s})
      res=residency_snapshot();residencies.append({'index':i,**e,'phase':event['phase'],'residency':res})
      require(mon.summary(mon.label)['budget_pass'],'Per-process monitor budget failed')
      mon.phase={'AFTER_SETUP':'warmup','FORMAL_BEGIN':'formal','FORMAL_END':'validation'}[event['phase']];mon.resume();child.stdin.write(b'ACK\n');child.stdin.flush()
   err=child.stderr.read();(run/f'process_{i+1:02}.stderr.raw').write_bytes(err);rc=child.wait();mon.pause();child=None
   active['finished']=True;tempdest.write_text(json.dumps(active));os.replace(tempdest,T/'reports/active_child.json')
   require(rc==0,'Gate worker failed; no replay');d=T/'capture'/('correctness_'+e['strategy']);receipt=json.loads((d/'state.json').read_text())
   require(receipt['status']=='PASS' and mon.summary(mon.label)['budget_pass'],'Gate numerical/monitor failure')
   state['processes'].append(receipt);state['completed']+=1
   print(json.dumps({'stage':stage,'completed':state['completed'],**e,'monitor_CPU_percent':mon.summary(mon.label)['one_core_cpu_percent']}),flush=True)
  state['status']='PASS'
 except BaseException as exc:state['status']='FAILED_STOP';state['errors'].append({'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
 finally:
  try:
   stop_child(child)
   if mon:mon.stop();dump_monitor(stage,mon)
   save_new(T/'reports'/(stage+'_boundaries.json'),boundaries);save_new(T/'reports'/(stage+'_residencies.json'),residencies)
  finally:
   state['restoration']=restore(stage)['status'];watch.wait(timeout=5);log.close();save_new(T/'reports'/(stage+'_state.json'),state)
 print(json.dumps({'stage':stage,'status':state['status'],'completed':state['completed'],'restoration':state['restoration']}),flush=True)
 if state['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
 signal.signal(signal.SIGTERM,lambda s,f:(_ for _ in ()).throw(InterruptedError('Coordinator terminated')))
 require(len(sys.argv)==2 and sys.argv[1]=='reference','Bad stage');main(sys.argv[1])
