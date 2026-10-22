"""Independent Decimal raw-CSV paired means, sample SDs and t intervals."""
import csv,json,sys
from decimal import Decimal,getcontext
from pathlib import Path
T=Path(__file__).resolve().parents[1];label=sys.argv[1];B=T/'evidence'/label;O=T/'reports'/label
getcontext().prec=45
load=lambda p:json.loads(p.read_text(encoding='utf8'))
A=load(O/'analysis_unrounded.json');plan=load(B/'protocol_frozen.json');design=plan['design'];n=design['n_blocks']
critical={6:'2.570581835636305',8:'2.3646242510102993',10:'2.2621571628540993',12:'2.200985160082949'}[n]
def mean(v):return sum(v)/Decimal(len(v))
def sd(v):
 m=mean(v);return (sum((x-m)**2 for x in v)/Decimal(len(v)-1)).sqrt()
checks=[]
def equal(name,a,b):
 e=abs(float(a)-float(b));assert e<1e-9,(name,str(a),b,e);checks.append({'item':name,'absolute_difference':e})
data={}
for e in plan['order']:
 p=B/'run'/f"process_{e['index']+1:02}_{e['condition']}_{e['strategy']}"/'formal.csv'
 with p.open(newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==design['frames_per_pass']*design['formal_passes']
 data[e['block'],e['condition'],e['strategy'],e.get('pacing','free')]={stage:mean([Decimal(r[stage]) for r in rows]) for stage in next(iter(A['summary'].values()))}
for name,stages in A['summary'].items():
 policy,mode,pacing=name.split('/')
 for stage,target in stages.items():
  values=[data[b,policy,mode,pacing][stage] for b in range(1,n+1)];m,s=mean(values),sd(values);h=Decimal(critical)*s/Decimal(n).sqrt()
  for field,val in [('mean',m),('sample_SD',s),('CI95_low',m-h),('CI95_high',m+h)]:equal(name+'/'+stage+'/'+field,val,target[field])
for name,stages in A['contrasts'].items():
 policy,pacing,contrast=name.split('/');left,right=contrast.split('-')
 for stage,target in stages.items():
  values=[data[b,policy,left,pacing][stage]-data[b,policy,right,pacing][stage] for b in range(1,n+1)];m,s=mean(values),sd(values);h=Decimal(critical)*s/Decimal(n).sqrt()
  for field,val in [('mean',m),('sample_SD',s),('CI95_low',m-h),('CI95_high',m+h)]:equal(name+'/'+stage+'/'+field,val,target[field])
  for i,val in enumerate(values):equal(name+'/'+stage+'/block'+str(i+1),val,target['values'][i])
  equal(name+'/'+stage+'/percent',100*m/mean([data[b,policy,left,pacing][stage] for b in range(1,n+1)]),target['relative_reduction_percent_ratio_of_means'])
  v=[100*values[i]/data[b,policy,left,pacing][stage] for i,b in enumerate(range(1,n+1))];m,s=mean(v),sd(v);h=Decimal(critical)*s/Decimal(n).sqrt();pct=target['paired_block_percent']
  for field,val in [('mean',m),('sample_SD',s),('CI95_low',m-h),('CI95_high',m+h)]:equal(name+'/'+stage+'/paired_percent/'+field,val,pct[field])
result={'status':'PASS','method':'Decimal45 from raw per-process CSV; primary analysis not imported; independent fixed t critical values; all reported process, block, SD, CI and percent estimates','checks':len(checks),'max_absolute_difference':max(x['absolute_difference'] for x in checks),'details':checks}
with (O/'independent_paired_recomputation.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='details'}))
