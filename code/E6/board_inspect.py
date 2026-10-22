"""Read-only admission inspection. Values are preserved without trimming digits."""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

T=Path(__file__).resolve().parents[1]

def rd(p):
    try:return Path(p).read_text().replace(chr(0),'').strip()
    except OSError as e:return {'error':type(e).__name__}

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def inspect():
    policies={}
    for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*')):
        policies[str(p)]={n:rd(p/n) for n in ['related_cpus','affected_cpus','scaling_driver',
          'scaling_available_frequencies','scaling_available_governors','scaling_governor',
          'scaling_min_freq','scaling_max_freq','scaling_setspeed','scaling_cur_freq','cpuinfo_cur_freq']}
    thermal={}
    for p in sorted(Path('<SYS_ROOT>/class/thermal').glob('thermal_zone*')):
        thermal[str(p)]={n:rd(p/n) for n in ['type','temp','policy']}
        thermal[str(p)]['trips']={q.name:rd(q) for q in p.glob('trip_point_*')}
    cooling={str(p):{n:rd(p/n) for n in ['type','cur_state','max_state']} for p in sorted(Path('<SYS_ROOT>/class/thermal').glob('cooling_device*'))}
    devfreq={str(p):{n:rd(p/n) for n in ['governor','min_freq','max_freq','cur_freq','available_frequencies']} for p in sorted(Path('<SYS_ROOT>/class/devfreq').glob('*'))}
    anc={os.getpid()};n=os.getppid()
    while n>1 and n not in anc:
        anc.add(n)
        try:n=int(next(x.split()[1] for x in Path('<PROC_ROOT>',str(n),'status').read_text().splitlines() if x.startswith('PPid:')))
        except Exception:break
    jobs=[];unread=0
    for p in Path('<PROC_ROOT>').glob('[0-9]*'):
        if int(p.name) in anc:continue
        try:
            c=(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')
            m=(p/'maps').read_text(errors='replace')
            if any(x in c for x in ['p1_process.py','p1_batch.py','rf_bc_driver.py','hb_dnn_perf']) or '/libdnn.so' in m or '/libhbrt_' in m:
                jobs.append({'pid':int(p.name),'command':c[:250]})
        except OSError:unread+=1
    return {'unix_ns':time.time_ns(),'monotonic_ns':time.perf_counter_ns(),'uid':os.getuid(),
      'platform':platform.platform(),'device':rd('<PROC_ROOT>/device-tree/model'),'online':rd('<SYS_ROOT>/devices/system/cpu/online'),
      'affinity':sorted(os.sched_getaffinity(0)),'boost':rd('<SYS_ROOT>/devices/system/cpu/cpufreq/boost'),
      'policies':policies,'devfreq':devfreq,'thermal':thermal,'cooling':cooling,
      'concurrent_known_sdk_jobs':jobs,'unreadable_proc_maps':unread,'inference_called':False}

if __name__=='__main__':
    record=inspect()
    dest=T/'reports'/sys.argv[1]
    with dest.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps(record,indent=2))
