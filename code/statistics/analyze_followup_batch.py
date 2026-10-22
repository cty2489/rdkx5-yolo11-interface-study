"""Raw-frame reconstruction, paired process statistics and CPU accounting."""
import csv,hashlib,json,math,statistics,sys
from collections import defaultdict
from decimal import Decimal,getcontext
from pathlib import Path
import numpy as np
from scipy.stats import t as student
T=Path(__file__).resolve().parents[1];label=sys.argv[1];B=T/'evidence'/label;O=T/'reports'/label;O.mkdir()
getcontext().prec=45
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(n,d):
 with (O/n).open('x',encoding='utf8') as f:json.dump(d,f,indent=2,allow_nan=False)
def write(n,rows):
 with (O/n).open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summary(values):
 n=len(values);m=statistics.mean(values);s=statistics.stdev(values);h=float(student.ppf(.975,n-1))*s/math.sqrt(n)
 return {'n_processes_or_paired_blocks':n,'mean':m,'sample_SD':s,'CI95_low':m-h,'CI95_high':m+h,'values':values,'positive':sum(v>0 for v in values),'negative':sum(v<0 for v in values)}
def delta_cpu(a,b):
 parse=lambda text:{r[0]:list(map(int,r[1:])) for line in text.splitlines() if (r:=line.split()) and (r[0]=='cpu' or r[0].startswith('cpu') and r[0][3:].isdigit())}
 aa,bb=parse(a['proc_stat_raw']),parse(b['proc_stat_raw']);out=[]
 for core,first in aa.items():
  v=[y-x for x,y in zip(first,bb[core])];assert all(x>=0 for x in v)
  total=sum(v[:8]);idle=sum(v[3:5]);out.append({'core':core,'total_ticks':total,'busy_ticks':total-idle,'utilization_percent':100*(total-idle)/total if total else 0,'raw_tick_delta':json.dumps(v)})
 return out
def residency(a,b,meta,phase,pass_id):
 rows=[]
 for policy,start in a['policies'].items():
  first={int(k):int(v) for k,v in map(str.split,start['time_in_state_raw'].splitlines())};end=b['policies'][policy];last={int(k):int(v) for k,v in map(str.split,end['time_in_state_raw'].splitlines())}
  assert start['related_cpus']==end['related_cpus']
  for freq,ticks in first.items():
   amount=last[freq]-ticks;assert amount>=0
   for core in start['related_cpus']:rows.append({**meta,'phase':phase,'pass':pass_id,'core':core,'policy':policy,'frequency_MHz':freq/1000,'residency_seconds':amount*.01,'raw_USER_HZ_delta':amount,'shared_policy_mapping':True,'independent_per_core_counter':False})
 return rows
