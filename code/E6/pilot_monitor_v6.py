"""One v6 simplification: sysfs-only 1 Hz monitoring, paired CPU/wall windows.

No model imports. No <PROC_ROOT> access in the periodic sampling path.
Initialization and controller boundary costs are never charged to runtime.
"""
import contextlib
import math
import os
from pathlib import Path
import signal
import threading
import time

from cpu_control_v6 import read,settings,FIXED

def timed_record(w0,c0):
    c1=time.thread_time_ns();w1=time.perf_counter_ns()
    return {'wall_start_ns':w0,'wall_end_ns':w1,'thread_cpu_start_ns':c0,'thread_cpu_end_ns':c1,
            'wall_ns':w1-w0,'thread_cpu_ns':c1-c0}

def residency_snapshot():
    result={'monotonic_ns':time.perf_counter_ns(),'policies':{}}
    for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*')):
        q=p/'stats/time_in_state'
        try:result['policies'][str(p)]={'available':True,'raw':q.read_text()}
        except OSError as e:result['policies'][str(p)]={'available':False,'error':type(e).__name__,'errno':e.errno}
    return result

def thread_boundary(pid):
    records={}
    if pid is None:return {'pid':None,'threads':records}
    for d in sorted(Path('<PROC_ROOT>',str(pid),'task').glob('*')):
        info={'tid':int(d.name),'errors':{}}
        for name in ('stat','status','sched'):
            try:info[name+'_raw']=(d/name).read_text()
            except OSError as e:info['errors'][name]={'type':type(e).__name__,'errno':e.errno}
        if 'stat_raw' in info:
            try:
                txt=info['stat_raw'];v=txt[txt.rfind(')')+2:].split()
                info.update(last_cpu=int(v[36]),utime_ticks=int(v[11]),stime_ticks=int(v[12]),starttime_ticks=int(v[19]))
            except (ValueError,IndexError) as e:info['errors']['stat_parse']=type(e).__name__
        if 'status_raw' in info:
            info['context_switches']={line.split(':',1)[0]:int(line.split(':',1)[1])
                  for line in info['status_raw'].splitlines() if 'ctxt_switches:' in line}
        info['migrations']=None
        if 'sched_raw' in info:
            for line in info['sched_raw'].splitlines():
                if 'nr_migrations' in line and ':' in line:
                    try:info['migrations']=int(line.split(':',1)[1].strip())
                    except ValueError:info['errors']['migration_parse']=line
                    break
        try:info['affinity']=sorted(os.sched_getaffinity(int(d.name)))
        except OSError as e:info['errors']['affinity']=type(e).__name__
        records[d.name]=info
    return {'pid':pid,'monotonic_ns':time.perf_counter_ns(),'threads':records,
            'interpretation':'Discrete last CPU and cumulative counters at boundaries; no per-frame migration trace.'}

def boundary_capture(pid,phase):
    w0=time.perf_counter_ns();c0=time.thread_time_ns()
    values={}
    for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*')):
        values[str(p/'cpuinfo_cur_freq')]=int(read(p/'cpuinfo_cur_freq'))
    for pattern in ('thermal_zone*/temp','cooling_device*/cur_state'):
        for p in sorted(Path('<SYS_ROOT>/class/thermal').glob(pattern)):values[str(p)]=int(read(p))
    dev={str(p):{n:read(p/n) for n in ('governor','min_freq','max_freq','cur_freq')}
         for p in sorted(Path('<SYS_ROOT>/class/devfreq').glob('*'))}
    result={'scope':'boundary_only; production frames blocked or not started','phase':phase,'unix_ns':time.time_ns(),
            'values':values,'CPU_settings':settings(),'devfreq':dev,'thread_state':thread_boundary(pid)}
    result['cost']=timed_record(w0,c0)
    return result

