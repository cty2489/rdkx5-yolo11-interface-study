"""Revised single P1 process. All production math remains in the original consumer.

Formal frames accumulate scalar records in memory. No CSV/NPZ/hash/thermal
polling occurs between the first and last formal frame, including pass boundaries.
"""
from __future__ import annotations
import os
for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
from p1_contract import (FRAME_BYTES, FRAMES, FIELDS, STAGES, ORDER, require, load,
                         digest, save_new, validate_plan)
from p1_environment import snapshot, check


def frame_step(video, sdk, consume, strategy, metadata, clock=time.perf_counter_ns):
    """All actual input, cache, bridge and detection work lies in t0..t_final."""
    t0 = clock()
    raw = video.read(FRAME_BYTES)
    require(len(raw) == FRAME_BYTES, 'Short NV12 input frame')
    t_read = clock()
    sdk.prepare(raw)  # Original bridge performs memcpy AND input cache clean.
    t_prepare = clock()
    sdk.forward()    # Submission, wait, output invalidate, task release.
    t_forward = clock()
    views = sdk.outputs()
    t_outputs = clock()
    final, trace = consume(strategy, views, sdk.props, metadata, 0.3, 0.5)
    t_final = clock()
    row = dict(zip(('t0_ns','t_read_ns','t_prepare_ns','t_forward_ns','t_outputs_ns','t_final_ns'),
                   (t0,t_read,t_prepare,t_forward,t_outputs,t_final)))
    row.update(Total_ms=(t_final-t0)/1e6, Pre_ms=(t_read-t0)/1e6,
               InputPrepare_ms=(t_prepare-t_read)/1e6, ForwardSync_ms=(t_forward-t_prepare)/1e6,
               SDK_ms=(t_forward-t_read)/1e6, OutputAccess_ms=(t_outputs-t_forward)/1e6,
               Consumer_ms=(t_final-t_outputs)/1e6, Post_ms=(t_final-t_forward)/1e6)
    row['Unclassified_ms'] = row['Total_ms']-row['Pre_ms']-row['SDK_ms']-row['Post_ms']
    for key in ('Select_ns','RestoreGather_ns','DFLCoordinates_ns','NMSAssemble_ns'):
        row[key.replace('_ns','_ms')] = trace[key]/1e6
    row['ConsumerUnclassified_ms'] = row['Consumer_ms'] - sum(row[key] for key in (
        'Select_ms','RestoreGather_ms','DFLCoordinates_ms','NMSAssemble_ms'))
    k, n = len(final['candidate_indices']), len(final['final_boxes'])
    full, selected = trace['full_float_bbox_elements'], trace['selected_integer_bbox_elements']
    # Scalar workload checks after the measured output is ready; identical code for all modes.
    require(0 <= n <= k <= 8400, 'Invalid candidate count')
    require(full == (537600 if strategy == 'F' else 0), 'Wrong full recovery workload')
    require(selected == (64*k if strategy == 'S' else 0), 'Wrong native integer workload')
    row.update(candidates=k, detections=n, full_float_bbox_elements=full, selected_integer_bbox_elements=selected)
    return final, row


def signature(final):
    """Warmup only: shape, dtype, all bytes, finite values; no numeric tolerance."""
    import numpy as np
    sig = {}
    for key, value in sorted(final.items()):
        array = np.ascontiguousarray(value)
        if np.issubdtype(array.dtype, np.floating):
            require(bool(np.isfinite(array).all()), 'Nonfinite warmup output: '+key)
        sig[key] = {'dtype': str(array.dtype), 'shape': list(array.shape),
                    'sha256': hashlib.sha256(array.tobytes()).hexdigest()}
    return sig


def compare_abi(observed, reference):
    wanted = {p['name']: p for p in reference['outputs']}
    require(set(observed) == set(wanted), 'Output name set differs from saved G2B')
    keys = ('dtype','layout','validShape','alignedShape','alignedByteSize','quantiType',
            'quantizeAxis','scaleLen','scaleFp32Bits','shiftLen','zeroPointLen')
    for name, current in observed.items():
        old = wanted[name]
        for key in keys:
            require(current[key] == old[key], 'G2B output ABI changed: '+name+'/'+key)
        require(current['stride'][:4] == old['stride'][:4], 'G2B stride changed: '+name)


