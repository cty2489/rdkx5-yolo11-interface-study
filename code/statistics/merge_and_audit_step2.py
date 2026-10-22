"""Compile derived batch views; every copied raw payload remains byte-identical."""
import hashlib,json,shutil,sys
from pathlib import Path
T=Path(__file__).resolve().parents[1];video=sys.argv[1];label='Step2_'+video
E=T/'evidence';B=E/label;B.mkdir()
load=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
save=lambda p,d:p.open('x',encoding='utf8').write(json.dumps(d,indent=2))
root=E/'campaign';selection=load(root/'batches'/label/'reports/selected_attempts.json')
order=load(root/'batches'/label/'order_frozen.json');sources=[];all_processes=[];monitors=[];plan=None
(B/'run').mkdir();(B/'reports').mkdir();(B/'inputs').mkdir()
for selected in selection:
 J=E/'jobs'/selected['selected_job'];state=load(J/'reports/batch_state.json')
 assert state['status']=='COMPLETE_STOP' and not state['failures'] and state['completed_processes']==8 and state['restoration']=='VERIFIED'
 if plan is None:plan=load(J/'protocol_frozen.json');shutil.copytree(J/'capture',B/'capture')
 mon=load(J/'reports/formal_monitor_samples.json')
 for local,e in enumerate(order[(selected['block']-1)*8:selected['block']*8]):
  assert e['block']==selected['block'];i=e['index'];p=state['processes'][local];assert p['index']==local and p['block']==e['block']
  d=J/'run'/f"process_{local+1:02}_{e['condition']}_{e['strategy']}";target=B/'run'/f"process_{i+1:02}_{e['condition']}_{e['strategy']}"
  shutil.copytree(d,target)
  for f in d.iterdir():
   if f.is_file():assert sha(f)==sha(target/f.name)
  all_processes.append({**p,'index':i,'source_job':selected['selected_job'],'local_index':local})
  source_state=load(d/'state.json');assert source_state['NUMERIC_GUARD']=='PASS'
  assert p['runtime_monitor']['budget_pass'] and p['runtime_monitor']['one_core_cpu_percent']<=.5
  samples=[s for s in mon if s['label']==d.name and s['phase']=='formal']
  assert samples
  temperatures=[v/1000 for s in samples for k,v in s['values'].items() if k.endswith('/temp')]
  assert max(temperatures)<80 and all(v==0 for s in samples for k,v in s['values'].items() if k.endswith('/cur_state'))
  if e['condition']=='L':assert all(v==1500000 for s in samples for k,v in s['values'].items() if k.endswith('/cpuinfo_cur_freq'))
  residency=load(J/'reports'/f'residency_check_{local+1:02}.json')
  if e['condition']=='L':
   for x in residency['policies'].values():assert x['available'] and all(int(k)==1500000 or v==0 for k,v in x['raw_counter_delta'].items())
  sources.append({'global_index':i,'block':e['block'],'position':e['position'],'strategy':e['strategy'],'condition':e['condition'],'selected_job':selected['selected_job'],'local_index':local,'raw_CSV':str((d/'formal.csv').relative_to(T)),'raw_CSV_sha256':sha(d/'formal.csv'),'pid':p['pid'],'forwards':source_state['forward_completions'],'formal_records':source_state['formal_records'],'model_loads':source_state['model_loads']})
  monitors.append({'global_index':i,'monitor_CPU_percent':p['runtime_monitor']['one_core_cpu_percent'],'temperature_min_C':min(temperatures),'temperature_max_C':max(temperatures),'thermal_events':0})
N=plan['design']['frames_per_pass'];design={**plan['design'],'order':order,'n_blocks':8,'formal_processes':64,'formal_records':64*3*N,'warmup_forwards':64*N,'max_forwards':64*4*N,'t_critical':2.3646242510102993}
plan.update(order=order,design=design,max_processes=64,max_forwards=64*4*N,formal_records=64*3*N,derived_batch_view=True)
save(B/'protocol_frozen.json',plan);save(B/'inputs/design_frozen.json',design)
save(B/'reports/batch_state.json',{'status':'COMPLETE_STOP','completed_processes':64,'processes':all_processes,'failures':[],'derived_from_selected_complete_blocks':True})
assert load(root/'reports/phase_timing_state.json')['restoration']=='VERIFIED'
save(B/'reports/independent_recovery_verification.json',{'status':'VERIFIED','source_phase_receipt':str((root/'reports/phase_timing_state.json').relative_to(T)),'source_individual_restorations':'selected per-block controller restore receipts'})
save(B/'reports/source_mapping.json',sources)
save(B/'reports/environment_audit.json',{'status':'PASS','processes':64,'monitors':monitors,'no_raw_payload_changed':True})
print(json.dumps({'status':'PASS','batch':label,'processes':64,'raw_CSV_bytes_verified':True}))
