"""Read-only target environment guard. Never changes clocks, services or credentials."""
from __future__ import annotations
import os
import platform
from pathlib import Path
from p1_contract import require


def read_optional(path, missing):
    try:
        return path.read_text().rstrip('\x00\n').strip()
    except OSError as exc:
        missing[str(path)] = type(exc).__name__
        return None


def snapshot():
    missing = {}
    static = {'platform': platform.platform(), 'machine': platform.machine(),
              'device_model': read_optional(Path('<PROC_ROOT>/device-tree/model'), missing)}
    dynamic = {}
    for p in sorted(Path('<SYS_ROOT>/devices/system/cpu').glob('cpu[0-9]*/cpufreq/*')):
        if p.name in ('scaling_governor', 'scaling_min_freq', 'scaling_max_freq', 'boost'):
            static[str(p)] = read_optional(p, missing)
        elif p.name in ('scaling_cur_freq', 'cpuinfo_cur_freq'):
            dynamic[str(p)] = read_optional(p, missing)
    for base in (Path('<SYS_ROOT>/devices/system/cpu/cpufreq/boost'), Path('<SYS_ROOT>/devices/system/cpu/intel_pstate/no_turbo')):
        if base.exists():
            static[str(base)] = read_optional(base, missing)
    domains = {}
    for d in sorted(Path('<SYS_ROOT>/class/devfreq').glob('*')):
        name = read_optional(d/'name', missing) if (d/'name').exists() else d.name
        domains[d.name] = name
        for field in ('governor', 'min_freq', 'max_freq'):
            if (d/field).exists(): static[str(d/field)] = read_optional(d/field, missing)
        if (d/'cur_freq').exists(): dynamic[str(d/'cur_freq')] = read_optional(d/'cur_freq', missing)
    thermal = {}
    for zone in sorted(Path('<SYS_ROOT>/class/thermal').glob('thermal_zone*')):
        temperature = read_optional(zone/'temp', missing)
        trips = []
        for p in sorted(zone.glob('trip_point_*_type')):
            kind = read_optional(p, missing)
            threshold = read_optional(p.with_name(p.name.replace('_type', '_temp')), missing)
            if kind in ('passive', 'hot', 'critical') and threshold is not None:
                trips.append({'kind': kind, 'temperature_mC': int(threshold)})
        thermal[zone.name] = {'temperature_mC': int(temperature) if temperature is not None else None, 'trips': trips}
        static[zone.name + '_trips'] = trips
    # Exclude this process and ancestors; their command may name this diagnostic.
    ancestors = {os.getpid()}; p = os.getppid()
    while p > 1 and p not in ancestors:
        ancestors.add(p)
        try:
            p = int(next(x.split()[1] for x in (Path('<PROC_ROOT>')/str(p)/'status').read_text().splitlines() if x.startswith('PPid:')))
        except (OSError, StopIteration): break
    jobs, unreadable = [], 0
    for d in Path('<PROC_ROOT>').glob('[0-9]*'):
        pid = int(d.name)
        if pid in ancestors: continue
        try:
            cmd = (d/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if not cmd: continue
            is_job = any(x in cmd for x in ('p1_process.py', 'p1_batch.py', 'rdk_x5_yolo11_e2e_perf',
                                           'perf_6head_layout_fixed', 'hb_dnn_perf', 'hb_perf'))
            try:
                maps = (d/'maps').read_text(errors='replace')
                is_job |= '/libdnn.so' in maps or '/libhbrt_' in maps
            except OSError: unreadable += 1
            if is_job: jobs.append({'pid': pid, 'command': cmd[:400]})
        except OSError: unreadable += 1
    return {'static': static, 'dynamic': dynamic, 'thermal': thermal, 'devfreq_domains': domains,
            'concurrent_jobs': jobs, 'unreadable_process_records': unreadable, 'unavailable': missing,
            'process_check_scope': 'Known benchmark names and readable libdnn/libhbrt memory maps; not a kernel BPU scheduler trace',
            'system_settings_modified': False}


def check(current, baseline=None):
    require(current['static']['machine'] == 'aarch64' and 'RDK X5' in str(current['static']['device_model']), 'Not the target X5')
    require(not current['concurrent_jobs'], 'Concurrent benchmark/SDK process detected')
    require(any('scaling_governor' in k and v is not None for k,v in current['static'].items()), 'CPU policy unreadable')
    require(current['thermal'] and all(v['temperature_mC'] is not None for v in current['thermal'].values()), 'Temperature unreadable')
    for zone, record in current['thermal'].items():
        for trip in record['trips']:
            require(record['temperature_mC'] < trip['temperature_mC'], 'Thermal trip reached: ' + zone)
    if baseline is not None:
        require(current['static'] == baseline['static'], 'Board or fixed frequency/thermal configuration changed')
        require(set(current['dynamic']) == set(baseline['dynamic']), 'Frequency telemetry availability changed')
    # Missing devfreq counters are reported, never manufactured or declared measured.
    return {'status': 'PASS', 'snapshot': current,
            'limits': 'Available configured policies and thermal trips checked; dynamic frequency samples are observations, not fixed-frequency proof.'}
