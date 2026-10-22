"""Offline CSV-only reconstruction. Does not import SDKs or execute models.
Run from any directory: python analysis/make_tables.py
Outputs are derived files; source CSVs are never written.
"""
import argparse,csv,hashlib,json,math,re,statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import t

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'analysis/output');args=parser.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
INPUTS={};CHECKS=[];DIFFS=[]
def read(p):
 p=Path(p);INPUTS[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
 if not rows:return
 with (OUT/name).open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def group(rows,keys):
 d=defaultdict(list)
 for r in rows:d[tuple(r[k] for k in keys)].append(r)
 return sorted(d.items())
def mean(xs):return statistics.mean(xs)
def summary(values):
 n=len(values);m=mean(values);s=statistics.stdev(values);h=float(t.ppf(.975,n-1))*s/math.sqrt(n)
 return dict(n=n,df=n-1,mean=m,sample_SD=s,CI95_low=m-h,CI95_high=m+h)
def check(name,a,b,tol=1e-9,scope='archive'):
 d=abs(float(a)-float(b));ok=d<=tol
 row={'scope':scope,'item':name,'recomputed':a,'reference':b,'absolute_difference':d,'tolerance':tol,'equal':int(ok)}
 CHECKS.append(row)
 if not ok:DIFFS.append(row)

STAGE={'Pre_ms':'pre_ms','SDK_ms':'sdk_ms','Post_ms':'post_ms','Total_ms':'total_ms','OutputAccess_ms':'output_access_ms','Select_ms':'select_ms','RestoreGather_ms':'restore_ms','DFLCoordinates_ms':'dfl_coord_ms','NMSAssemble_ms':'nms_assemble_ms','QueueWait_ms':'queue_wait_ms'}
BATCHES=['Step2_A','Step2_B_recovery08','Step2_C_full08','E1_A_v2','E1_B_v2','E2_A_v2','E3_A','E3_B','E3_C','E4_A_FSS2_12','E4_B_FSS2_12','E4_C_FSS2_12','E5_A','E6_A']
PROCS={};SAVED={};FRAMEQ={};count_frames={}
for label in BATCHES:
 src=read(DATA/label/'process_summary.csv');SAVED[label]=src;byid={r['process_id']:r for r in src}
 frames=read(DATA/label/'frames.csv');count_frames[label]=len(frames)
 buckets=defaultdict(lambda:defaultdict(list));seen=set();q=defaultdict(list)
 for r in frames:
  key=(r['process_id'],r['pass'],r['frame']);assert key not in seen;seen.add(key)
  p=byid[r['process_id']]
  assert all(r[k]==p[k] for k in ['video','config','policy','block','position'])
  for s,c in STAGE.items():
   if c in r:buckets[r['process_id']][s].append(float(r[c]))
  q[r['policy'],r['config'],r['pacing']].append(float(r['total_ms']))
 rows=[]
 for pid,stages in buckets.items():
  p=byid[pid];m={k:p[k] for k in ['batch','video','config','policy','pacing','block','position','process_id']}
  for s,v in stages.items():
   m[s]=math.fsum(v)/len(v)
   if s in p:check(label+'/'+pid+'/'+s,m[s],p[s],1e-10)
   else:assert s=='QueueWait_ms' and m[s]==0
  m['formal_frames']=len(stages['Total_ms']);rows.append(m)
 PROCS[label]=rows;FRAMEQ[label]=q
 del frames,buckets
print('reconstructed',len(PROCS),'batches',flush=True)

def config_table(label,stages):
 out=[]
 for key,rows in group(PROCS[label],['batch','video','policy','config','pacing']):
  for stage in stages:
   out.append(dict(zip(['batch','video','policy','config','pacing'],key),stage=stage,**summary([r[stage] for r in rows])))
 return out
def pairs(label,pairs,stages):
 out=[]
 for policy,pacing in sorted({(r['policy'],r['pacing']) for r in PROCS[label]}):
  for left,right in pairs:
   a={int(r['block']):r for r in PROCS[label] if (r['policy'],r['pacing'],r['config'])==(policy,pacing,left)}
   b={int(r['block']):r for r in PROCS[label] if (r['policy'],r['pacing'],r['config'])==(policy,pacing,right)}
   if not a or not b:continue
   assert set(a)==set(b)
   for stage in stages:
    values=[a[k][stage]-b[k][stage] for k in sorted(a)];z=summary(values)
    out.append(dict(batch=label,video=next(iter(a.values()))['video'],policy=policy,pacing=pacing,contrast=left+'->'+right,stage=stage,**z,relative_reduction_percent_ratio_of_means=100*z['mean']/mean(r[stage] for r in a.values()),raw_block_differences=json.dumps(values)))
 return out
main=['Step2_A','Step2_B_recovery08','Step2_C_full08']
write('table4_Total.csv',[r for b in main for r in config_table(b,['Total_ms'])])
write('table5_paired_differences.csv',[r for b in main for r in pairs(b,[('R','F'),('F','S2'),('R','S2'),('M6','S2')],['Total_ms','Post_ms'])])
write('table6_A_fixed1500_stages.csv',[r for r in config_table(main[0],list(STAGE)[:-1]) if r['policy']=='L'])
write('table7_configuration_decomposition.csv',[r for b in ['E3_A','E3_B','E3_C'] for r in pairs(b,[('M6','CID_MAX'),('CID_MAX','CID_INDEX'),('CID_INDEX','R')],['Total_ms','SDK_ms','Post_ms','Select_ms','RestoreGather_ms'])])
write('table8_candidate_recovery.csv',[r for b in ['E4_A_FSS2_12','E4_B_FSS2_12','E4_C_FSS2_12'] for r in pairs(b,[('F','S'),('F','S2')],['Total_ms','Post_ms','RestoreGather_ms'])])
write('table9_A_frequency_sweep.csv',config_table('E1_A_v2',['Pre_ms','SDK_ms','Post_ms','Total_ms']))

# Verify every reconstructed configuration mean and CI against its own batch CSV.
for b in BATCHES:
 for row in read(DATA/b/'configuration_summary.csv'):
  key=(row['policy'],row['config'],row.get('pacing','free'))
  vals=[r[row['stage']] for r in PROCS[b] if (r['policy'],r['config'],r['pacing'])==key]
  z=summary(vals)
  for f in ['mean','sample_SD','CI95_low','CI95_high']:check(b+'/configuration/'+str(key)+'/'+row['stage']+'/'+f,z[f],row[f])
 paired=read(DATA/b/'paired_summary.csv')
 for row in paired:
  left,right=row['contrast'].split('-',1)
  found=pairs(b,[(left,right)],[row['stage']])
  z=next(r for r in found if r['policy']==row['policy'] and r['pacing']==row.get('pacing','free'))
  for f in ['mean','sample_SD','CI95_low','CI95_high']:
   check(b+'/paired/'+row['policy']+'/'+row['contrast']+'/'+row['stage']+'/'+f,z[f],row[f])

# Precision/recall CSVs were exported losslessly from the archived COCOeval tensors.
# No annotation files, images, model inference, or evaluator execution is needed here.
precision=read(DATA/'Step1/coco_precision.csv');recall=read(DATA/'Step1/coco_recall.csv')
def tensor_mean(rows,predicate):
 values=[float(r['value']) for r in rows if predicate(r) and float(r['value'])>-1]
 return float(np.mean(np.asarray(values,dtype=np.float64)))
ap=tensor_mean(precision,lambda r:r['area']=='0' and r['maxdet']=='2')
ap50=tensor_mean(precision,lambda r:r['iou']=='0' and r['area']=='0' and r['maxdet']=='2')
ap75=tensor_mean(precision,lambda r:r['iou']=='5' and r['area']=='0' and r['maxdet']=='2')
ar=tensor_mean(recall,lambda r:r['area']=='0' and r['maxdet']=='2')
accuracy=[]
for r in read(DATA/'Step1/metrics.csv'):
 z={'batch':'Step1','config':r['config'],'images':int(r['images']),'predictions':int(r['predictions']),'AP':ap,'AP50':ap50,'AP75':ap75,'AR100':ar}
 for f in ['AP','AP50','AP75','AR100']:check('Step1/'+r['config']+'/'+f,z[f],r[f],1e-14)
 accuracy.append(z)
write('table3_accuracy.csv',accuracy)
del precision,recall

# Frequency: shared policy0 counts mapped to each core, not eight independent counters.
rf=[]
for batch in BATCHES:
 byid={r['process_id']:r for r in SAVED[batch]}
 for r in read(DATA/batch/'frequency_residency_per_core.csv'):
  # Historical exporter wrote a cpufreq path in policy; restore condition via PID join.
  r['policy']=byid[r['process_id']]['policy'];rf.append(r)
freq=[]
for key,rows in group([r for r in rf if r['phase']=='formal'],['batch','policy','config','pacing','core']):
 counts=[int(r['raw_USER_HZ_delta']) for r in rows];den=sum(counts)
 value=sum(float(r['frequency_MHz'])*int(r['raw_USER_HZ_delta']) for r in rows)/den
 freq.append(dict(zip(['batch','policy','config','pacing','core'],key),time_weighted_mean_MHz=value,residency_seconds=den/100,independent_per_core_counter=0))
write('text_frequency.csv',freq)
cpu=[];cp=[]
for batch,rows in SAVED.items():
 for r in rows:
  for window,prefix in [('formal','formal_'),('whole_reaped_process','process_')]:
   cpu.append({**{k:r[k] for k in ['batch','policy','config','pacing']},'window':window,**{k:r[prefix+k] for k in ['user_seconds','sys_seconds','wall_seconds']}})
for key,rows in group(cpu,['batch','policy','config','pacing','window']):
 u=sum(float(r['user_seconds']) for r in rows);s=sum(float(r['sys_seconds']) for r in rows);w=sum(float(r['wall_seconds']) for r in rows)
 cp.append(dict(zip(['batch','policy','config','pacing','window'],key),processes=len(rows),user_seconds=u,sys_seconds=s,wall_seconds=w,CPU_ratio=(u+s)/w,CPU_percent=100*(u+s)/w))
write('text_CPU_utilization.csv',cp)
tails=[]
for b in ['E1_A_v2','E1_B_v2']:
 for (policy,config,pacing),values in sorted(FRAMEQ[b].items()):
  if policy in ['D','O']:
   qq=np.percentile(values,[50,95,99],method='linear')
   tails.append(dict(batch=b,policy=policy,config=config,frames=len(values),p50_ms=float(qq[0]),p95_ms=float(qq[1]),p99_ms=float(qq[2])))
write('text_E1_percentiles.csv',tails)
write('text_E2_R_to_F.csv',pairs('E2_A_v2',[('R','F')],['Total_ms','Post_ms','SDK_ms']))
write('text_E2_frequency.csv',[r for r in freq if r['batch']=='E2_A_v2'])

e6=read(DATA/'Step3/E6_overlap_FPS_latency_per_process.csv');fps=[];fpsci=[];overlap=[];latency=[]
for r in e6:
 check('E6/FPS/'+r['process_id'],int(r['formal_frames'])*1e9/int(r['stream_ns']),r['FPS'],1e-10)
for key,rows in group(e6,['policy','config']):
 fps.append(dict(zip(['policy','config'],key),**summary([float(r['FPS']) for r in rows])))
 vals=[100*int(r['SDK_envelope_ns'])/int(r['stream_ns']) for r in rows]
 overlap.append(dict(zip(['policy','config'],key),SDK_envelope_seconds_mean=mean(int(r['SDK_envelope_ns'])/1e9 for r in rows),CPU_post_service_seconds_mean=mean(int(r['CPU_post_service_ns'])/1e9 for r in rows),SDK_CPU_overlap_seconds_mean=mean(int(r['SDK_CPU_intersection_ns'])/1e9 for r in rows),SDK_envelope_percent_stream_mean=mean(vals),SDK_envelope_percent_stream_sample_SD=statistics.stdev(vals),SDK_envelope_percent_stream_pooled=100*sum(int(r['SDK_envelope_ns']) for r in rows)/sum(int(r['stream_ns']) for r in rows)))
for policy in ['D','L']:
 for left,right in [('M6','R'),('R','F'),('M6','F')]:
  a={int(r['block']):float(r['FPS']) for r in e6 if r['policy']==policy and r['config']==left};b={int(r['block']):float(r['FPS']) for r in e6 if r['policy']==policy and r['config']==right}
  vals=[b[k]-a[k] for k in sorted(a)]
  fpsci.append(dict(policy=policy,contrast=left+'->'+right,sign='FPS_right_minus_left',**summary(vals),raw_block_differences=json.dumps(vals)))
for key,values in sorted(FRAMEQ['E6_A'].items()):
 qq=np.percentile(values,[50,95,99],method='linear')
 latency.append(dict(zip(['policy','config','pacing'],key),frames=len(values),p50_ms=float(qq[0]),p95_ms=float(qq[1]),p99_ms=float(qq[2])))
write('table10_pipeline_FPS.csv',fps);write('table10_pipeline_latency.csv',latency);write('text_E6_FPS_paired_CI.csv',fpsci);write('text_E6_overlap.csv',overlap)

# Rev13's actual seven tables are a different historical design. Verify them
# against their own frozen CSV batch, never against the new Step2 batch.
paper=read(DATA/'paper_reference/rev13_tables.csv');cells={(int(r['table']),int(r['row']),int(r['column'])):r['text'] for r in paper}
def paper_number(table,row,col,value,part=0):
 raw=cells[table,row,col].replace('−','-').replace('+','')
 pieces=raw.split('±');s=pieces[part].rstrip('%');ref=float(s);decimals=len(s.split('.')[1]) if '.' in s else 0
 check(f'Rev13/table{table}/row{row}/column{col}/part{part}',value,ref,.5*10**(-decimals)+1e-12,'Rev13')
historical=read(DATA/'reference_rev13/COCO/metrics.csv')
for i,mode in enumerate(['M6','R','F'],1):
 r=next(r for r in historical if r['mode']==mode)
 for j,f in enumerate(['AP','AP50','AP75','AR100'],1):paper_number(3,i,j,float(r[f]))
dv=read(DATA/'reference_rev13/DVFS/process_means.csv')
for i,(policy,mode) in enumerate([('D','R'),('D','F'),('L','R'),('L','F')],1):
 own=[r for r in dv if r['condition']==policy and r['strategy']==mode]
 for j,f in enumerate(['SDK_ms','Post_ms','Total_ms'],2):
  values=[float(r[f]) for r in own];paper_number(4,i,j,mean(values));paper_number(4,i,j,statistics.stdev(values),1)
historical_rows={}
for video in ['A','B','C']:
 rows=read(DATA/f'reference_rev13/{video}/formal_process_summary.csv');historical_rows[video]=rows
 for ip,policy in enumerate(['D','L']):
  row=1+2*(['A','B','C'].index(video))+ip
  means={}
  for col,mode in enumerate(['M6','R','F'],2):
   values=[float(r['Total_ms']) for r in rows if r['condition']==policy and r['strategy']==mode]
   means[mode]=mean(values);paper_number(6,row,col,means[mode]);paper_number(6,row,col,statistics.stdev(values),1)
  paper_number(6,row,5,100*(means['M6']-means['F'])/means['M6'])
  for col,(a,b) in enumerate([('M6','R'),('R','F'),('M6','F')],2):paper_number(7,row,col,means[a]-means[b])
p1={}
for mode,rows in group(read(DATA/'reference_rev13/P1/process_means.csv'),['config']):p1[mode[0]]=rows
for i,mode in enumerate(['R','F','S'],1):
 for j,f in enumerate(['SDK_ms','Post_ms','RestoreGather_ms','Total_ms'],1):paper_number(5,i,j,mean(float(r[f]) for r in p1[mode]))

write('comparison_checks.csv',CHECKS)
mapping=[{'requested_table':i,'source':'Step1' if i==3 else 'Step2' if i in [4,5,6] else 'E3' if i==7 else 'E4' if i==8 else 'E1' if i==9 else 'E6','Rev13_corresponding_table':3 if i==3 else 'NONE','status':'SCOPE_DIFFERS: Step1 has R/F/S/S2; Rev13 has earlier M6/R/F' if i==3 else 'NOT_IN_REV13; Rev13 has seven tables from older batches'} for i in range(3,11)]
write('paper_table_mapping.csv',mapping)
issue=['# differences','',f'数值差异：{len(DIFFS)}。','', '版本/范围差异：所提供Rev13共7表；其表4—表7来自旧六区组等批次。请求的新表4—表10分别来自Step2/E3/E4/E1/E6，不能按表号直接比较。Rev13表3含M6，Step1未运行M6；M6历史指标另存reference_rev13，未混入Step1。','']
if DIFFS:
 issue+=['|scope|item|recomputed|reference|difference|','|---|---|---:|---:|---:|']+[f"|{r['scope']}|{r['item']}|{r['recomputed']}|{r['reference']}|{r['absolute_difference']}|" for r in DIFFS]
else:issue+=['对同批归档CSV和Rev13已有表3—表7的可对应数值：无差异。']
(OUT/'differences.md').write_text('\n'.join(issue)+'\n',encoding='utf8')
result={'new_board_runs':0,'source_CSVs':len(INPUTS),'batches':len(BATCHES),'selected_main_processes':sum(len(PROCS[b]) for b in main),'selected_main_formal_frames':sum(count_frames[b] for b in main),'excluded_B_processes_used':0,'checked_numeric_fields':len(CHECKS),'numeric_mismatches':len(DIFFS),'Rev13_checked_fields':sum(r['scope']=='Rev13' for r in CHECKS),'paper_requested_table_mapping':'SCOPE_DIFFERENCE','CI':'paired block two-sided Student t; df=n-1','percentile':'numpy linear pooled formal frames; no frame-level inference','input_sha256':INPUTS}
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in INPUTS.items())
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='input_sha256'},ensure_ascii=False))
