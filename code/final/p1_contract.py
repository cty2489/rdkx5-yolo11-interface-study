"""P1 protocol constants and fail-closed verification; no SDK import or inference."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

GROUPS = ('RFS', 'FSR', 'SRF', 'RSF', 'SFR', 'FRS')
ORDER = [{'block': i + 1, 'strategy': s} for i, group in enumerate(GROUPS) for s in group]
FRAME_BYTES = 614400
FRAMES = 132
PROTOCOL_SHA = '7c3b2aae8b4d6e17b817e1fa33e443452beebad5fa9b5c113a3401e214de1faf'
MODEL_SHA = {'original': 'bdc4740c9af8f891a916228375738cf7ae5d9ac585b614af8770558797efb8b6',
             'modified': '469b2e82fd461955bc4e610a146f8d030a538e1124dae2c48b1fd0305561ac96'}
VIDEO_SHA = 'd3f89cc3194c035f3b9596269c301f992067ef56df654fba2917d32c87c6f24c'
FIRST_FRAME_SHA = 'a7c1d378c3fe03842be6d43294391699b2c8fdfc032918725881382a7d49fc33'
ORIGINAL_CODE_SHA = {
    'consumer.py': '18d47ae6886100dae89afa6b1d2a7e2d2a507ed5cebfc92814709d3349007cbc',
    'bridge.py': '2a581b0ba3f252eca0b8735416a2c7a8a04f3ef4042a47c32e4f288caadfeac1',
    'p1_bridge.c': '40e4c1ed91eb92279b9b977fc75196228254c9607f8e3a112eef5fe60e93aa89',
}
LIB_SHA = '86efc86ebba185ed137af2083fb7b0bbc6c14be240ccb0ee06387b5e7a3a2755'
THRESHOLDS = {'conf': 0.3, 'iou': 0.5, 'class_agnostic': True, 'top_k': None, 'max_det': None}
GATE = {'R_minus_S_mean_ms_min': 0.1, 'R_minus_S_relative_percent_min': 1.0,
        'R_minus_S_positive_blocks_min': 5, 'F_minus_S_mean_positive': True,
        'F_minus_S_positive_blocks_min': 5, 'numeric_and_environment_must_pass': True,
        'significance_or_acceptance_standard': False}
TIMES = ['t0_ns', 't_read_ns', 't_prepare_ns', 't_forward_ns', 't_outputs_ns', 't_final_ns']
STAGES = ['Total_ms', 'Pre_ms', 'InputPrepare_ms', 'ForwardSync_ms', 'SDK_ms',
          'OutputAccess_ms', 'Consumer_ms', 'Post_ms', 'Unclassified_ms',
          'Select_ms', 'RestoreGather_ms', 'DFLCoordinates_ms', 'NMSAssemble_ms',
          'ConsumerUnclassified_ms']
FIELDS = ['block', 'index', 'strategy', 'pass', 'frame'] + TIMES + STAGES + [
    'candidates', 'detections', 'full_float_bbox_elements', 'selected_integer_bbox_elements']

def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def save_new(path, value):
    """Write a new artifact, never silently replace previous evidence."""
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def validate_plan(plan, verify_files=True):
    require(plan.get('freeze_status') == 'FROZEN', 'Protocol has not been frozen on the target board')
    require(plan.get('source_protocol_status') == 'VERIFIED', 'Source protocol missing')
    require(plan.get('source_protocol_02_sha256') == PROTOCOL_SHA, 'Wrong source protocol')
    require(plan.get('order') == ORDER, 'Both strategy order and block membership are immutable')
    require(plan.get('thresholds') == THRESHOLDS, 'Detection thresholds changed')
    require(plan.get('engineering_gate') == GATE, 'Engineering gate changed')
    require(plan.get('frames') == 132 and plan.get('warmup_passes') == 1 and plan.get('formal_passes') == 3,
            'Process/frame budget changed')
    require(plan['input']['sha256'] == VIDEO_SHA and plan['input']['bytes'] == 81100800, 'Wrong A input')
    for mode, expected in MODEL_SHA.items():
        require(plan['models'][mode]['sha256'] == expected, 'Wrong model: ' + mode)
    require(plan.get('numpy') == '1.26.4' and plan.get('opencv') == '4.11.0', 'Wrong target math environment')
    require(plan.get('library_sha256') == LIB_SHA, 'Changed or unverified C bridge binary')
    require(plan.get('offline_regression_status') == 'PASS', 'Target saved-output regression missing')
    require(plan.get('environment_baseline', {}).get('status') == 'PASS', 'No target environment baseline')
    require(plan.get('abi_reference_paths') and plan.get('coordinate_metadata_path'), 'Missing G2B references')
    task = Path(plan['task_root']).resolve()
    require(Path(plan['run_root']).resolve() == task / 'run_p1_rfs', 'Cannot choose another run root to bypass a failed batch')
    if not verify_files:
        return
    files = plan['frozen_files']
    require(len(files) >= 12, 'Incomplete frozen file set')
    covered = {str(Path(f['path']).resolve()): f['sha256'] for f in files}
    require(len(covered) == len(files), 'Duplicate frozen file paths')
    needed = [plan['source_protocol_path'], plan['library'], plan['offline_regression_path'],
              plan['coordinate_metadata_path'], plan['g2b_A_firstframe_reference']] + list(plan['abi_reference_paths'].values())
    needed += [str(p) for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('._')]
    needed += [str(Path(__file__).parent.parent / name) for name in ORIGINAL_CODE_SHA]
    for path in needed:
        require(str(Path(path).resolve()) in covered, 'Required file is not frozen: ' + path)
    for item in files:
        require(digest(item['path']) == item['sha256'], 'Frozen file changed: ' + item['path'])
    require(digest(plan['source_protocol_path']) == PROTOCOL_SHA, 'Source protocol bytes changed')
    require(digest(plan['library']) == LIB_SHA, 'C bridge bytes changed')
    for name, expected in ORIGINAL_CODE_SHA.items():
        require(digest(Path(__file__).parent.parent / name) == expected, 'Original implementation changed: ' + name)
    require(digest(plan['input']['path']) == VIDEO_SHA, 'Board A input hash mismatch')
    require(Path(plan['input']['path']).stat().st_size == 81100800, 'Board A length mismatch')
    with Path(plan['input']['path']).open('rb') as f:
        require(hashlib.sha256(f.read(FRAME_BYTES)).hexdigest() == FIRST_FRAME_SHA, 'A first-frame mismatch')
    for item in plan['models'].values():
        require(digest(item['path']) == item['sha256'], 'Board model bytes mismatch')

def check_row(row, index, entry, expected_pair):
    require(int(row['index']) == index and int(row['block']) == entry['block'] and
            row['strategy'] == entry['strategy'], 'CSV identity or block order mismatch')
    require((int(row['pass']), int(row['frame'])) == expected_pair, 'CSV duplicate/missing/reordered frame')
    ts = [int(row[k]) for k in TIMES]
    require(all(t >= 0 for t in ts) and all(a <= b for a, b in zip(ts, ts[1:])), 'Non-monotonic timestamps')
    values = {k: float(row[k]) for k in STAGES}
    require(all(math.isfinite(v) for v in values.values()), 'Non-finite timing data')
    require(values['Total_ms'] > 0, 'Invalid Total')
    require(all(v >= 0 for k, v in values.items() if k not in ('Unclassified_ms', 'ConsumerUnclassified_ms')),
            'Negative measured duration')
    expected = {'Total_ms': ts[5]-ts[0], 'Pre_ms': ts[1]-ts[0], 'InputPrepare_ms': ts[2]-ts[1],
                'ForwardSync_ms': ts[3]-ts[2], 'SDK_ms': ts[3]-ts[1], 'OutputAccess_ms': ts[4]-ts[3],
                'Consumer_ms': ts[5]-ts[4], 'Post_ms': ts[5]-ts[3]}
    for key, ns in expected.items():
        require(abs(values[key] - ns/1e6) <= 1e-9, 'CSV timing contradicts raw timestamps: ' + key)
    residual = values['Total_ms'] - values['Pre_ms'] - values['SDK_ms'] - values['Post_ms']
    require(abs(values['Unclassified_ms'] - residual) <= 1e-9, 'Unclassified interval changed')
    sub = sum(values[k] for k in ('Select_ms', 'RestoreGather_ms', 'DFLCoordinates_ms', 'NMSAssemble_ms'))
    require(abs(values['ConsumerUnclassified_ms'] - (values['Consumer_ms'] - sub)) <= 1e-9,
            'Consumer residual changed')
    require(values['ConsumerUnclassified_ms'] >= -1e-9, 'Overlapping/mismatched consumer stage clocks')
    k, n = int(row['candidates']), int(row['detections'])
    require(0 <= n <= k <= 8400, 'Invalid candidate/detection counts')
    full, selected = int(row['full_float_bbox_elements']), int(row['selected_integer_bbox_elements'])
    require(full == (537600 if entry['strategy'] == 'F' else 0), 'Wrong full recovery workload')
    require(selected == (64*k if entry['strategy'] == 'S' else 0), 'Wrong selected integer workload')
    return values
