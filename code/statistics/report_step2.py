"""Numeric batch report, all eight paired-block values and df7 CIs."""
import csv,json,sys
from pathlib import Path
T=Path(__file__).resolve().parents[1];label=sys.argv[1];O=T/'reports'/label
a=json.loads((O/'analysis_unrounded.json').read_text());assert a['processes']==64
lines=['# '+label,'','| status | processes | formal records | forwards | blocks | df |','|---|---:|---:|---:|---:|---:|',f"| PASS | {a['processes']} | {a['formal_rows']} | {a['actual_forwards']} | 8 | 7 |",'',
 '| policy | config | Pre mean±SD ms | SDK mean±SD ms | Post mean±SD ms | Restore mean±SD ms | Total mean±SD ms |','|---|---|---:|---:|---:|---:|---:|']
for policy in ['D','L']:
 for mode in ['M6','R','F','S2']:
  s=a['summary'][policy+'/'+mode+'/free']
  values=[f"{s[k]['mean']:.9f}±{s[k]['sample_SD']:.9f}" for k in ['Pre_ms','SDK_ms','Post_ms','RestoreGather_ms','Total_ms']]
  lines.append('| '+policy+' | '+mode+' | '+' | '.join(values)+' |')
lines+=['','| policy | left−right | stage | mean ms | sample SD ms | CI95 low | CI95 high | df | eight raw block differences ms |','|---|---|---|---:|---:|---:|---:|---:|---|']
for name,stages in a['contrasts'].items():
 for stage in ['Total_ms','Post_ms']:
  z=stages[stage];assert len(z['values'])==8
  lines.append('| '+name.split('/')[0]+' | '+name.split('/')[-1]+' | '+stage+' | '+' | '.join(f"{z[k]:.9f}" for k in ['mean','sample_SD','CI95_low','CI95_high'])+' | 7 | '+', '.join(f'{v:.12f}' for v in z['values'])+' |')
lines+=['','[frames.csv](frames.csv) · [process_summary.csv](process_summary.csv) · [paired_blocks.csv](paired_blocks.csv) · [paired_summary.csv](paired_summary.csv) · [frequency_residency_per_core.csv](frequency_residency_per_core.csv)','']
(O/'batch_report.md').open('x',encoding='utf8').write('\n'.join(lines))
print(json.dumps({'batch':label,'status':'PASS','df':7}))
