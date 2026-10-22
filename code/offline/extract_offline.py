"""Offline-only Step 3 extraction. No remote connection or inference imports/calls.
All input paths are immutable existing batches; outputs use exclusive creation.
Run: python -B extract_offline.py [new_output_directory]
"""
import csv, hashlib, itertools, json, math, shutil, statistics, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import t

SOURCE = Path('<PROJECT_ROOT>/experiments/frequency_pacing_followup_20261021_111632')
OLD = SOURCE.parent/'final_equivalence_8condition_20261021_185155/step3'
OUT = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
LABELS = ['E1_A_v2','E1_B_v2','E2_A_v2','E3_A','E3_B','E3_C','E6_A']
inputs={}
def track(p):
    p=Path(p); inputs.setdefault(str(p),hashlib.sha256(p.read_bytes()).hexdigest()); return p
def load(p): return json.loads(track(p).read_text(encoding='utf-8-sig'))
def read(p):
    with track(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def write(name,rows):
    assert rows,name
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def groups(rows,keys):
    d=defaultdict(list)
    for r in rows: d[tuple(r[k] for k in keys)].append(r)
    return sorted(d.items())
def tis(snapshot,path):
    return {int(k):int(v) for k,v in (x.split() for x in snapshot['policies'][path]['time_in_state_raw'].splitlines())}
def meta_keys(): return ['batch','video','policy','config','pacing','block','position','process_id','process_index']
def mean(x): return statistics.mean(x)
def sd(x): return statistics.stdev(x)
def close(a,b):
    assert math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-9),(a,b)
def intervals_overlap(a,b):
    assert all(x[1]<=y[0] for x,y in zip(a,a[1:]))
    assert all(x[1]<=y[0] for x,y in zip(b,b[1:]))
    total=0; i=j=0
    while i<len(a) and j<len(b):
        total+=max(0,min(a[i][1],b[j][1])-max(a[i][0],b[j][0]))
        if a[i][1]<=b[j][1]: i+=1
        else: j+=1
    return total

