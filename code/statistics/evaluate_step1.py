"""COCOeval on the new same-batch board predictions; no board forwards."""
import contextlib,hashlib,json,sys
from pathlib import Path
T=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(T.parent/'systematic_ABC_20261018_072643/dependencies'))
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
import numpy as np
load=lambda p:json.loads(p.read_text(encoding='utf8'))
phase=load(T/'evidence/gates_campaign/reports/phase_gates_state.json')
choices=[r for r in phase['attempts'] if r['job'].startswith('Step1_') and r['complete']]
assert choices,'No completed COCO block'
job=choices[-1]['job'];J=T/'evidence/jobs'/job
equivalence=load(J/'reports/prediction_equivalence.json')
manifest=load(J/'inputs/manifest_5000.json');ids=[x['image_id'] for x in manifest]
assert len(ids)==len(set(ids))==5000
metrics={}
for mode in ['R','F','S2','S']:
 O=T/'reports/Step1'/mode;O.mkdir(parents=True)
 with (O/'COCOeval.stdout.raw').open('w',encoding='utf8') as stream,contextlib.redirect_stdout(stream):
  coco=COCO(str(T/'inputs/instances_val2017.json'));pred=J/'capture'/('correctness_'+mode)/'predictions.json';det=coco.loadRes(str(pred))
  ev=COCOeval(coco,det,'bbox');ev.params.imgIds=ids;ev.params.maxDets=[1,10,100]
  ev.evaluate();ev.accumulate();ev.summarize()
 np.savez_compressed(O/'precision_recall.npz',precision=ev.eval['precision'],recall=ev.eval['recall'])
 z={k:float(ev.stats[i]) for k,i in [('AP',0),('AP50',1),('AP75',2),('AR100',8)]};z.update(images=5000,predictions=len(load(pred)),prediction_sha256=hashlib.sha256(pred.read_bytes()).hexdigest())
 metrics[mode]=z
 with (O/'metrics.json').open('x',encoding='utf8') as f:json.dump(z,f,indent=2)
result={'status':equivalence['status'],'selected_job':job,'metrics':metrics,'prediction_comparisons':equivalence['comparisons'],'evaluation_maxDets':[1,10,100],'new_forwards_during_evaluation':0}
with (T/'reports/Step1_evaluation.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