class Monitor:
    def __init__(self):
        w0=time.perf_counter_ns();c0=time.thread_time_ns()
        paths=[p/'cpuinfo_cur_freq' for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*'))]
        paths+=sorted(Path('<SYS_ROOT>/class/thermal').glob('thermal_zone*/temp'))
        paths+=sorted(Path('<SYS_ROOT>/class/thermal').glob('cooling_device*/cur_state'))
        self.fds={str(p):os.open(p,os.O_RDONLY) for p in paths}
        self.initialization_resources={'scope':'initialization_resource_setup','paths':list(self.fds),'cost':timed_record(w0,c0)}
        self.condition=threading.Condition();self.ready=threading.Event();self.requested=False;self.active=False;self.stopping=False
        self.mode='D';self.pid=None;self.label='idle';self.phase='idle';self.error=None
        self.samples=[];self.setup_samples=[];self.segments=[];self.initialization_thread=None
        self.next_due=None;self.cpu_overruns=0

    def _poll(self,scope):
        w0=time.perf_counter_ns();c0=time.thread_time_ns()
        values={}
        for path,fd in self.fds.items():
            os.lseek(fd,0,os.SEEK_SET);values[path]=int(os.read(fd,128).decode().strip())
        c1=time.thread_time_ns();w1=time.perf_counter_ns()
        item={'scope':scope,'monotonic_ns':w0,'end_ns':w1,'unix_ns':time.time_ns(),
              'thread_cpu_start_ns':c0,'thread_cpu_end_ns':c1,'poll_cpu_ns':c1-c0,'poll_wall_ns':w1-w0,
              'sampling_tid':threading.get_native_id(),'mode':self.mode,'pid':self.pid,'label':self.label,'phase':self.phase,'values':values}
        (self.setup_samples if scope=='initialization' else self.samples).append(item)
        for p,v in values.items():
            if p.endswith('/temp') and v>=80000:raise RuntimeError('Temperature ceiling reached')
            if p.endswith('/cur_state') and v!=0:raise RuntimeError('Thermal cooling activated')
            if self.mode in FIXED and p.endswith('/cpuinfo_cur_freq') and v!=FIXED[self.mode]:raise RuntimeError('Actual CPU frequency departed fixed target')
        if scope=='runtime':
            self.cpu_overruns=self.cpu_overruns+1 if item['poll_cpu_ns']>5000000 else 0
            if self.cpu_overruns>=3:raise RuntimeError('Sustained monitor CPU overhead above 0.5% at 1 Hz')
        return item

    def _fail(self,exc):
        self.error=type(exc).__name__+': '+str(exc)
        if self.pid:
            with contextlib.suppress(ProcessLookupError):os.killpg(self.pid,signal.SIGTERM)

    def loop(self):
        w0=time.perf_counter_ns();c0=time.thread_time_ns()
        try:
            os.setpriority(os.PRIO_PROCESS,threading.get_native_id(),19)
            os.sched_setaffinity(threading.get_native_id(),{0})
            for _ in range(3):self._poll('initialization')
        except BaseException as exc:self._fail(exc)
        self.initialization_thread={'scope':'initialization_sampler_thread','tid':threading.get_native_id(),
                                    'nice':os.getpriority(os.PRIO_PROCESS,threading.get_native_id()),
                                    'affinity':sorted(os.sched_getaffinity(0)),'cost':timed_record(w0,c0)}
        self.ready.set()
        while self.error is None:
            with self.condition:
                while not self.requested and not self.stopping:self.condition.wait()
                if self.stopping:break
            label,phase,mode,pid=self.label,self.phase,self.mode,self.pid
            w0=time.perf_counter_ns();c0=time.thread_time_ns()
            with self.condition:self.active=True;self.condition.notify_all()
            try:
                while True:
                    with self.condition:
                        if not self.requested or self.stopping:break
                        delay=0 if self.next_due is None else max(0,(self.next_due-time.perf_counter_ns())/1e9)
                        if delay:
                            self.condition.wait(delay);continue
                    item=self._poll('runtime');self.next_due=item['monotonic_ns']+1000000000
            except BaseException as exc:self._fail(exc)
            finally:
                cost=timed_record(w0,c0)
                self.segments.append({'scope':'runtime','label':label,'phase':phase,'mode':mode,'pid':pid,**cost})
                with self.condition:self.active=False;self.requested=False;self.condition.notify_all()
        with self.condition:self.active=False;self.condition.notify_all()

    def start(self):
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
        if not self.ready.wait(5):raise RuntimeError('Monitor initialization timeout')
        if self.error:raise RuntimeError(self.error)

    def resume(self):
        with self.condition:
            if self.error:raise RuntimeError(self.error)
            self.requested=True;self.condition.notify_all()
            if not self.condition.wait_for(lambda:self.active or self.error,timeout=5):raise RuntimeError('Monitor resume timeout')
            if self.error:raise RuntimeError(self.error)

    def pause(self):
        with self.condition:
            self.requested=False;self.condition.notify_all()
            if not self.condition.wait_for(lambda:not self.active,timeout=5):raise RuntimeError('Monitor pause timeout')

    def summary(self,label=None):
        if self.active:raise RuntimeError('Pause monitor before requesting paired-window statistics')
        segments=[s for s in self.segments if label is None or s['label']==label]
        samples=[s for s in self.samples if label is None or s['label']==label]
        cpu=sum(s['thread_cpu_ns'] for s in segments);wall=sum(s['wall_ns'] for s in segments)
        pct=100*cpu/wall if wall else 0
        walls=sorted(s['poll_wall_ns']/1e6 for s in samples)
        return {'scope':'runtime_only','label':label,'samples':len(samples),'window_count':len(segments),
                'runtime_wall_ns':wall,'runtime_thread_cpu_ns':cpu,'one_core_cpu_percent':pct,
                'window_definition':'sum of matching sampler-thread CPU and monotonic wall deltas measured at identical runtime segment boundaries',
                'initialization_and_boundaries_included':False,'poll_p99_ms':walls[math.ceil(.99*len(walls))-1] if walls else None,
                'poll_max_ms':max(walls) if walls else None,'period_seconds':1,'sampler_nice':19,'sampler_affinity':[0],
                'errors':self.error,'wall_p99_gate':'DIAGNOSTIC_ONLY','budget_pass':pct<=.5 and self.error is None}

    def stop(self):
        self.pause()
        with self.condition:self.stopping=True;self.condition.notify_all()
        if hasattr(self,'thread'):
            self.thread.join(5)
            if self.thread.is_alive():raise RuntimeError('Monitor did not stop')
        for fd in self.fds.values():os.close(fd)