residency=[]; cpu=[]; freq=[]; ledger=[]; q1=[]; e6=[]; e6_frames=defaultdict(list); roles=[]; governor=[]
for label in LABELS:
    base=SOURCE/'evidence'/label
    plan=load(base/'protocol_frozen.json'); state=load(base/'reports/batch_state.json')
    ps=read(SOURCE/'reports'/label/'process_summary.csv'); by_index={int(r['process_index']):r for r in ps}
    assert len(plan['order'])==len(state['processes'])==len(ps)
    e1_values=defaultdict(list)
    for entry,run in zip(plan['order'],state['processes']):
        index=entry['index']+1; p=by_index[index]
        assert str(run['pid'])==p['process_id']
        assert entry['condition']==p['policy'] and entry['strategy']==p['config']
        directory=base/'run'/f"process_{index:02}_{entry['condition']}_{entry['strategy']}"
        a=load(directory/'accounting.json')
        m={k:p[k] for k in meta_keys()}
        begin,end=a['formal_begin'],a['formal_end']
        wall=(end['monotonic_ns']-begin['monotonic_ns'])/1e9
        user=end['user_seconds']-begin['user_seconds']; system=end['sys_seconds']-begin['sys_seconds']
        cpu.append({**m,'window':'formal','user_seconds':user,'sys_seconds':system,'wall_seconds':wall,'CPU_ratio':(user+system)/wall,'CPU_one_core_percent':100*(user+system)/wall})
        whole=run['process_CPU_time'];u,s,w=[whole[k] for k in ['user_seconds','sys_seconds','wall_seconds']]
        cpu.append({**m,'window':'whole_reaped_process','user_seconds':u,'sys_seconds':s,'wall_seconds':w,'CPU_ratio':(u+s)/w,'CPU_one_core_percent':100*(u+s)/w})
        close(user,p['formal_user_seconds']);close(system,p['formal_sys_seconds']);close(wall,p['formal_wall_seconds'])
        windows=[('formal',0,begin,end)]+[('per_pass',z['pass'],z['before'],z['after']) for z in a['per_pass']]
        for phase,pass_id,left,right in windows:
            assert left['clock_ticks_per_second']==right['clock_ticks_per_second']==100
            for path,record in left['policies'].items():
                x,y=tis(left,path),tis(right,path);assert set(x)==set(y)
                delta={k:y[k]-x[k] for k in x};assert min(delta.values())>=0
                cores=record['related_cpus'];assert cores==list(range(8))
                for k,count in delta.items():
                    for core in cores:
                        residency.append({**m,'phase':phase,'pass':pass_id,'core':core,'cpufreq_policy_path':path,'frequency_MHz':k/1000,'raw_USER_HZ_delta':count,'residency_seconds':count/100,'shared_policy_mapping':1,'independent_per_core_counter':0})
                if phase=='formal':
                    ticks=sum(delta.values());assert ticks>0
                    for core in cores:
                        freq.append({**m,'core':core,'cpufreq_policy_path':path,'resident_wall_seconds':ticks/100,'time_weighted_mean_MHz':sum(k*v for k,v in delta.items())/(1000*ticks)})
        if label.startswith('E1') and p['policy'] in ['D','O'] or label=='E6_A':
            raw=read(directory/'formal.csv')
            expected={'A':132,'B':187,'C':154}[p['video']]*3
            assert len(raw)==expected
            assert len({(r['pass'],r['frame']) for r in raw})==expected
            if label.startswith('E1'):
                for r in raw:
                    value=(int(r['t_final_ns'])-int(r['t0_ns']))/1e6
                    close(value,r['Total_ms']);e1_values[p['policy'],p['config']].append(value)
            if label=='E6_A':
                ticks=[{k:int(r[k]) for k in ['t0_ns','t_read_ns','t_forward_ns','t_post_start_ns','t_final_ns']} for r in raw]
                assert all(z['t0_ns']<=z['t_read_ns']<=z['t_forward_ns']<=z['t_post_start_ns']<=z['t_final_ns'] for z in ticks)
                sdk=[(z['t_read_ns'],z['t_forward_ns']) for z in ticks]
                post=[(z['t_post_start_ns'],z['t_final_ns']) for z in ticks]
                inter=intervals_overlap(sdk,post)
                span=ticks[-1]['t_final_ns']-ticks[0]['t0_ns']
                sdk_ns=sum(b-a for a,b in sdk);post_ns=sum(b-a for a,b in post)
                saved=load(directory/'pipeline_throughput.json')
                fps=len(raw)*1e9/span
                close(fps,saved['measured_FPS']);close(inter/1e9,saved['SDK_interval_CPU_post_service_overlap_seconds'])
                er={**m,'formal_frames':len(raw),'stream_ns':span,'FPS':fps,'SDK_envelope_ns':sdk_ns,'CPU_post_service_ns':post_ns,'SDK_CPU_intersection_ns':inter,'SDK_CPU_union_ns':sdk_ns+post_ns-inter,'SDK_envelope_seconds':sdk_ns/1e9,'CPU_post_service_seconds':post_ns/1e9,'overlap_seconds':inter/1e9,'overlap_percent_stream':100*inter/span}
                for stage,col in [('Pre','Pre_ms'),('SDK','SDK_ms'),('Post','Post_ms'),('QueueWait','QueueWait_ms'),('Total','Total_ms')]:
                    values=[float(r[col]) for r in raw]
                    for q,v in zip([50,95,99],np.percentile(values,[50,95,99],method='linear')):er[f'{stage}_P{q}_ms']=float(v)
                    er[f'{stage}_mean_ms']=mean(values)
                    e6_frames[p['policy'],p['config'],stage].extend(values)
                e6.append(er)
                boundaries=load(directory/'thread_roles.json')
                for phase,record in boundaries.items():
                    for z in record['thread_boundaries']:
                        stat=z.get('stat_raw','');parts=stat[stat.rfind(')')+2:].split() if stat else []
                        roles.append({**m,'phase':phase,'role':z['role'],'boundary':z['phase'],'monotonic_ns':z['monotonic_ns'],'tid':z['tid'],'allowed_cores':','.join(map(str,z['affinity'])),'last_processor':parts[36] if len(parts)>36 else 'NA','migration_count':'NA','sched_error':z.get('sched_error','')})
    for (policy,config),values in sorted(e1_values.items()):
        q=np.percentile(values,[50,95,99],method='linear')
        q1.append({'batch':label,'video':plan['design']['video'],'policy':policy,'config':config,'frames':len(values),'p50_ms':q[0],'p95_ms':q[1],'p99_ms':q[2],'method':'linear'})
    ledger.append({'batch':label,'processes':len(ps),'formal_frames':sum({'A':396,'B':561,'C':462}[p['video']]*(10 if label=='E2_A_v2' else 1) for p in ps),'new_processes':0,'new_forwards':0})
    gov=read(SOURCE/'reports'/label/'governor_settings.csv')
    governor.extend(gov)
    for name in ['governor_settings.csv','thread_boundary_schedule.csv']:
        path=track(SOURCE/'reports'/label/name)
        target=OUT/(label+'_'+name);assert not target.exists();shutil.copyfile(path,target)
    print(json.dumps({'batch':label,'processes':len(ps),'status':'extracted'}),flush=True)

