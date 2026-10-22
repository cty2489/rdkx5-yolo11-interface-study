"""Explicit single-class FP32 postprocessing; no Ultralytics validation API."""
import math
import cv2
import numpy as np

CONF = 0.001
IOU = 0.5
MAX_DET = 100
GRIDS = (80, 40, 20)
STRIDES = (8, 16, 32)
COCO_IDS = np.array([
    1,2,3,4,5,6,7,8,9,10,11,13,14,15,16,17,18,19,20,21,
    22,23,24,25,27,28,31,32,33,34,35,36,37,38,39,40,41,42,
    43,44,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,
    62,63,64,65,67,70,72,73,74,75,76,77,78,79,80,81,82,84,
    85,86,87,88,89,90], dtype=np.int64)
LOGIT_CONF = math.log(CONF / (1.0 - CONF))


def sigmoid(x):
    # Only selected max logits above logit(.001) reach this function.
    return (np.float32(1) / (np.float32(1) + np.exp(-x))).astype(np.float32)


def canonical(raw, backend):
    """All paths become [8400,64] DFL, max-logit, class, optional top2 margin."""
    boxes, scores, classes, margins = [], [], [], []
    for i, size in enumerate(GRIDS):
        bbox = raw[f"bbox{i}"]
        if backend == "ort6":
            if bbox.shape != (1, size, size, 64):
                raise ValueError("Unexpected six-head bbox layout")
            bbox = bbox.transpose(0, 3, 1, 2)
        if bbox.shape != (1, 64, size, size) or bbox.dtype != np.float32:
            raise ValueError("DFL shape/dtype mismatch")
        boxes.append(bbox.reshape(64, -1).T)
        if backend in ("pt", "ort6"):
            cls = raw[f"cls{i}"]
            if backend == "ort6":
                if cls.shape != (1, size, size, 80):
                    raise ValueError("Unexpected six-head cls layout")
                cls = cls.transpose(0, 3, 1, 2)
            if cls.shape != (1, 80, size, size) or cls.dtype != np.float32:
                raise ValueError("Full-cls shape/dtype mismatch")
            if not np.isfinite(cls).all():
                raise ValueError("Non-finite full cls")
            flat = cls.reshape(80, -1).T
            # Class selection is in logit space, before sigmoid.
            scores.append(flat.max(axis=1))
            classes.append(flat.argmax(axis=1).astype(np.int16))
            top2 = np.partition(flat, -2, axis=1)[:, -2:]
            margins.append(top2.max(axis=1) - top2.min(axis=1))
        else:
            score, cls = raw[f"score{i}"], raw[f"class{i}"]
            if score.shape != (1, 1, size, size) or cls.shape != score.shape:
                raise ValueError("Nine-head score/class shape mismatch")
            if score.dtype != np.float32 or cls.dtype != np.float32:
                raise ValueError("Nine-head dtype mismatch")
            if (not np.isfinite(cls).all() or not np.equal(cls, np.rint(cls)).all()
                    or not ((cls >= 0) & (cls < 80)).all()):
                raise ValueError("Invalid nine-head class id")
            scores.append(score.reshape(-1))
            classes.append(cls.reshape(-1).astype(np.int16))
            margins.append(np.full(size * size, np.nan, dtype=np.float32))
    result = dict(bbox=np.concatenate(boxes), score=np.concatenate(scores),
                  cls=np.concatenate(classes), margin=np.concatenate(margins))
    if not np.isfinite(result["bbox"]).all() or not np.isfinite(result["score"]).all():
        raise ValueError("NaN/Inf raw outputs")
    if not ((result["cls"] >= 0) & (result["cls"] < 80)).all():
        raise ValueError("Class outside 0..79")
    return result


def dfl_decode(raw):
    values = raw.reshape(-1, 4, 16)
    exp = np.exp(values - values.max(axis=-1, keepdims=True))
    prob = exp / exp.sum(axis=-1, keepdims=True)
    return (prob * np.arange(16, dtype=np.float32)[None, None]).sum(axis=-1).astype(np.float32)


