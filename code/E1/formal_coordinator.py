"""Exactly one prespecified video process batch; no other experiment path."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse
import contextlib
import resource
import csv
import json
from pathlib import Path
import pwd
import signal
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from board_inspect import inspect
from cpu_control_v6 import T,comparable,digest,read,restore,save_new,set_condition,settings,FIXED,GOVERNORS,governor_info
from pilot_monitor_v6 import Monitor,boundary_capture,residency_snapshot

P1=Path('<HOME>/p1_rfs_A_20261012_224112')
DESIGN=json.loads((T/'inputs/design_frozen.json').read_text())
ORDER=DESIGN['order']
N=DESIGN['frames_per_pass'];PASSES=DESIGN['formal_passes']
def load(p):return json.loads(Path(p).read_text())
def active_receipt(record):
    temp=T/'reports/active_child.json.tmp';temp.write_text(json.dumps(record)+'\n');os.replace(temp,T/'reports/active_child.json')
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def dev_static(s):return {p:{n:v[n] for n in ('governor','min_freq','max_freq')} for p,v in s['devfreq'].items()}
def watchdog(tag):
    text=Path('<PROC_ROOT>',str(os.getpid()),'stat').read_text();token=text[text.rfind(')')+2:].split()[19]
    log=(T/'reports'/('watchdog_'+tag+'.log')).open('xb')
    child=subprocess.Popen([sys.executable,'-B',str(T/'code/cpu_control_v6.py'),'watch',str(os.getpid()),token,tag],
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    return child,log
def stop_child(child):
    if child is not None and child.poll() is None:
        with contextlib.suppress(ProcessLookupError):os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):os.killpg(child.pid,signal.SIGKILL)
            child.wait(timeout=5)
def dump_monitor(prefix,mon):
    save_new(T/'reports'/(prefix+'_monitor_samples.json'),mon.samples)
    save_new(T/'reports'/(prefix+'_monitor_segments.json'),mon.segments)
    save_new(T/'reports'/(prefix+'_monitor_initialization.json'),{'resources':mon.initialization_resources,
        'sampler_thread':mon.initialization_thread,'polls':mon.setup_samples})
    save_new(T/'reports'/(prefix+'_monitor_summary.json'),mon.summary())
def check_boundary(s,mode,baseline):
    require(dev_static(s)==dev_static(baseline),'BPU/DDR/GPU configuration changed')
    require(s['CPU_settings']['boost']=='0','Boost changed')
    for p,v in s['CPU_settings']['policies'].items():
        require(v['scaling_governor']==GOVERNORS[mode],'CPU governor changed')
        require(v['scaling_min_freq']==str(FIXED.get(mode,300000)) and v['scaling_max_freq']==str(FIXED.get(mode,1500000)),'CPU limits changed')
    for p,v in s['values'].items():
        if p.endswith('/temp'):require(v<80000,'Temperature ceiling reached')
        if p.endswith('/cur_state'):require(v==0,'Thermal cooling activated')
        if mode in FIXED and p.endswith('/cpuinfo_cur_freq'):require(v==FIXED[mode],'Actual fixed CPU frequency departed target')
    require(s['devfreq']['<SYS_ROOT>/class/devfreq/3a000000.bpu']['cur_freq']=='996000000','BPU frequency changed at boundary')
    require(s['devfreq']['<SYS_ROOT>/class/devfreq/soc:ddrc-freq']['cur_freq']=='4266000000','DDR frequency changed at boundary')

def admit():
    require(os.getuid()==0,'Root required')
    require(not (T/'protocol_frozen.json').exists() and not (T/'FORMAL_STARTED.json').exists(),'Single-use admission')
    require(load(T/'reports/correctness_gate.json')['status']=='PASS','Current video correctness not passed')
    initial=inspect();save_new(T/'reports/admission_environment.json',initial)
    before=settings()
    save_new(T/'reports/cpu_settings_before.json',before)
    require(comparable(before)==comparable(load(T/'reports/cpu_settings_before.json')),'Original settings not restored')
    require(not initial['concurrent_known_sdk_jobs'] and initial['unreadable_proc_maps']==0,'Not idle')
    v6=load('<HOME>/rf_cpu_fixed_A_pilot_v6_20261015_134516/protocol_frozen.json')
    thermal=lambda x:{p:{n:v[n] for n in ('type','policy','trips')} for p,v in x['thermal'].items()}
    require(dev_static(initial)==dev_static(v6['baseline']) and thermal(initial)==thermal(v6['baseline']),'Devfreq/thermal changed')
    require(DESIGN['monitor_change']=='fixed-target safety check only; identical sampling path and budgets','Unregistered monitor change')
    governor_reference={'D':governor_info()}
    if any(e['condition']=='O' for e in ORDER):
        watcher,wlog=watchdog('admission')
        try:
            set_condition('O');governor_reference['O']=governor_info()
        finally:
            restore('admission');watcher.wait(timeout=5);wlog.close()
    save_new(T/'reports/governor_reference.json',governor_reference)
    models=DESIGN['models'];objects=[{'path':x['path'],'sha256':x['sha256']} for x in models.values()]+[DESIGN['input']]
    objects+=[{'path':str(p),'sha256':digest(p)} for p in sorted((T/'code').glob('*')) if p.is_file()]
    objects+=[{'path':str(T/'inputs/design_frozen.json'),'sha256':digest(T/'inputs/design_frozen.json')},{'path':DESIGN['metadata_path'],'sha256':DESIGN['metadata_sha256']}]
    objects+=v6['immutable_files']
    for x in objects:require(digest(x['path'])==x['sha256'],'Identity changed: '+x['path'])
    original={**v6['original_protocol'],'library':str(T/'code/libbaselinebridge.so'),'input':DESIGN['input'],'coordinate_metadata_path':DESIGN['metadata_path']}
    frozen={**v6,'schema':DESIGN['schema'],'status':'FROZEN','order':ORDER,'models':models,'max_processes':len(ORDER),'max_forwards':DESIGN['max_forwards'],
      'formal_records':DESIGN['formal_records'],'baseline':initial,'immutable_files':objects,'original_protocol':original,'measurement_version':'baseline','design':DESIGN,'governor_reference':governor_reference,
      'design_sha256':digest(T/'inputs/design_frozen.json'),'correctness_gate_sha256':digest(T/'reports/correctness_gate.json'),
      'batch_sources':[{'path':str(p),'sha256':digest(p)} for p in sorted((T/'code').glob('*')) if p.is_file()]}
    save_new(T/'protocol_frozen.json',frozen);save_new(T/'reports/admission_result.json',{'status':'PASS','protocol_sha256':digest(T/'protocol_frozen.json'),'model_forwards':0})
    print(json.dumps({'status':'PASS','protocol_sha256':digest(T/'protocol_frozen.json')}),flush=True)

def compare_saved_predictions(left,right,index):
    diffs=[];count=0
    with zipfile.ZipFile(left) as a,zipfile.ZipFile(right) as b:
        require(set(a.namelist())==set(b.namelist()),'Prediction array names differ')
        for name in sorted(a.namelist()):
            x,y=a.read(name),b.read(name);count+=1
            if x!=y:
                positions=[i for i,(l,r) in enumerate(zip(x,y)) if l!=r]
                positions+=list(range(min(len(x),len(y)),max(len(x),len(y))))
                diffs.append({'array':name,'left_bytes':len(x),'right_bytes':len(y),'byte_positions':positions})
    result={'status':'PASS' if not diffs else 'FAIL','left':str(left),'right':str(right),
            'arrays_compared':count,'frames':PASSES*N,'exact_NPY_payload_and_header':True,'differences':diffs}
    save_new(T/'reports'/f'prediction_comparison_{index+1:02}.json',result)
    require(not diffs and count==3*PASSES*N,'Final R/F or frequency-condition predictions differ')
    return result

def check_residency(records,index,condition):
    own={r['phase']:r['residency'] for r in records if r['index']==index}
    result={'index':index,'condition':condition,'policies':{}}
    for policy,start in own['FORMAL_BEGIN']['policies'].items():
        end=own['FORMAL_END']['policies'][policy]
        if start['available'] and end['available']:
            parse=lambda text:{int(a):int(b) for a,b in (line.split() for line in text.splitlines())}
            a,b=parse(start['raw']),parse(end['raw']);delta={k:b[k]-a[k] for k in a}
            result['policies'][policy]={'available':True,'raw_counter_delta':delta}
            require(all(v>=0 for v in delta.values()),'CPU frequency residency counter reset')
            if condition in FIXED:require(sum(delta.values())>0 and all(v==0 for k,v in delta.items() if k!=FIXED[condition]),'Non-target CPU residency in fixed formal interval')
        else:result['policies'][policy]={'available':False}
    save_new(T/'reports'/f'residency_check_{index+1:02}.json',result)

def formal():
    require(not (T/'FORMAL_STARTED.json').exists() and not (T/'run').exists(),'Existing attempt must not be restarted')
    require(load(T/'reports/admission_result.json')['status']=='PASS','Admission not passed')
    protocol=load(T/'protocol_frozen.json')
    require(protocol['order']==ORDER and protocol['max_forwards']==DESIGN['max_forwards'],'Frozen order or budget changed')
    require(comparable(settings())==comparable(load(T/'reports/cpu_settings_before.json')),'CPU original backup differs')
    for x in protocol['batch_sources']:require(digest(x['path'])==x['sha256'],'Pilot source changed')
    initial=inspect();require(not initial['concurrent_known_sdk_jobs'] and initial['unreadable_proc_maps']==0,'Concurrent SDK work or incomplete census')
    save_new(T/'FORMAL_STARTED.json',{'pid':os.getpid(),'monotonic_ns':time.perf_counter_ns(),'protocol_sha256':digest(T/'protocol_frozen.json')})
    save_new(T/'reports/execution_ticket.json',{'parent_pid':os.getpid(),'plan_sha256':digest(T/'protocol_frozen.json')})
    (T/'run').mkdir();ac=pwd.getpwnam('<USER>');os.chown(T/'run',ac.pw_uid,ac.pw_gid)
    state={'status':'RUNNING','planned_processes':len(ORDER),'launched_processes':0,'completed_processes':0,'planned_forwards':DESIGN['max_forwards'],
           'planned_formal_records':DESIGN['formal_records'],'processes':[],'failures':[],'inference_stage':'FORMAL_SINGLE_BATCH'}
    save_new(T/'reports/batch_state_initial.json',state)
    save_new(T/'reports/cpu_residency_before.json',residency_snapshot())
    watch,log=watchdog('formal');mon=None;child=None;error=None;boundaries=[];transitions=[];starts=[];first_predictions={};residency_boundaries=[]
    try:
        mon=Monitor();mon.start()
        for index,entry in enumerate(ORDER):
            mon.pause();set_condition(entry['condition'])
            actual_info=governor_info()
            if entry['condition'] in ['D','O']:require(actual_info['tunables']==protocol['governor_reference'][entry['condition']]['tunables'],'Governor parameters changed')
            mon.mode=entry['condition'];mon.pid=None
            stable=[]
            for _ in range(3):
                actual={str(p):int(read(p/'cpuinfo_cur_freq')) for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*'))}
                if entry['condition'] in FIXED:require(all(v==FIXED[entry['condition']] for v in actual.values()),'Fixed frequency unstable before process')
                stable.append({'monotonic_ns':time.perf_counter_ns(),'actual_kHz':actual});time.sleep(.1)
            cooldown=[];deadline=time.monotonic()+60
            while True:
                check=boundary_capture(None,'before_child_'+str(index));check_boundary(check,entry['condition'],protocol['baseline'])
                current={p:v for p,v in check['values'].items() if p.endswith('/temp')}
                cooldown.append(check)
                if not starts or all(abs(current[p]-starts[0][p])<=2000 for p in current):break
                require(time.monotonic()<deadline,'Start temperature did not return within frozen 2 C band in 60 seconds')
                time.sleep(1)
            starts.append(current);transitions.append({'index':index,**entry,'stable_readbacks':stable,'start_temperatures':current,'preprocess_boundaries':cooldown})
            require(mon.error is None,mon.error or 'Monitor failed')
            command=[sys.executable,'-B','-u',str(T/'code/formal_worker.py'),'--index',str(index)]
            child_usage_before=resource.getrusage(resource.RUSAGE_CHILDREN);child_wall_before=time.perf_counter_ns()
            child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,
                 user=ac.pw_uid,group=ac.pw_gid,extra_groups=os.getgrouplist('<USER>',ac.pw_gid),env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            state['launched_processes']+=1
            active={'pid':child.pid,'index':index,**entry,'monotonic_ns':time.perf_counter_ns()}
            text=Path('<PROC_ROOT>',str(child.pid),'stat').read_text();active['starttime_ticks']=text[text.rfind(')')+2:].split()[19]
            active_receipt(active)
            mon.pid=child.pid;label=f"process_{index+1:02}_{entry['condition']}_{entry['strategy']}";mon.label=label;mon.phase='setup';mon.resume()
            rec={**active,'command':command}
            with (T/'run'/f'process_{index+1:02}.stdout.raw').open('xb') as out:
                for line in child.stdout:
                    out.write(line);out.flush()
                    if line.startswith(b'PILOT_EVENT '):
                        event=json.loads(line[len(b'PILOT_EVENT '):]);require(event['pid']==child.pid,'Wrong barrier sender')
                        mon.pause();require(mon.error is None,mon.error or 'Monitor failed')
                        snapshot=boundary_capture(child.pid,event['phase']);check_boundary(snapshot,entry['condition'],protocol['baseline'])
                        w0=time.perf_counter_ns();c0=time.thread_time_ns();resident=residency_snapshot();resident['proc_stat_raw']=Path('<PROC_ROOT>/stat').read_text();resident['governor_info']=governor_info();resident_cost={'wall_ns':time.perf_counter_ns()-w0,'thread_cpu_ns':time.thread_time_ns()-c0}
                        residency_boundaries.append({'index':index,'block':entry['block'],'condition':entry['condition'],'strategy':entry['strategy'],'phase':event['phase'],'residency':resident,'cost':resident_cost})
                        boundaries.append({'index':index,**entry,'event':event,'snapshot':snapshot,'runtime_monitor_so_far':mon.summary(label)})
                        require(mon.summary(label)['budget_pass'],'Per-process runtime monitor CPU exceeded 0.5%')
                        mon.phase={'AFTER_SETUP':'warmup','FORMAL_BEGIN':'formal','FORMAL_END':'validation'}[event['phase']]
                        mon.resume();child.stdin.write(b'ACK\n');child.stdin.flush()
            err=child.stderr.read();(T/'run'/f'process_{index+1:02}.stderr.raw').write_bytes(err)
            rc=child.wait();child_usage_after=resource.getrusage(resource.RUSAGE_CHILDREN)
            rec['process_CPU_time']={'user_seconds':child_usage_after.ru_utime-child_usage_before.ru_utime,'sys_seconds':child_usage_after.ru_stime-child_usage_before.ru_stime,'wall_seconds':(time.perf_counter_ns()-child_wall_before)/1e9,'scope':'entire reaped worker including imports, setup, warmup, formal, validation and serialization'}
            mon.pause();mon.pid=None;rec['exit_code']=rc;state['processes'].append(rec);child=None
            active_receipt({**active,'finished':True})
            require(rc==0,'Pilot child failed; stop without replay')
            directory=T/'run'/label;receipt=load(directory/'state.json')
            require(receipt['status']=='COMPLETE' and receipt['NUMERIC_GUARD']=='PASS','Numerical or completion guard failed')
            require(receipt['forward_attempts']==receipt['forward_completions']==(PASSES+1)*N and receipt['formal_records']==PASSES*N,'Forward or row count changed')
            require(mon.summary(label)['budget_pass'] and mon.summary()['budget_pass'],'Runtime monitor CPU budget exceeded')
            with (directory/'formal.csv').open(newline='') as f:rows=list(csv.DictReader(f))
            t0,t1=int(rows[0]['t0_ns']),int(rows[-1]['t_final_ns'])
            load_samples=[s for s in mon.samples if s['label']==label and s['phase']=='formal' and t0<=s['monotonic_ns']<=t1]
            require(bool(load_samples),'No actual frequency observation during formal model load')
            if entry['condition'] in FIXED:require(all(v==FIXED[entry['condition']] for s in load_samples for p,v in s['values'].items() if p.endswith('/cpuinfo_cur_freq')),'Fixed frequency departed target under load')
            check_residency(residency_boundaries,index,entry['condition'])
            rec['formal_actual_frequency_samples']=len(load_samples);rec['runtime_monitor']=mon.summary(label)
            predictions=directory/'formal_detections.npz'
            reference_key='M6' if entry['strategy']=='M6' else 'RF'
            if reference_key not in first_predictions:first_predictions[reference_key]=predictions
            else:compare_saved_predictions(first_predictions[reference_key],predictions,index)
            state['completed_processes']+=1
            save_new(T/'reports'/f'process_completed_{index+1:02}.json',{'index':index,'block':entry['block'],'condition':entry['condition'],'strategy':entry['strategy'],'monitor':mon.summary(label),'state':receipt})
            print(json.dumps({'completed':state['completed_processes'],**entry,'forward_completions':(PASSES+1)*N,'monitor_CPU_percent':mon.summary(label)['one_core_cpu_percent']}),flush=True)
        state['status']='COMPLETE_STOP'
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        state['status']='FAILED_STOP';state['failures'].append(error)
    finally:
        try:
            stop_child(child)
            if mon is not None:mon.stop();dump_monitor('formal',mon)
            save_new(T/'reports/thread_boundaries.json',boundaries)
            save_new(T/'reports/residency_boundaries.json',residency_boundaries)
            save_new(T/'reports/process_frequency_transitions.json',transitions)
            save_new(T/'reports/cpu_residency_after.json',residency_snapshot())
        finally:
            state['restoration']=restore('formal')['status'];watch.wait(timeout=5);log.close()
            state['remaining_owned_child']=None;save_new(T/'reports/batch_state.json',state)
            final=inspect();save_new(T/'reports/board_final.json',final)
            require(dev_static(final)==dev_static(initial),'Devfreq configuration changed after pilot')
    if error:raise RuntimeError(error['message'])
    print(json.dumps(state),flush=True)

if __name__=='__main__':
    def interrupted(signum,frame):raise InterruptedError('Controller interrupted: '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['admit','formal']);args=p.parse_args()
    if args.phase=='admit':admit()
    else:formal()