freq_cfg=[]
for key,rows in groups(freq,['batch','policy','config','pacing','core']):
    sec=sum(r['resident_wall_seconds'] for r in rows)
    freq_cfg.append(dict(zip(['batch','policy','config','pacing','core'],key),processes=len(rows),time_weighted_mean_MHz=sum(r['time_weighted_mean_MHz']*r['resident_wall_seconds'] for r in rows)/sec,summed_resident_wall_seconds=sec,shared_policy='policy0',independent_per_core_counter=0))
cpu_cfg=[]
for key,rows in groups(cpu,['batch','policy','config','pacing','window']):
    u=sum(r['user_seconds'] for r in rows);s=sum(r['sys_seconds'] for r in rows);w=sum(r['wall_seconds'] for r in rows)
    cpu_cfg.append(dict(zip(['batch','policy','config','pacing','window'],key),processes=len(rows),user_seconds_sum=u,sys_seconds_sum=s,wall_seconds_sum=w,CPU_ratio_pooled=(u+s)/w,CPU_percent_pooled=100*(u+s)/w,CPU_percent_process_mean=mean(r['CPU_one_core_percent'] for r in rows),CPU_percent_sample_SD=sd(r['CPU_one_core_percent'] for r in rows)))
resident_cfg=[]
for key,rows in groups([r for r in residency if r['phase']=='formal'],['batch','policy','config','pacing','core','frequency_MHz']):
    resident_cfg.append(dict(zip(['batch','policy','config','pacing','core','frequency_MHz'],key),residency_seconds=sum(r['residency_seconds'] for r in rows),raw_USER_HZ_delta=sum(r['raw_USER_HZ_delta'] for r in rows),shared_policy='policy0',independent_per_core_counter=0))

fps_contrasts=[];fps_raw=[]
for policy in ['D','L']:
    for left,right in [('M6','R'),('R','F'),('M6','F')]:
        # right - left, positive = higher right FPS. No latency sign ambiguity.
        values=[]
        for block in range(1,7):
            l=next(r for r in e6 if r['policy']==policy and r['config']==left and int(r['block'])==block)
            r=next(r for r in e6 if r['policy']==policy and r['config']==right and int(r['block'])==block)
            diff=r['FPS']-l['FPS'];values.append(diff)
            fps_raw.append({'batch':'E6_A','policy':policy,'contrast':left+'->'+right,'block':block,'left_FPS':l['FPS'],'right_FPS':r['FPS'],'FPS_right_minus_left':diff})
        m,s=mean(values),sd(values);h=float(t.ppf(.975,5))*s/math.sqrt(6)
        fps_contrasts.append({'batch':'E6_A','policy':policy,'contrast':left+'->'+right,'n_blocks':6,'df':5,'mean_FPS_right_minus_left':m,'sample_SD':s,'CI95_low':m-h,'CI95_high':m+h,**{f'block_{i+1}':v for i,v in enumerate(values)}})
fps_summary=[];overlap_summary=[]
for key,rows in groups(e6,['policy','config']):
    fps_summary.append(dict(zip(['policy','config'],key),processes=len(rows),FPS_mean=mean(r['FPS'] for r in rows),FPS_sample_SD=sd(r['FPS'] for r in rows)))
    o=dict(zip(['policy','config'],key),processes=len(rows))
    for name in ['stream_ns','SDK_envelope_ns','CPU_post_service_ns','SDK_CPU_intersection_ns','SDK_CPU_union_ns']:
        o[name.replace('_ns','_seconds_mean')]=mean(r[name] for r in rows)/1e9
        o[name.replace('_ns','_seconds_sample_SD')]=sd(r[name] for r in rows)/1e9
    overlap_summary.append(o)
latency=[]
for (policy,config,stage),values in sorted(e6_frames.items()):
    q=np.percentile(values,[50,95,99],method='linear')
    latency.append({'batch':'E6_A','policy':policy,'config':config,'stage':stage,'frames':len(values),'p50_ms':q[0],'p95_ms':q[1],'p99_ms':q[2],'method':'linear'})