plan=load(B/'protocol_frozen.json');design=plan['design'];state=load(B/'reports/batch_state.json');assert state['status']=='COMPLETE_STOP' and state['completed_processes']==len(plan['order'])
assert load(B/'reports/independent_recovery_verification.json')['status']=='VERIFIED'
N=design['frames_per_pass'];PASSES=design['formal_passes'];video=design['video'];batch_processes={p['index']:p for p in state['processes']}
stages=['Pre_ms','SDK_ms','Post_ms','Total_ms','OutputAccess_ms','Select_ms','RestoreGather_ms','DFLCoordinates_ms','NMSAssemble_ms']
if design.get('pipeline'):stages.append('QueueWait_ms')
normalized=[];processes=[];passrows=[];resident=[];cpu=[];decimal_checks=[];raw_rows={}
for entry in plan['order']:
 i=entry['index'];policy=entry['condition'];mode=entry['strategy'];folder=B/'run'/f'process_{i+1:02}_{policy}_{mode}'
 receipt=load(folder/'state.json');assert receipt['status']=='COMPLETE' and receipt['NUMERIC_GUARD']=='PASS'
 assert receipt['forward_completions']==receipt['forward_attempts']==N*(PASSES+1) and receipt['formal_records']==N*PASSES
 assert sha(folder/'formal.csv')==receipt['csv_sha256']
 with (folder/'formal.csv').open(newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==N*PASSES and len({(r['pass'],r['frame']) for r in rows})==N*PASSES
 meta={'batch':label,'video':video,'config':mode,'policy':policy,'block':entry['block'],'position':entry['position'],'process_id':receipt['pid'],'process_index':i+1,'pacing':entry.get('pacing','free')}
 means={s:statistics.mean(float(r[s]) for r in rows) for s in stages}
 for stage in stages:
  exact=sum(Decimal(r[stage]) for r in rows)/Decimal(len(rows));err=abs(float(exact)-means[stage]);assert err<1e-10;decimal_checks.append(err)
 for r in rows:
  ticks=[int(r[k]) for k in ['t0_ns','t_read_ns','t_prepare_ns','t_forward_ns','t_outputs_ns','t_final_ns']];assert ticks==sorted(ticks)
  assert abs(float(r['Total_ms'])-(ticks[-1]-ticks[0])/1e6)<1e-10
  assert abs(float(r['Total_ms'])-sum(float(r[k]) for k in ['Pre_ms','SDK_ms','Post_ms'])-float(r.get('QueueWait_ms',0)))<1e-10
  normalized.append({**meta,'pass':int(r['pass']),'frame':int(r['frame']),'pre_ms':r['Pre_ms'],'sdk_ms':r['SDK_ms'],'post_ms':r['Post_ms'],'total_ms':r['Total_ms'],'restore_ms':r['RestoreGather_ms'],
   'output_access_ms':r['OutputAccess_ms'],'select_ms':r['Select_ms'],'dfl_coord_ms':r['DFLCoordinates_ms'],'nms_assemble_ms':r['NMSAssemble_ms'],'K':int(r['candidates']),'detections':int(r['detections']),
   'full_float_bbox_elements':int(r['full_float_bbox_elements']),'selected_integer_bbox_elements':int(r['selected_integer_bbox_elements']),
   'pacing_wait_ns':int(r.get('pacing_wait_ns',0)),'release_target_ns':int(r.get('release_target_ns',0)),'start_lateness_ns':int(r.get('start_lateness_ns',0)),'arrival_to_result_ms':r.get('arrival_to_result_ms',r['Total_ms']),
   'queue_wait_ms':r.get('QueueWait_ms',0),'slot':r.get('slot',''),'post_start_ns':r.get('t_post_start_ns',r['t_forward_ns']),'t0_ns':ticks[0],'t_final_ns':ticks[-1]})
 account=load(folder/'accounting.json');begin,end=account['formal_begin'],account['formal_end'];whole=batch_processes[i]['process_CPU_time'];formal_user=end['user_seconds']-begin['user_seconds'];formal_sys=end['sys_seconds']-begin['sys_seconds'];wall=(end['monotonic_ns']-begin['monotonic_ns'])/1e9
 p={**meta,**means,'K_mean':statistics.mean(int(r['candidates']) for r in rows),'process_user_seconds':whole['user_seconds'],'process_sys_seconds':whole['sys_seconds'],'process_wall_seconds':whole['wall_seconds'],
  'formal_user_seconds':formal_user,'formal_sys_seconds':formal_sys,'formal_wall_seconds':wall,'formal_process_CPU_one_core_percent':100*(formal_user+formal_sys)/wall,'formal_achieved_FPS':len(rows)/wall,
  **{'Total_P'+str(q)+'_ms':float(np.percentile([float(r['Total_ms']) for r in rows],q)) for q in [50,95,99]}}
 processes.append(p);raw_rows[i]=rows
 resident.extend(residency(begin,end,meta,'formal',0));cpu.extend({**meta,'phase':'formal','pass':0,**x} for x in delta_cpu(begin,end))
 for pass_id in range(1,PASSES+1):
  own=[r for r in rows if int(r['pass'])==pass_id];z={**meta,'pass':pass_id,**{s:statistics.mean(float(r[s]) for r in own) for s in stages}}
  if account['per_pass']:
   pair=account['per_pass'][pass_id-1];assert pair['pass']==pass_id
   a,b=pair['before'],pair['after'];z.update(pass_wall_seconds=(b['monotonic_ns']-a['monotonic_ns'])/1e9,pass_user_seconds=b['user_seconds']-a['user_seconds'],pass_sys_seconds=b['sys_seconds']-a['sys_seconds'])
   resident.extend(residency(a,b,meta,'per_pass',pass_id));cpu.extend({**meta,'phase':'per_pass','pass':pass_id,**x} for x in delta_cpu(a,b))
  passrows.append(z)
assert len(normalized)==design['formal_records']
write('frames.csv',normalized);write('process_summary.csv',processes);write('pass_summary.csv',passrows);write('frequency_residency_per_core.csv',resident);write('CPU_utilization.csv',cpu)
groups=defaultdict(list)
for p in processes:groups[(p['policy'],p['config'],p['pacing'])].append(p)
summaries={};flat=[]
for key,own in groups.items():
 name='/'.join(key);summaries[name]={s:summary([p[s] for p in own]) for s in stages}
 for s in stages:flat.append({'batch':label,'video':video,'policy':key[0],'config':key[1],'pacing':key[2],'stage':s,**{k:v for k,v in summaries[name][s].items() if k not in ['values','positive','negative']}})
write('configuration_summary.csv',flat)
modes={p['config'] for p in processes};comparisons=[('R','F')] if modes=={'R','F'} else [('F','S')]+([('F','S2'),('S','S2')] if 'S2' in modes else []) if modes.issubset({'F','S','S2'}) else [('M6','CID_MAX'),('CID_MAX','CID_INDEX'),('CID_INDEX','R'),('R','F'),('M6','R'),('M6','F')]
if modes=={'M6','R','F'}:comparisons=[('M6','R'),('R','F'),('M6','F')]
contrasts={};paired=[];summary_flat=[]
for policy in sorted({p['policy'] for p in processes}):
 for pacing in sorted({p['pacing'] for p in processes}):
  for left,right in comparisons:
   aa={p['block']:p for p in processes if (p['policy'],p['config'],p['pacing'])==(policy,left,pacing)};bb={p['block']:p for p in processes if (p['policy'],p['config'],p['pacing'])==(policy,right,pacing)}
   assert set(aa)==set(bb) and len(aa)==design['n_blocks']
   name='/'.join([policy,pacing,left+'-'+right]);contrasts[name]={}
   for stage in stages:
    values=[aa[b][stage]-bb[b][stage] for b in sorted(aa)];z=summary(values);z['relative_reduction_percent_ratio_of_means']=100*z['mean']/statistics.mean(aa[b][stage] for b in aa)
    z['paired_block_percent']=summary([100*(aa[b][stage]-bb[b][stage])/aa[b][stage] for b in sorted(aa)])
    contrasts[name][stage]=z
    summary_flat.append({'batch':label,'video':video,'policy':policy,'pacing':pacing,'contrast':left+'-'+right,'stage':stage,**{k:v for k,v in z.items() if k not in ['values','paired_block_percent']}})
    for block,value in zip(sorted(aa),values):paired.append({'batch':label,'video':video,'policy':policy,'pacing':pacing,'block':block,'left':left,'right':right,'stage':stage,'left_ms':aa[block][stage],'right_ms':bb[block][stage],'difference_ms':value,'percent':100*value/aa[block][stage]})
write('paired_blocks.csv',paired);write('paired_summary.csv',summary_flat)
save('analysis_unrounded.json',{'status':'COMPLETE','source_protocol_sha256':sha(B/'protocol_frozen.json'),'design_sha256':sha(B/'inputs/design_frozen.json'),'processes':len(processes),'formal_rows':len(normalized),'actual_forwards':sum(load(B/'run'/f"process_{e['index']+1:02}_{e['condition']}_{e['strategy']}"/'state.json')['forward_completions'] for e in plan['order']),
 'summary':summaries,'contrasts':contrasts,'statistical_unit':'independent process mean within paired block; no cross-batch pooling','CI_method':'two-sided Student t with n_blocks-1 df','tail_method':'linear percentile within each process; no independent-frame inference','per_core_frequency_note':'all related cores share a policy; identical mapped rows are not independent observations'})
save('independent_Decimal_recomputation.json',{'status':'PASS','method':'Decimal45 process means directly from raw CSV, separately from statistics.mean','checks':len(decimal_checks),'max_abs_difference':max(decimal_checks)})
print(json.dumps({'status':'COMPLETE','batch':label,'processes':len(processes),'formal_rows':len(normalized),'contrasts_Total':{k:v['Total_ms'] for k,v in contrasts.items()}},indent=2))
