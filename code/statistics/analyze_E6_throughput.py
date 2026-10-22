"""Measured pipeline FPS is not reciprocal mean latency."""
import csv,json,math,statistics
from pathlib import Path
from scipy.stats import t
T=Path(__file__).resolve().parents[1];B=T/'evidence/E6_A';O=T/'reports/E6_A'
plan=json.loads((B/'protocol_frozen.json').read_text());rows=[]
for e in plan['order']:
 folder=B/'run'/f"process_{e['index']+1:02}_{e['condition']}_{e['strategy']}"
 throughput=json.loads((folder/'pipeline_throughput.json').read_text());state=json.loads((folder/'state.json').read_text())
 rows.append({'block':e['block'],'position':e['position'],'policy':e['condition'],'config':e['strategy'],'process_id':state['pid'],'measured_FPS':throughput['measured_FPS'],'stream_seconds':throughput['stream_seconds'],
 'SDK_CPU_post_envelope_overlap_seconds':throughput['SDK_interval_CPU_post_service_overlap_seconds'],'contexts':throughput['contexts']})
def stat(v):
 m=statistics.mean(v);s=statistics.stdev(v);h=t.ppf(.975,len(v)-1)*s/math.sqrt(len(v));return {'n':len(v),'mean':m,'sample_SD':s,'CI95_low':m-h,'CI95_high':m+h}
def write(n,rr):
 with (O/n).open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
write('measured_pipeline_FPS_by_process.csv',rows)
summary=[];paired=[];by={(r['block'],r['policy'],r['config']):r for r in rows}
for policy in ['D','L']:
 for m in ['M6','R','F']:summary.append({'policy':policy,'config':m,**stat([r['measured_FPS'] for r in rows if r['policy']==policy and r['config']==m])})
 for a,b in [('M6','R'),('R','F'),('M6','F')]:
  v=[by[i,policy,a]['measured_FPS']-by[i,policy,b]['measured_FPS'] for i in range(1,7)];paired.append({'policy':policy,'FPS_contrast':a+'-'+b,**stat(v),'raw_block_values':json.dumps(v),'direction':'positive means LEFT has higher throughput'})
write('pipeline_FPS_configuration_summary.csv',summary);write('pipeline_FPS_paired_contrasts.csv',paired)
with (O/'pipeline_interpretation.json').open('x') as f:json.dump({'FPS_measured_from_stream_interval':True,'FPS_not_1000_over_mean_latency':True,'per_frame_Total_is_latency_including_queue_wait':True,'Post_is_CPU_service_only':True,'overlap_scope':'external SDK envelope vs CPU post service, not pure BPU hardware time','prototype':'two independently loaded same-BIN SDK contexts, two Python role threads, bounded2-slot queue, unchanged C library and consumer'},f,indent=2)
print(json.dumps({'E6_pipeline_FPS':summary,'paired_FPS':paired}))
