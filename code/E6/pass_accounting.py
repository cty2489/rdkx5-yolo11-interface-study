"""Boundary-only cumulative accounting. Never called inside frame_step."""
import os,resource,time
from pathlib import Path
def snapshot():
 w0=time.perf_counter_ns();c0=time.thread_time_ns();r=resource.getrusage(resource.RUSAGE_SELF)
 policies={}
 for p in sorted(Path('<SYS_ROOT>/devices/system/cpu/cpufreq').glob('policy*')):
  policies[str(p)]={'related_cpus':[int(x) for x in (p/'related_cpus').read_text().split()],
   'time_in_state_raw':(p/'stats/time_in_state').read_text()}
 result={'monotonic_ns':w0,'user_seconds':r.ru_utime,'sys_seconds':r.ru_stime,'maxrss_kB':r.ru_maxrss,'voluntary_context_switches':r.ru_nvcsw,
  'involuntary_context_switches':r.ru_nivcsw,'proc_stat_raw':Path('<PROC_ROOT>/stat').read_text(),'policies':policies,'clock_ticks_per_second':os.sysconf('SC_CLK_TCK')}
 result['sampling_cost']={'wall_ns':time.perf_counter_ns()-w0,'thread_cpu_ns':time.thread_time_ns()-c0}
 return result
