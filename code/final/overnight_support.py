"""Integrity/recording wrapper. Original decoding, preprocessing and NMS stay unchanged."""
import hashlib
import importlib.util
import json
import logging
import os
import platform
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def stamp():
    return datetime.now().astimezone().isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                    allow_nan=False), encoding='utf-8')


def validate_outputs(mod, outputs):
    mapped = mod.map_outputs(outputs)
    stats = {}
    for key, arr in mapped.items():
        a = np.asarray(arr)
        if a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
            raise ValueError('Non-numeric or non-finite tensor: ' + key)
        g = mod.GRID_SIZES[int(key[-1])]
        channels = 64 if key.startswith('bbox') else (80 if key.startswith('cls') else 1)
        if a.shape not in ((1, channels, g, g), (1, g, g, channels)):
            raise ValueError('Invalid shape: ' + key + ' ' + str(a.shape))
        if key.startswith('class'):
            # Validate before the original decoder's astype(int), with no rounding correction.
            if not np.equal(a, np.rint(a)).all() or not ((a >= 0) & (a < 80)).all():
                raise ValueError('class_id must be exact integers in 0..79: ' + key)
        stats[key] = dict(shape=list(a.shape), dtype=str(a.dtype),
                          min=float(a.min()), max=float(a.max()))
    return stats


def validate_detections(boxes, scores, classes):
    if boxes.shape != (len(scores), 4) or classes.shape != scores.shape:
        raise ValueError('Inconsistent detection shapes')
    if not all(np.isfinite(x).all() for x in (boxes, scores, classes)):
        raise ValueError('Non-finite detection')
    if not ((scores >= 0) & (scores <= 1)).all():
        raise ValueError('COCO scores must be probabilities in [0,1]')
    if not np.equal(classes, np.rint(classes)).all() or not ((classes >= 0) & (classes < 80)).all():
        raise ValueError('Invalid model class index')
    if not ((boxes[:, 2:] - boxes[:, :2]) >= 0).all():
        raise ValueError('Negative detection width/height')


def final_limit(boxes, scores, classes, max_det):
    """Original NMS has already globally sorted scores. Preserve its exact tie order."""
    validate_detections(boxes, scores, classes)
    if max_det < 1:
        raise ValueError('max_det must be positive')
    if len(scores) > 1 and not (scores[:-1] >= scores[1:]).all():
        raise ValueError('Original NMS output is not descending by score')
    return boxes[:max_det], scores[:max_det], classes[:max_det]


def read_image(item):
    p = Path(item['path'])
    if digest(p) != item['sha256']:
        raise ValueError('Input image hash changed: ' + str(p))
    image = cv2.imread(str(p))
    if image is None:
        raise ValueError('Unreadable image: ' + str(p))
    if image.shape[:2] != (item['height'], item['width']):
        raise ValueError('Image dimensions differ from official manifest')
    return image


def describe_tensors(tensors):
    result = []
    for t in tensors:
        properties = getattr(t, 'properties', None)
        d = {'name': str(getattr(t, 'name', ''))}
        for key in ('shape', 'dtype', 'tensor_type', 'layout'):
            value = getattr(properties, key, None)
            d[key] = str(value) if value is not None else 'unknown'
        result.append(d)
    return result