# Full-series comparison to the previously archived extraction, separate from raw recomputation.
checks={}
original=read(OLD/'frequency_per_config_policy_core.csv')
index={(r['batch'],r['policy'],r['config'],r['pacing'],int(r['core'])):r for r in original}
assert len(index)==len(freq_cfg)
checks['frequency_max_abs_MHz']=max(abs(r['time_weighted_mean_MHz']-float(index[r['batch'],r['policy'],r['config'],r['pacing'],r['core']]['time_weighted_mean_MHz'])) for r in freq_cfg)
assert checks['frequency_max_abs_MHz']<1e-9
original=read(OLD/'CPU_time_per_process.csv'); ix={(r['batch'],r['process_id'],r['window']):r for r in original}
assert len(ix)==len(cpu)
checks['CPU_max_abs_percent']=max(abs(r['CPU_one_core_percent']-float(ix[r['batch'],r['process_id'],r['window']]['CPU_one_core_percent'])) for r in cpu)
assert checks['CPU_max_abs_percent']<1e-9
original=read(OLD/'E1_Total_percentiles.csv'); ix={(r['batch'],r['policy'],r['config']):r for r in original}
for r in q1:
    for field in ['p50_ms','p95_ms','p99_ms']:close(r[field],ix[r['batch'],r['policy'],r['config']][field])
original=read(OLD/'E6_FPS_pair_CIs_both_signs.csv');ix={(r['policy'],r['contrast'].replace('-','->')):r for r in original}
for r in fps_contrasts:
    prev=ix[r['policy'],r['contrast']]
    for field,of in [('mean_FPS_right_minus_left','FPS_right_minus_left'),('CI95_low','FPS_RminusL_CI95_low'),('CI95_high','FPS_RminusL_CI95_high')]:close(r[field],prev[of])
