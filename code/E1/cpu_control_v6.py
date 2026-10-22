"""CPU settings transaction, hardware telemetry, and emergency restoration.

No model loading or forward call exists in this module.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import sys
import threading
import time

T=Path(__file__).resolve().parents[1]

def read(p):return Path(p).read_text().replace(chr(0),'').strip()

def save_new(p,value):
    with Path(p).open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def settings():
    return {'boost':read('<SYS_ROOT>/devices/system/cpu/cpufreq/boost'),
      'policies':{str(p):{n:read(p/n) for n in ['scaling_governor','scaling_min_freq','scaling_max_freq','scaling_setspeed']}
                  for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*'))}}

def comparable(s):
    return {'boost':s['boost'],'policies':{p:{n:v for n,v in d.items() if n!='scaling_setspeed' or d['scaling_governor']=='userspace'}
                                          for p,d in s['policies'].items()}}

def mutate(p,value,reason,force=False):
    p=Path(p);old=read(p);value=str(value)
    if old==value and not force:return
    record={'monotonic_ns':time.perf_counter_ns(),'path':str(p),'old':old,'requested':value,'reason':reason}
    with (T/'reports/frequency_mutations.jsonl').open('a') as f:
        f.write(json.dumps(record)+'\n');f.flush();os.fsync(f.fileno())
    p.write_text(value+'\n')
    deadline=time.monotonic()+2;stable=0;observed=None
    while time.monotonic()<deadline:
        observed=read(p);stable=stable+1 if observed==value else 0
        if stable>=3:
            with (T/'reports/frequency_mutations.jsonl').open('a') as f:f.write(json.dumps({'event':'stable_readback','path':str(p),'value':observed,'monotonic_ns':time.perf_counter_ns()})+'\n')
            return
        time.sleep(.02)
    raise RuntimeError('CPU setting did not settle within 2 seconds: '+str((p,observed,value)))

FIXED={'F600':600000,'F1200':1200000,'L':1500000}
GOVERNORS={'D':'schedutil','O':'ondemand','F600':'userspace','F1200':'userspace','L':'userspace'}

def governor_info():
    policies={}
    for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*')):
        policies[str(p)]={n:read(p/n) for n in ['scaling_governor','scaling_min_freq','scaling_max_freq','related_cpus','affected_cpus','scaling_driver']}
    tunables={}
    for base in [Path('<SYS_ROOT>/devices/system/cpu/cpufreq'),*sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*'))]:
        for name in ['schedutil','ondemand','userspace']:
            d=base/name
            if d.exists():tunables[str(d)]={p.name:read(p) for p in sorted(d.iterdir()) if p.is_file()}
    return {'policies':policies,'tunables':tunables,'kernel':os.uname().release,'clock_ticks_per_second':os.sysconf('SC_CLK_TCK')}

def set_condition(mode):
    assert mode in GOVERNORS
    mutate('<SYS_ROOT>/devices/system/cpu/cpufreq/boost','0','frozen boost disabled')
    for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*')):
        assert GOVERNORS[mode] in read(p/'scaling_available_governors').split()
        target=FIXED.get(mode)
        if target:assert str(target) in read(p/'scaling_available_frequencies').split()
        mutate(p/'scaling_max_freq','1500000','expand upper limit before lower-limit change')
        mutate(p/'scaling_min_freq',str(target or 300000),'frozen '+mode)
        mutate(p/'scaling_max_freq',str(target or 1500000),'frozen '+mode)
        mutate(p/'scaling_governor',GOVERNORS[mode],'frozen '+mode)
        if target:mutate(p/'scaling_setspeed',target,'fixed target')
    current=settings()
    for p,v in current['policies'].items():
        assert v['scaling_governor']==GOVERNORS[mode]
        if mode in FIXED:assert read(Path(p)/'cpuinfo_cur_freq')==str(FIXED[mode])
    return current

def restore(role):
    # A controller and its independent watchdog may both request recovery.
    with (T/'reports/restore_mutex').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        before=json.loads((T/'reports/cpu_settings_before.json').read_text())
        for base,v in before['policies'].items():
            p=Path(base);curmax=int(read(p/'scaling_max_freq'));targetmax=int(v['scaling_max_freq'])
            mutate(p/'scaling_max_freq',max(curmax,targetmax),'restore '+role,force=True)
            mutate(p/'scaling_min_freq',v['scaling_min_freq'],'restore '+role,force=True)
            mutate(p/'scaling_max_freq',v['scaling_max_freq'],'restore '+role,force=True)
            mutate(p/'scaling_governor',v['scaling_governor'],'restore '+role,force=True)
            if v['scaling_governor']=='userspace':mutate(p/'scaling_setspeed',v['scaling_setspeed'],'restore '+role,force=True)
        mutate('<SYS_ROOT>/devices/system/cpu/cpufreq/boost',before['boost'],'restore '+role,force=True)
        stable_readbacks=[]
        for _ in range(3):stable_readbacks.append(settings());time.sleep(.05)
        after=stable_readbacks[-1];ok=all(comparable(v)==comparable(before) for v in stable_readbacks)
        receipt={'role':role,'status':'VERIFIED' if ok else 'FAILED','monotonic_ns':time.perf_counter_ns(),
                 'before':before,'after':after,'stable_readbacks':stable_readbacks,'comparison':'governor/min/max/boost and userspace setspeed if originally active'}
        dest=T/'reports'/('restore_'+role+'.json')
        save_new(dest,receipt)
        assert ok,'CPU configuration was not restored'
        return receipt

def watch(parent_pid,token,tag):
    deadline=time.monotonic()+86400
    while time.monotonic()<deadline:
        if (T/'reports'/('restore_'+tag+'.json')).exists():return
        try:
            text=Path('<PROC_ROOT>',str(parent_pid),'stat').read_text();current=text[text.rfind(')')+2:].split()[19]
            if current!=token:break
        except OSError:break
        active=T/'reports/active_child.json'
        if active.exists():
            item=json.loads(active.read_text())
            if not item.get('finished',False) and time.perf_counter_ns()-item['monotonic_ns']>900000000000:
                with contextlib.suppress(ProcessLookupError):os.kill(parent_pid,signal.SIGTERM)
                break
        time.sleep(2)
    childfile=T/'reports/active_child.json'
    if childfile.exists():
        child=json.loads(childfile.read_text())
        with contextlib.suppress(ProcessLookupError,OSError):
            txt=Path('<PROC_ROOT>',str(child['pid']),'stat').read_text();start=txt[txt.rfind(')')+2:].split()[19]
            if not child.get('finished',False) and start==child.get('starttime_ticks'):os.killpg(child['pid'],signal.SIGTERM)
    restore('watchdog_'+tag)
    save_new(T/'reports'/('watchdog_triggered_'+tag+'.json'),{'parent_pid':parent_pid,'monotonic_ns':time.perf_counter_ns()})

if __name__=='__main__' and sys.argv[1]=='watch':watch(int(sys.argv[2]),sys.argv[3],sys.argv[4])