def run(mod, args):
    mod.setup_logger(args.debug)
    out = Path(args.output)
    out.mkdir(exist_ok=False)
    stop = {'signal': None}
    def stopped(signum, frame):
        stop['signal'] = signum
    signal.signal(signal.SIGTERM, stopped)
    signal.signal(signal.SIGINT, stopped)
    state = {'status': 'running', 'pid': os.getpid(), 'started_at': stamp(),
             'success': 0, 'failed': 0, 'scope': 'accuracy_job_not_performance_evidence'}
    write(out / 'process_state.json', state)
    entries, records, statuses, failures = [], [], [], []
    regression = None
    config = {}
    exit_code = 1
    try:
        if (args.conf, args.iou, args.input_size, args.score_mode,
            args.category_map, args.category_offset, args.max_det, args.max_images) != (
                .001, .5, 640, 'logits', 'coco2017', 0, 100, 0):
            raise ValueError('Protocol mismatch; do not adjust fixed night parameters')
        entries = json.loads(Path(args.manifest).read_text())
        ids = [x['image_id'] for x in entries]
        if len(ids) not in (20, 5000) or ids != sorted(set(ids)):
            raise ValueError('Manifest must be the fixed sorted 20 or 5000 unique image_ids')
        for x in entries:
            if Path(x['path']).parent != Path(args.images) or Path(x['path']).name != x['file_name']:
                raise ValueError('Manifest image path mismatch')
            if int(Path(x['file_name']).stem) != x['image_id']:
                raise ValueError('Manifest image_id mismatch')
        config = {'parsed_args': vars(args), 'manifest_sha256': digest(args.manifest),
                  'script_sha256': digest(mod.__file__), 'helper_sha256': digest(__file__),
                  'model_sha256': digest(args.model), 'input_count': len(entries),
                  'nms_mode': 'class-aware', 'prediction_max_det': args.max_det,
                  'nms_tie_rule': 'unchanged np.argsort(scores[keep_global])[::-1] default kind; prefix only',
                  'preprocessing': 'original BGR uint8 letterbox: round size, center padding 114, INTER_LINEAR; BGR2YUV_I420 then NV12 uint8, no normalization',
                  'python': sys.version, 'opencv': cv2.__version__, 'numpy': np.__version__,
                  'platform': platform.platform(), 'started_at': state['started_at']}
        write(out / 'actual_config.json', config)
        write(out / 'input_manifest.json', entries)
        if args.regression_source:
            spec = importlib.util.spec_from_file_location('original_regression', args.regression_source)
            regression = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(regression)
            config['original_regression_sha256'] = digest(args.regression_source)
        logging.info('Loading original model: %s', args.model)
        model = mod.dnn.load(args.model)[0]
        config['model_inputs'] = describe_tensors(model.inputs)
        config['model_outputs'] = describe_tensors(model.outputs)
        write(out / 'actual_config.json', config)
        with (out / 'image_status.jsonl').open('x') as journal:
            for idx, item in enumerate(entries, 1):
                if stop['signal'] is not None:
                    break
                record = {'index': idx, 'image_id': item['image_id'], 'path': item['path'],
                          'input_sha256': item['sha256'], 'started_at': stamp()}
                try:
                    image = read_image(item)
                    t0 = time.time()
                    nv12, scale, left, top = mod.preprocess(image, args.input_size)
                    pre_ms = (time.time() - t0) * 1000
                    if nv12.dtype != np.uint8 or nv12.shape != (960, 640):
                        raise ValueError('Original preprocessing did not yield uint8 960x640 NV12')
                    t1 = time.time()
                    outputs = model.forward(nv12)
                    infer_ms = (time.time() - t1) * 1000
                    tensor_stats = validate_outputs(mod, outputs)
                    kw = dict(conf_threshold=args.conf, nms_iou_threshold=args.iou,
                              score_mode=args.score_mode, scale=scale, pad_left=left,
                              pad_top=top, orig_w=item['width'], orig_h=item['height'])
                    t2 = time.time()
                    boxes, scores, classes, candidates = mod.run_postprocess(outputs, **kw)
                    post_ms = (time.time() - t2) * 1000
                    if regression is not None:
                        original = regression.run_postprocess(outputs, **kw)
                        record['same_output_regression'] = all(np.array_equal(a, b)
                            for a, b in zip((boxes, scores, classes), original[:3])) and candidates == original[3]
                        if not record['same_output_regression']:
                            raise ValueError('Original/patched postprocess regression differs')
                    raw_count = len(scores)
                    boxes, scores, classes = final_limit(boxes, scores, classes, args.max_det)
                    pred = mod.to_coco_records(item['image_id'], boxes, scores, classes,
                                              args.category_map, args.category_offset)
                    if not all(x['category_id'] in mod.COCO80_TO_COCO91 for x in pred):
                        raise ValueError('Illegal COCO category_id')
                    if idx == 1:
                        config['first_input'] = {'shape': list(nv12.shape), 'dtype': str(nv12.dtype),
                                                 'min': int(nv12.min()), 'max': int(nv12.max())}
                        config['first_output_statistics'] = tensor_stats
                        write(out / 'actual_config.json', config)
                        if regression is not None:
                            np.savez_compressed(out / 'first_model_outputs.npz',
                                **{str(i): mod.get_output_array(t) for i, t in enumerate(outputs)})
                            write(out / 'first_output_names.json', [mod.get_output_name(t) for t in outputs])
                    record.update(status='completed', candidates=candidates, nms_boxes=raw_count,
                                  final_boxes=len(pred), predictions=pred,
                                  pre_ms=pre_ms, infer_ms=infer_ms, post_ms=post_ms,
                                  total_ms=pre_ms + infer_ms + post_ms)
                    records.extend(pred)
                    state['success'] += 1
                except Exception as exc:
                    logging.exception('Image failed: %s', item['path'])
                    record.update(status='failed', error_type=type(exc).__name__, error=str(exc))
                    failures.append(record.copy())
                    state['failed'] += 1
                record['finished_at'] = stamp()
                statuses.append(record)
                journal.write(json.dumps(record, allow_nan=False) + '\n')
                journal.flush()
                state['updated_at'] = stamp()
                write(out / 'process_state.json', state)
                if idx % 50 == 0 or idx == len(entries):
                    logging.info('Processed %d/%d, success=%d failed=%d', idx, len(entries), state['success'], state['failed'])
                # Core semantics/hardware errors stop this branch; never silently skip them.
                if record['status'] == 'failed':
                    break
        if state['success'] == len(entries) and not failures and len(records) > 0:
            state['status'] = 'completed'
            exit_code = 0
        else:
            state['status'] = 'partial' if state['success'] else 'failed'
            if state['success'] == len(entries) and not records:
                failures.append({'error': 'All-zero predictions; branch stopped for review'})
    except Exception as exc:
        logging.exception('Initialization/contract failed')
        failures.append({'error_type': type(exc).__name__, 'error': str(exc)})
        state['status'] = 'failed'
    finally:
        state.update(finished_at=stamp(), exit_code=exit_code, stop_signal=stop['signal'],
                     manifest_count=len(entries), unprocessed=len(entries) - len(statuses))
        write(out / 'predictions.json', records)
        write(out / 'failures.json', failures)
        summary = dict(state, total_prediction_boxes=len(records), conf_threshold=args.conf,
                       nms_iou_threshold=args.iou, score_mode=args.score_mode,
                       category_map=args.category_map, category_offset=args.category_offset,
                       prediction_max_det=args.max_det, nms_mode='class-aware',
                       images_processed=state['success'], timing_scope='progress only; not performance evidence')
        write(out / 'summary.json', summary)
        write(out / 'process_state.json', state)
    return exit_code