checks.update({'E1_percentile_fields':len(q1)*3,'E6_FPS_CI_fields':len(fps_contrasts)*3,'raw_processes':len(cpu)//2,'new_board_connections':0,'new_forwards':0})

datasets={'frequency_per_process_core.csv':freq,'frequency_per_config_policy_core.csv':freq_cfg,'frequency_residency_per_core_full.csv':residency,'frequency_residency_per_config_core.csv':resident_cfg,'CPU_time_per_process.csv':cpu,'CPU_utilization_per_config.csv':cpu_cfg,'E1_Total_percentiles.csv':q1,'E6_overlap_FPS_latency_per_process.csv':e6,'E6_overlap_per_config.csv':overlap_summary,'E6_FPS_per_config.csv':fps_summary,'E6_FPS_paired_CI.csv':fps_contrasts,'E6_FPS_block_differences.csv':fps_raw,'E6_latency_percentiles.csv':latency,'E6_thread_role_core_boundaries.csv':roles,'source_batch_ledger.csv':ledger}
for name,rows in datasets.items():write(name,rows)

params=[]
for r in governor:
    meta={k:r[k] for k in ['batch','video','process_id','process_index','block','position','policy','config','pacing','boundary','kernel','cpufreq_policy','governor','minimum_kHz','maximum_kHz']}
    for path,values in json.loads(r['tunables']).items():
        for k,v in values.items():params.append({**meta,'parameter_path':path,'parameter':k,'value':v})
write('governor_parameters_per_boundary.csv',params)
param_unique=[]
for key,rows in groups(params,['governor','parameter_path','parameter','value']):
    param_unique.append(dict(zip(['governor','parameter_path','parameter','value'],key),boundary_records=len(rows)))
write('governor_parameters_unique.csv',param_unique)

worker=track(SOURCE/'evidence/E2_A_v2/code/formal_worker.py')
frame=track(SOURCE/'dependencies/frozen_project_sources/board_sources/home/<USER>/p1_rfs_A_20261012_224112/code/revision_20261013/p1_process.py')
ws=worker.read_text();fs=frame.read_text()
def excerpt(txt,start,end):
    lines=txt.splitlines();a=next(i for i,z in enumerate(lines) if start in z);b=next(i for i,z in enumerate(lines[a:],a) if end in z)
    return '\n'.join(lines[a:b]),a+1,b
wx,wa,wb=excerpt(ws,'            next_release=','                    # Retain')
fx,fa,fb=excerpt(fs,'def frame_step(','    t_read = clock()')
fx+='\n    t_read = clock()'
e2def=[{'batch':'E2_A_v2','sleep_function':'time.sleep','sleep_argument':'(target-pace_start)/1e9','busy_wait':0,'sleep_inside_frame_step':0,'t0_after_sleep':1,'Total_includes_pacing_sleep':0,'clock':'time.perf_counter_ns','period_fps30_ns':int(1e9/30),'period_fps15_ns':int(1e9/15),'formal_passes':30}]
write('E2_pacing_definition.csv',e2def)
excerpt_text=f'{worker}\nSHA256 {inputs[str(worker)]}\nlines {wa}-{wb}\n{wx}\n\n{frame}\nSHA256 {inputs[str(frame)]}\nlines {fa}-{fb+1}\n{fx}\n'
(OUT/'E2_t0_and_pacing_excerpt.txt').open('x',encoding='utf8').write(excerpt_text)

def number(x):
    if isinstance(x,float):return f'{x:.9f}'
    return str(x)
def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(number(v).replace('|','\\|') for v in row)+' |' for row in rows]
lines=['# Step3_report','',f'源目录：`{SOURCE}`','',
    '| 新板端连接 | 新进程 | 新前向 | 源批次数 | 源进程数 |', '|---:|---:|---:|---:|---:|',f'| 0 | 0 | 0 | {len(LABELS)} | {len(cpu)//2} |','',
    '## 1. 频率、驻留与CPU时间','',
    '`D=schedutil(300–1500 MHz)`；`O=ondemand(300–1500 MHz)`；`L=userspace(1500 MHz)`；`F600/F1200=userspace(600/1200 MHz)`。','',
    '`f_mean=Σ(f_MHz×Δtime_in_state)/ΣΔtime_in_state`；`USER_HZ=100`；`CPU%=100×(Δuser+Δsys)/Δwall`；`100%=1 core`。','',
    '`formal`：formal_begin→formal_end；`whole_reaped_process`：父进程回收窗口；E2 formal 含 sleep。聚合CPU%=ΣCPU秒/Σwall秒×100；CSV另列进程CPU%均值与样本SD。','',
    '| policy counter | related/affected cores | independent per-core counters |', '|---|---|---:|','| policy0 | 0,1,2,3,4,5,6,7 | 0 |','',
    '下表每行的频率对应core 0–7同一policy0计数；完整逐核映射和零驻留频点保存在CSV。','']
cpidx={(r['batch'],r['policy'],r['config'],r['pacing'],r['window']):r for r in cpu_cfg}
summary=[]
for r in freq_cfg:
    if r['core']!=0:continue
    key=(r['batch'],r['policy'],r['config'],r['pacing'])
    cf=cpidx[key+('formal',)];cw=cpidx[key+('whole_reaped_process',)]
    summary.append([*key,r['processes'],r['time_weighted_mean_MHz'],r['summed_resident_wall_seconds'],cf['CPU_percent_pooled'],cw['CPU_percent_pooled']])
lines+=table(['batch','policy','config','pacing','n','MHz','residency s','formal CPU%','whole CPU%'],summary)
lines+=['','[逐进程CPU时间](CPU_time_per_process.csv) · [CPU汇总](CPU_utilization_per_config.csv) · [完整驻留](frequency_residency_per_core_full.csv) · [配置驻留](frequency_residency_per_config_core.csv) · [逐进程频率](frequency_per_process_core.csv) · [逐配置频率](frequency_per_config_policy_core.csv)','',
    '## 2. E1 Total分位数','', '`linear`；同批次内正式逐帧合并；单位ms。','']
lines+=table(['batch','policy','config','frames','p50','p95','p99'],[[r[k] for k in ['batch','policy','config','frames','p50_ms','p95_ms','p99_ms']] for r in q1])
lines+=['','[CSV](E1_Total_percentiles.csv)','','## 3. E2 t0及限帧','',
    '| sleep | 忙等 | sleep位置 | t0在sleep后 | Total含sleep | formal passes |', '|---|---:|---|---:|---:|---:|', '| time.sleep((target-pace_start)/1e9) | 0 | frame_step调用前 | 1 | 0 | 30 |','',
    f'`formal_worker.py:{wa}–{wb}`；SHA256 `{inputs[str(worker)]}`','', '```python',wx,'```','',f'`p1_process.py:{fa}–{fb+1}`；SHA256 `{inputs[str(frame)]}`','', '```python',fx,'```','',
    '[代码与绝对路径](E2_t0_and_pacing_excerpt.txt) · [定义CSV](E2_pacing_definition.csv)','',
    '## 4. E6','', '`FPS=396×10^9/(last t_final_ns−first t0_ns)`；差值=FPS右−FPS左；Student t，n=6，df=5；CI=均差±t(0.975,5)×SD/√6。','']
lines+=table(['policy','config','n','FPS mean','FPS sample SD'],[[r[k] for k in ['policy','config','processes','FPS_mean','FPS_sample_SD']] for r in fps_summary])
lines+=['']+table(['policy','left→right','mean FPS右−左','sample SD','CI95 low','CI95 high','df'],[[r[k] for k in ['policy','contrast','mean_FPS_right_minus_left','sample_SD','CI95_low','CI95_high','df']] for r in fps_contrasts])
lines+=['']+table(['policy','left→right','b1','b2','b3','b4','b5','b6'],[[r['policy'],r['contrast']]+[r[f'block_{i}'] for i in range(1,7)] for r in fps_contrasts])
lines+=['','[FPS CI](E6_FPS_paired_CI.csv) · [逐区组差值](E6_FPS_block_differences.csv)','',
    '`SDK envelope=[t_read_ns,t_forward_ns)`；`CPU post service=[t_post_start_ns,t_final_ns)`；`overlap=两组区间交集`；SDK非纯BPU时间。','',
    '下表为每进程正式396帧区间累计量的进程均值，单位s。','']
lines+=table(['policy','config','n','stream','SDK envelope','CPU post service','overlap','union'],[[r[k] for k in ['policy','config','processes','stream_seconds_mean','SDK_envelope_seconds_mean','CPU_post_service_seconds_mean','SDK_CPU_intersection_seconds_mean','SDK_CPU_union_seconds_mean']] for r in overlap_summary])
lines+=['','[逐进程原始ns/秒、FPS、分位数](E6_overlap_FPS_latency_per_process.csv) · [重叠汇总及SD](E6_overlap_per_config.csv)','',
    '`Total=t_final−t0`；包含QueueWait；`Post=t_final−t_post_start`；分位数为同配置2376帧合并linear，单位ms。','']
lines+=table(['policy','config','stage','frames','p50','p95','p99'],[[r[k] for k in ['policy','config','stage','frames','p50_ms','p95_ms','p99_ms']] for r in latency])
lines+=['','[延迟CSV](E6_latency_percentiles.csv)','',
    '| role | allowed cores | 单核固定绑定 | 迁移计数 |', '|---|---|---:|---|',
    '| inference | 0,1,2,3,4,5,6,7 | 0 | NA |','| postprocessing | 0,1,2,3,4,5,6,7 | 0 | NA |','| monitor | 0 | 1 | NA |','',
    '[角色TID/边界时间戳/last_processor](E6_thread_role_core_boundaries.csv) · [完整线程边界](E6_A_thread_boundary_schedule.csv)','',
    '## 5. Governor参数','']
lines+=table(['governor','path','parameter','value','boundary records'],[[r[k] for k in ['governor','parameter_path','parameter','value','boundary_records']] for r in param_unique])
lines+=['','[每进程每边界参数、min/max、kernel](governor_parameters_per_boundary.csv)','',
    '## 6. 来源与复算计数','']+table(['batch','processes','formal frames','new processes','new forwards'],[[r[k] for k in ['batch','processes','formal_frames','new_processes','new_forwards']] for r in ledger])
lines+=['']+table(['check','value'],list(checks.items()))
lines+=['','[来源SHA256](source_manifest.csv) · [复算脚本](extract_offline.py) · [复核数值](verification.json)','']
(OUT/'Step3_report.md').open('x',encoding='utf8').write('\n'.join(lines))

# Check every consumed immutable input after extraction; no frozen input writes.
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())
write('source_manifest.csv',[{'absolute_path':p,'sha256':h,'unchanged':1} for p,h in sorted(inputs.items())])
(OUT/'verification.json').open('x',encoding='utf8').write(json.dumps({**checks,'source_files':len(inputs),'source_hash_mismatches':0,'residency_rows':len(residency),'formal_CPU_windows':len(cpu)//2,'E2_t0_after_sleep':1,'E6_df':5},indent=2))
with (OUT/'MANIFEST_SHA256').open('x',encoding='utf8') as f:
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='MANIFEST_SHA256':f.write(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
print(json.dumps({'output':str(OUT),'new_forwards':0,'new_board_connections':0,'source_files':len(inputs),'csvs':len(list(OUT.glob('*.csv'))),'report_bytes':(OUT/'Step3_report.md').stat().st_size},ensure_ascii=False))