def nms(boxes, scores, classes):
    keep = []
    for cls in np.unique(classes):
        ix = np.flatnonzero(classes == cls)
        b = boxes[ix]
        xywh = np.column_stack((b[:, :2], b[:, 2:] - b[:, :2])).astype(np.float32)
        local = cv2.dnn.NMSBoxes(xywh.tolist(), scores[ix].tolist(), CONF, IOU)
        if len(local):
            keep.extend(ix[np.asarray(local).reshape(-1)].tolist())
    if not keep:
        return np.empty(0, dtype=np.int64)
    keep = np.asarray(keep, dtype=np.int64)
    # Preserve the established reverse-argsort tie policy; then global limit.
    return keep[np.argsort(scores[keep])[::-1]]


def decode(data, item, geometry):
    all_boxes, all_scores, all_cls, positions = [], [], [], []
    offset = 0
    scale = min(640 / item["height"], 640 / item["width"])
    left, top = geometry["pad_left_top"]
    for size, stride in zip(GRIDS, STRIDES):
        count = size * size
        logits = data["score"][offset:offset + count]
        # One explicitly shared strict threshold comparison for all paths.
        ix = np.flatnonzero(logits.astype(np.float64) > LOGIT_CONF)
        if len(ix):
            ltrb = dfl_decode(data["bbox"][offset + ix])
            cx = ((ix % size).astype(np.float32) + np.float32(.5)) * stride
            cy = ((ix // size).astype(np.float32) + np.float32(.5)) * stride
            b = np.column_stack((cx-ltrb[:,0]*stride, cy-ltrb[:,1]*stride,
                                 cx+ltrb[:,2]*stride, cy+ltrb[:,3]*stride)).astype(np.float32)
            b[:, (0,2)] = (b[:, (0,2)] - left) / scale
            b[:, (1,3)] = (b[:, (1,3)] - top) / scale
            b[:, (0,2)] = np.clip(b[:, (0,2)], 0, item["width"])
            b[:, (1,3)] = np.clip(b[:, (1,3)], 0, item["height"])
            all_boxes.append(b)
            all_scores.append(sigmoid(logits[ix]))
            all_cls.append(data["cls"][offset + ix])
            positions.append(offset + ix)
        offset += count
    if not all_boxes:
        return dict(records=[], candidate_count=0, after_nms=0, final_boxes=0,
                    final_positions=[], boxes=np.empty((0,4),np.float32),
                    scores=np.empty(0,np.float32), classes=np.empty(0,np.int16))
    boxes, scores, classes, source = map(np.concatenate, (all_boxes, all_scores, all_cls, positions))
    keep = nms(boxes, scores, classes)
    after_nms = len(keep)
    keep = keep[:MAX_DET]
    boxes, scores, classes, source = boxes[keep], scores[keep], classes[keep], source[keep]
    if len(boxes) > MAX_DET or not np.isfinite(boxes).all() or not np.isfinite(scores).all():
        raise ValueError("Invalid final detections")
    if not ((scores >= 0) & (scores <= 1)).all() or not (boxes[:, 2:] >= boxes[:, :2]).all():
        raise ValueError("Invalid final scores/box dimensions")
    if len(scores) > 1 and not (scores[:-1] >= scores[1:]).all():
        raise ValueError("Detections not globally score sorted")
    records = []
    for b, s, c in zip(boxes, scores, classes):
        records.append(dict(image_id=int(item["image_id"]), category_id=int(COCO_IDS[int(c)]),
                            bbox=[float(b[0]),float(b[1]),float(b[2]-b[0]),float(b[3]-b[1])],
                            score=float(s)))
    return dict(records=records, candidate_count=sum(len(s) for s in all_scores),
                after_nms=after_nms, final_boxes=len(records), final_positions=source.tolist(),
                boxes=boxes, scores=scores, classes=classes)
