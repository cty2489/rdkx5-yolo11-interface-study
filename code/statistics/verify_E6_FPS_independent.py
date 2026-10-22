"""Independently recompute pipeline rates and interval overlap from raw CSV."""
import csv
from decimal import Decimal, localcontext
import json
from pathlib import Path

T = Path(__file__).resolve().parents[1]
B, O = T/'evidence/E6_A', T/'reports/E6_A'
load = lambda p: json.loads(p.read_text(encoding='utf8'))
plan = load(B/'protocol_frozen.json')


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def overlap(first, second):
    assert all(a[1] <= b[0] for a,b in zip(first,first[1:]))
    assert all(a[1] <= b[0] for a,b in zip(second,second[1:]))
    i = j = total = 0
    while i < len(first) and j < len(second):
        a,b = first[i],second[j]
        total += max(0,min(a[1],b[1])-max(a[0],b[0]))
        if a[1] <= b[1]: i += 1
        else: j += 1
    return total


rates, checked = {}, []
with localcontext() as context:
    context.prec = 45
    for entry in plan['order']:
        directory = B/'run'/f"process_{entry['index']+1:02}_{entry['condition']}_{entry['strategy']}"
        rows = read(directory/'formal.csv')
        assert len(rows) == 396
        timestamps = [{k:int(row[k]) for k in ['t0_ns','t_read_ns','t_forward_ns','t_post_start_ns','t_final_ns']} for row in rows]
        assert all(t['t0_ns'] <= t['t_read_ns'] <= t['t_forward_ns'] <= t['t_post_start_ns'] <= t['t_final_ns'] for t in timestamps)
        ns = timestamps[-1]['t_final_ns']-timestamps[0]['t0_ns']
        rate = Decimal(len(rows))*Decimal(10**9)/Decimal(ns)
        sdk = [(t['t_read_ns'],t['t_forward_ns']) for t in timestamps]
        post = [(t['t_post_start_ns'],t['t_final_ns']) for t in timestamps]
        shared = overlap(sdk,post)
        source = load(directory/'pipeline_throughput.json')
        assert abs(float(rate)-source['measured_FPS']) < 1e-10
        assert abs(Decimal(str(source['SDK_interval_CPU_post_service_overlap_seconds']))-Decimal(shared)/Decimal(10**9)) < Decimal('1e-12')
        rates[entry['block'],entry['condition'],entry['strategy']] = rate
        checked.append({'process_index':entry['index']+1,'stream_ns':ns,'measured_FPS_decimal':str(rate),
            'SDK_CPU_service_intersection_ns':shared,'source':'integer timestamps in original formal.csv'})
    primary = read(O/'pipeline_FPS_paired_contrasts.csv')
    contrasts = []
    t5 = Decimal('2.570581835636314')
    for policy in ['D','L']:
        for left,right in [('M6','R'),('R','F'),('M6','F')]:
            values = [rates[b,policy,left]-rates[b,policy,right] for b in range(1,7)]
            m = sum(values)/Decimal(6)
            s = (sum((v-m)**2 for v in values)/Decimal(5)).sqrt()
            h = t5*s/Decimal(6).sqrt()
            result = {'mean':m,'sample_SD':s,'CI95_low':m-h,'CI95_high':m+h}
            original = next(r for r in primary if r['policy']==policy and r['FPS_contrast']==left+'-'+right)
            assert all(abs(Decimal(original[k])-v) < Decimal('1e-9') for k,v in result.items())
            contrasts.append({'policy':policy,'contrast':left+'-'+right,
                'values_decimal':[str(v) for v in values], **{k:str(v) for k,v in result.items()}})
with (O/'independent_pipeline_FPS.json').open('x',encoding='utf8') as f:
    json.dump({'status':'PASS','processes':len(checked),'independent_numeric_method':'Decimal45, raw integer CSV timestamps and two-pointer interval intersection; fixed Student t(df5)',
        'new_forwards':0,'checks':checked,'paired_contrasts':contrasts},f,indent=2)
print(json.dumps({'status':'PASS','processes':len(checked),'paired_FPS_contrasts':len(contrasts),'new_forwards':0}))