def execute(plan_path, index):
    plan_path = Path(plan_path).resolve()
    plan = load(plan_path)
    validate_plan(plan)  # No SDK import/load before source and identity gates.
    require(0 <= index < 18, 'Invalid batch index')
    root = Path(plan['run_root']); task = Path(plan['task_root'])
    lock = load(task/'P1_SINGLE_BATCH_20261013.lock')
    require(lock['plan_sha256'] == digest(plan_path) and lock['batch_pid'] == os.getppid(),
            'Only the owning serial batch may launch this process')
    entry = ORDER[index]; strategy = entry['strategy']
    output = root/f'process_{index+1:02}_{strategy}'
    output.mkdir(exist_ok=False)
    (output/'STARTED').write_text(str(os.getpid())+'\n')
    state = {'status':'RUNNING', 'index':index, 'block':entry['block'], 'strategy':strategy, 'pid':os.getpid(),
             'plan_sha256':digest(plan_path), 'model_sha256':plan['models']['original' if strategy=='R' else 'modified']['sha256'],
             'input_sha256':plan['input']['sha256'], 'warmup_frames':0, 'formal_records':0,
             'model_load_attempts':0, 'model_loads':0, 'forward_attempts':0, 'forward_completions':0,
             'counts_finalized':False, 'NUMERIC_GUARD':'NOT_RUN', 'ENVIRONMENT':'NOT_RUN',
             'identity_after':False, 'sdk_closed':False, 'errors':[]}
    # RUNNING is left as incomplete after abrupt termination. It must never be resumed.
    save_new(output/'state_initial.json', state)
    rows, warmup, sdk = [], [], None
    snapshots = {}
    error = None
    try:
        baseline = plan['environment_baseline']['snapshot']
        snapshots['before_setup'] = snapshot(); check(snapshots['before_setup'], baseline)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import numpy as np
        import cv2
        from bridge import SDK
        from consumer import consume, compare_arrays
        require(np.__version__==plan['numpy'] and cv2.__version__==plan['opencv'], 'Math libraries changed')
        cv2.setNumThreads(1)
        require(cv2.getNumThreads()==1, 'OpenCV is not single-threaded')
        state['model_load_attempts'] = 1
        sdk = SDK(plan['library'], plan['models']['original' if strategy=='R' else 'modified']['path'], strategy)
        state['model_loads'] = 1
        require(sdk.lib.p1_sdk_version().decode() == plan['sdk'], 'SDK version changed')
        compare_abi(sdk.props, load(plan['abi_reference_paths']['original' if strategy=='R' else 'modified']))
        save_new(output/'actual_abi.json', sdk.props)
        meta = load(plan['coordinate_metadata_path'])
        reference = root/'warmup_reference.json'
        previous = None if index==0 else load(reference)
        if previous is not None:
            require(previous['plan_sha256']==state['plan_sha256'] and len(previous['frames'])==132,
                    'Reference from a different/incomplete batch')
        with Path(plan['input']['path']).open('rb') as video:
            for frame in range(FRAMES):
                final, row = frame_step(video, sdk, consume, strategy, meta)
                item = {'frame':frame, 'signature':signature(final), 'candidates':row['candidates'],
                        'detections':row['detections']}
                if index == 0 and frame == 0:
                    with np.load(plan['g2b_A_firstframe_reference'], allow_pickle=False) as old:
                        require(set(final).issubset(old.files), 'G2B A0 result fields differ')
                        for key, value in final.items():
                            result = compare_arrays('G2B_A0_'+key, old[key], value, output)
                            require(result['status']=='PASS', 'Real bridge A0 differs from G2B: '+key)
                if previous is not None:
                    if item != previous['frames'][frame]:
                        save_new(output/f'warmup_mismatch_{frame:03}.json',
                                 {'expected':previous['frames'][frame], 'actual':item})
                        np.savez_compressed(output/f'warmup_actual_{frame:03}.npz', **final)
                        raise RuntimeError('Strict 132-frame warmup mismatch')
                warmup.append(item)
            save_new(output/'warmup.json', {'status':'PASS','frames':warmup})
            if index==0:
                save_new(reference, {'plan_sha256':state['plan_sha256'],'frames':warmup})
            state['NUMERIC_GUARD'] = 'PASS'
            snapshots['after_warmup'] = snapshot(); check(snapshots['after_warmup'], baseline)
            # Scalar rows only until all three full passes are done. No disk writes,
            # output reference computation or environment polling in this region.
            for pass_id in range(1,4):
                video.seek(0)
                for frame in range(FRAMES):
                    final, row = frame_step(video, sdk, consume, strategy, meta)
                    row.update(block=entry['block'], index=index, strategy=strategy, **{'pass':pass_id,'frame':frame})
                    rows.append(row)
        snapshots['after_formal'] = snapshot(); check(snapshots['after_formal'], baseline)
        state['ENVIRONMENT'] = 'PASS'
        validate_plan(plan)  # Rehash only after the final formal frame.
        state['identity_after'] = True
        require(len(rows)==396 and len(warmup)==132 and sdk.counts()['forward_completions']==528,
                'Actual process budget differs from the protocol')
        state['status'] = 'COMPLETE'
    except BaseException as exc:
        error = exc
        state['status'] = 'FAILED'
        state['errors'].append({'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
    finally:
        if sdk is not None:
            try:
                state.update(sdk.counts()); state['counts_finalized'] = True
                sdk.close(); state['sdk_closed'] = True
            except BaseException as exc:
                state['status'] = 'FAILED'
                state['errors'].append({'type':type(exc).__name__,'message':str(exc),'stage':'close/counts'})
                error = error or exc
        else:
            # A failed constructor may have loaded a model, but no forward exists
            # in the unchanged constructor. Do not infer a successful load.
            state['counts_finalized'] = True
        state.update(warmup_frames=len(warmup), formal_records=len(rows))
        with (output/'formal.csv').open('x', newline='', encoding='utf-8') as f:
            writer=csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
        state['csv_sha256'] = digest(output/'formal.csv')
        save_new(output/'environment.json', snapshots)
        save_new(output/'state.json', state)
    if error is not None: raise error
    return state


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--plan',required=True); parser.add_argument('--index',required=True,type=int)
    a=parser.parse_args(); print(json.dumps(execute(a.plan,a.index),ensure_ascii=False))
if __name__=='__main__': main()
