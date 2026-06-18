import base64
import io
import json
import math
import os
import random
import re
import shutil
import threading
import uuid
import zipfile
import ast
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

try:
    import albumentations as A
except ImportError:  # pragma: no cover - dependency may be installed after setup
    A = None

from backend.services.dataset import DATASETS_DIR, DatasetService, dataset_service

TRAIN_TUNE_DIR = os.path.join(DATASETS_DIR, '_train_tune')
TRAIN_TUNE_WORKSPACE_DIR = os.path.abspath(os.getenv('TRAIN_TUNE_WORKSPACE_DIR', 'traintune-workspace'))
TRAINING_TASKS = {'detect', 'segment', 'pose', 'classify_single'}
TRAINING_FAMILIES = {'yolo11', 'yolo26'}
TRAINING_SIZES = {'n', 's', 'm', 'l'}
TRAINING_MODES = {'standard', 'high_speed'}
BASIC_AUGMENTATION_ONLINE = {
    'fliplr': 0.5,
    'hsv_s': 0.3,
    'hsv_v': 0.25,
    'translate': 0.05,
    'scale': 0.25,
    'mosaic': 0.5,
    'close_mosaic': 10.0,
}


class MissingSegmentationMasksError(ValueError):
    def __init__(self, missing: list[dict]):
        self.missing = missing
        super().__init__('Segmentation training requires masks for every accepted annotation')


def ultralytics_task(task_type: str) -> str:
    return 'classify' if task_type == 'classify_single' else task_type


def _sanitize_json_value(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    return value


def _finite_metric_value(metric: dict, key: str, default: float = float("-inf")) -> float:
    value = metric.get(key)
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    if number in {float("inf"), float("-inf")}:
        return default
    return number


def _metric_rank(metric: dict, task_type: str) -> tuple:
    if task_type == "classify_single":
        return (
            _finite_metric_value(metric, "accuracy_top1"),
            _finite_metric_value(metric, "accuracy_top5"),
            -_finite_metric_value(metric, "val_loss", default=float("inf")),
            _finite_metric_value(metric, "epoch", default=0.0),
        )
    return (
        _finite_metric_value(metric, "map50_95"),
        _finite_metric_value(metric, "map50"),
        _finite_metric_value(metric, "precision"),
        _finite_metric_value(metric, "recall"),
        -_finite_metric_value(metric, "val_loss", default=float("inf")),
        _finite_metric_value(metric, "epoch", default=0.0),
    )


def _select_best_metric(metrics: list[dict], task_type: str) -> dict | None:
    if not metrics:
        return None
    best = max(metrics, key=lambda metric: _metric_rank(metric, task_type))
    return _sanitize_json_value(best)


class TrainingService:
    def __init__(self, dataset_service_instance: DatasetService | None = None):
        self.dataset_service = dataset_service_instance or dataset_service
        self._lock = threading.Lock()
        self._ensure_root()

    def _ensure_root(self):
        for path in (
            self._root(),
            self._workspace_root(),
            self._versions_dir(),
            self._jobs_dir(),
            self._metrics_dir(),
            self._models_dir(),
        ):
            os.makedirs(path, exist_ok=True)

    def _root(self) -> str:
        return TRAIN_TUNE_DIR

    def _workspace_root(self) -> str:
        return TRAIN_TUNE_WORKSPACE_DIR

    def _versions_dir(self) -> str:
        return os.path.join(self._root(), 'dataset_versions')

    def _jobs_dir(self) -> str:
        return os.path.join(self._root(), 'jobs')

    def _metrics_dir(self) -> str:
        return os.path.join(self._root(), 'metrics')

    def _models_dir(self) -> str:
        return os.path.join(self._root(), 'models')

    def _version_dir(self, version_id: str) -> str:
        return os.path.join(self._versions_dir(), version_id)

    def _version_meta_path(self, version_id: str) -> str:
        return os.path.join(self._version_dir(version_id), 'meta.json')

    def _job_path(self, job_id: str) -> str:
        return os.path.join(self._jobs_dir(), f'{job_id}.json')

    def _metrics_path(self, job_id: str) -> str:
        return os.path.join(self._metrics_dir(), f'{job_id}.json')

    def _model_path(self, model_id: str) -> str:
        return os.path.join(self._models_dir(), f'{model_id}.json')

    def _read_json(self, path: str, default=None):
        if not os.path.isfile(path):
            return [] if default is None else default
        with open(path) as f:
            return self._sanitize_json_value(json.load(f))

    def _write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self._sanitize_json_value(payload), f, indent=2, allow_nan=False)

    def _sanitize_json_value(self, value):
        return _sanitize_json_value(value)

    def _slugify(self, value: str, fallback: str) -> str:
        base = re.sub(r'[^A-Za-z0-9._-]+', '-', (value or '').strip()).strip('-.')
        return base or fallback

    def _split_ratios(self, config: dict) -> tuple[float, float, float]:
        split = config.get('split_config') or {'train': 70, 'val': 20, 'test': 10}
        train = float(split.get('train', 70))
        val = float(split.get('val', 20))
        test = float(split.get('test', 10))
        total = train + val + test
        if total <= 0:
            raise ValueError('split_config total must be positive')
        return train / total, val / total, test / total

    def _assign_splits(self, items: list[dict], config: dict) -> dict[str, list[dict]]:
        train_ratio, val_ratio, _test_ratio = self._split_ratios(config)
        ordered = list(items)
        random.Random(42).shuffle(ordered)
        total = len(ordered)
        if total == 0:
            return {'train': [], 'val': [], 'test': []}
        train_count = int(round(total * train_ratio))
        if train_count <= 0:
            train_count = 1
        if train_count > total:
            train_count = total
        remaining = total - train_count
        val_count = 0 if remaining <= 0 else min(remaining, int(round(total * val_ratio)))
        test_count = total - train_count - val_count
        if test_count < 0:
            test_count = 0
            val_count = total - train_count
        train_items = ordered[:train_count]
        val_items = ordered[train_count:train_count + val_count]
        test_items = ordered[train_count + val_count:train_count + val_count + test_count]
        return {'train': train_items, 'val': val_items, 'test': test_items}

    def _task_type(self, config: dict | None) -> str:
        task_type = (config or {}).get('task_type') or 'detect'
        if task_type not in TRAINING_TASKS:
            raise ValueError("task_type must be one of: classify_single, detect, pose, segment")
        return task_type

    def _format_yolo_float(self, value: float) -> str:
        return f'{value:.6f}'.rstrip('0').rstrip('.') or '0'

    def _build_yolo_detect_lines(self, detections: list[dict], class_to_id: dict[str, int], width: int, height: int) -> str:
        lines = []
        for det in detections:
            cls_id = class_to_id.get(det['label'], -1)
            if cls_id < 0:
                continue
            x1, y1, x2, y2 = det['box']
            x_center = ((x1 + x2) / 2) / width
            y_center = ((y1 + y2) / 2) / height
            bw = (x2 - x1) / width
            bh = (y2 - y1) / height
            lines.append(f'{cls_id} {self._format_yolo_float(x_center)} {self._format_yolo_float(y_center)} {self._format_yolo_float(bw)} {self._format_yolo_float(bh)}')
        return '\n'.join(lines)

    def _normalize_polygon(self, points: list, width: int, height: int) -> list[float] | None:
        normalized: list[float] = []
        if width <= 0 or height <= 0:
            return None
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return None
            try:
                x = min(max(float(point[0]), 0.0), float(width)) / width
                y = min(max(float(point[1]), 0.0), float(height)) / height
            except (TypeError, ValueError):
                return None
            normalized.extend([x, y])
        return normalized if len(normalized) >= 6 else None

    def _build_yolo_segment_lines(self, detections: list[dict], class_to_id: dict[str, int], width: int, height: int) -> str:
        lines = []
        for det in detections:
            cls_id = class_to_id.get(det['label'], -1)
            if cls_id < 0:
                continue
            polygon = self._normalize_polygon(det.get('mask') or [], width, height)
            if not polygon:
                continue
            coords = ' '.join(self._format_yolo_float(value) for value in polygon)
            lines.append(f'{cls_id} {coords}')
        return '\n'.join(lines)

    def _pose_visibility_value(self, visibility: str) -> int:
        if visibility == 'missing':
            return 0
        if visibility == 'occluded':
            return 1
        return 2

    def _build_yolo_pose_lines(self, poses: list[dict], class_to_id: dict[str, int], width: int, height: int, pose_template: dict | None = None) -> str:
        keypoint_names = (pose_template or {}).get('keypoint_names') or []
        lines = []
        for pose in poses:
            cls_id = class_to_id.get(pose['label'], -1)
            if cls_id < 0:
                continue
            x1, y1, x2, y2 = pose['box']
            parts = [
                str(cls_id),
                self._format_yolo_float(((x1 + x2) / 2) / width),
                self._format_yolo_float(((y1 + y2) / 2) / height),
                self._format_yolo_float((x2 - x1) / width),
                self._format_yolo_float((y2 - y1) / height),
            ]
            keypoints = pose.get('keypoints') or []
            keypoint_map = {kp.get('name'): kp for kp in keypoints if isinstance(kp, dict)}
            ordered = [keypoint_map[name] for name in keypoint_names if name in keypoint_map] if keypoint_names else keypoints
            for kp in ordered:
                parts.extend([
                    self._format_yolo_float(min(max(float(kp.get('x', 0.0)), 0.0), float(width)) / width),
                    self._format_yolo_float(min(max(float(kp.get('y', 0.0)), 0.0), float(height)) / height),
                    str(self._pose_visibility_value(kp.get('visibility', 'visible'))),
                ])
            lines.append(' '.join(parts))
        return '\n'.join(lines)

    def _build_yolo_lines(self, detections: list[dict], class_to_id: dict[str, int], width: int, height: int, task_type: str, pose_template: dict | None = None) -> str:
        if task_type == 'segment':
            return self._build_yolo_segment_lines(detections, class_to_id, width, height)
        if task_type == 'pose':
            return self._build_yolo_pose_lines(detections, class_to_id, width, height, pose_template)
        return self._build_yolo_detect_lines(detections, class_to_id, width, height)

    def _missing_segment_masks(self, entries: list[dict]) -> list[dict]:
        missing = []
        for entry in entries:
            for det in entry['detections']:
                if self._normalize_polygon(det.get('mask') or [], entry['width'], entry['height']):
                    continue
                missing.append({
                    'img_id': entry.get('img_id'),
                    'image': entry.get('export_filename'),
                    'detection_id': det.get('id'),
                    'label': det.get('label'),
                })
        return missing

    def _unique_name(self, filename: str, used: set[str]) -> str:
        safe = self._slugify(os.path.basename(filename), 'image.jpg')
        if safe not in used:
            used.add(safe)
            return safe
        stem, ext = os.path.splitext(safe)
        index = 2
        while True:
            candidate = f'{stem}-{index}{ext}'
            if candidate not in used:
                used.add(candidate)
                return candidate
            index += 1

    def _write_dataset_yaml(self, dataset_path: str, class_to_id: dict[str, int], task_type: str = 'detect', pose_template: dict | None = None):
        if task_type == 'classify_single':
            return
        names = {v: k for k, v in class_to_id.items()}
        lines = [
            f'path: {dataset_path}',
            'train: images/train',
            'val: images/val',
            'test: images/test',
        ]
        if task_type == 'pose' and pose_template:
            lines.extend([
                f"kpt_shape: {pose_template.get('kpt_shape')}",
                f"flip_idx: {pose_template.get('flip_idx')}",
            ])
        lines.extend([
            'names:',
        ])
        for cid, cname in sorted(names.items()):
            lines.append(f'  {cid}: {cname}')
        if task_type == 'pose' and pose_template:
            lines.append('kpt_names:')
            for index, name in enumerate(pose_template.get('keypoint_names') or []):
                lines.append(f'  {index}: {name}')
        Path(dataset_path, 'dataset.yaml').write_text('\n'.join(lines) + '\n')

    def _normalize_preprocessing_config(self, config: dict) -> dict:
        raw = config.get('preprocessing_config') or {}
        resize_mode = raw.get('resize_mode') or config.get('resize_mode') or 'keep'
        if resize_mode == 'fit':
            resize_mode = 'letterbox'
        if resize_mode not in {'keep', 'letterbox', 'stretch'}:
            resize_mode = 'keep'
        target_size = raw.get('target_size') or config.get('imgsz') or config.get('target_size') or 640
        try:
            target_size = int(target_size)
        except (TypeError, ValueError):
            target_size = 640
        target_size = min(max(target_size, 32), 4096)
        return {
            'auto_orient': bool(raw.get('auto_orient', True)),
            'resize_mode': resize_mode,
            'target_size': target_size,
        }

    def _transform_detection_geometry(self, detections: list[dict], scale_x: float, scale_y: float, pad_x: float = 0.0, pad_y: float = 0.0) -> list[dict]:
        transformed = []
        for det in detections:
            x1, y1, x2, y2 = det['box']
            next_det = {
                **det,
                'box': [
                    x1 * scale_x + pad_x,
                    y1 * scale_y + pad_y,
                    x2 * scale_x + pad_x,
                    y2 * scale_y + pad_y,
                ],
            }
            if det.get('mask'):
                next_det['mask'] = [[float(point[0]) * scale_x + pad_x, float(point[1]) * scale_y + pad_y] for point in det['mask']]
            if det.get('keypoints'):
                next_det['keypoints'] = [
                    {
                        **point,
                        'x': float(point.get('x', 0.0)) * scale_x + pad_x,
                        'y': float(point.get('y', 0.0)) * scale_y + pad_y,
                    }
                    for point in det['keypoints']
                ]
            transformed.append(next_det)
        return transformed

    def _preprocess_entry_image(self, image: np.ndarray, detections: list[dict], preprocessing_config: dict, task_type: str) -> tuple[np.ndarray, list[dict]]:
        height, width = image.shape[:2]
        detections = self._sanitize_detections(detections, width, height, task_type)
        resize_mode = preprocessing_config.get('resize_mode', 'keep')
        if resize_mode == 'keep' or not detections:
            return image, detections
        target = int(preprocessing_config.get('target_size') or 640)
        if resize_mode == 'stretch':
            resized = cv2.resize(image, (target, target), interpolation=cv2.INTER_AREA)
            next_detections = self._transform_detection_geometry(detections, target / width, target / height)
            return resized, self._sanitize_detections(next_detections, target, target, task_type)
        scale = min(target / width, target / height)
        next_width = max(1, int(round(width * scale)))
        next_height = max(1, int(round(height * scale)))
        resized = cv2.resize(image, (next_width, next_height), interpolation=cv2.INTER_AREA)
        canvas = np.full((target, target, 3), 114, dtype=np.uint8)
        pad_x = (target - next_width) // 2
        pad_y = (target - next_height) // 2
        canvas[pad_y:pad_y + next_height, pad_x:pad_x + next_width] = resized
        next_detections = self._transform_detection_geometry(detections, scale, scale, pad_x, pad_y)
        return canvas, self._sanitize_detections(next_detections, target, target, task_type)

    def _normalize_augmentation_config(self, config: dict) -> dict:
        raw = config.get('augmentation_config') or {'profile': 'baseline'}
        if raw.get('mode') == 'basic':
            return {
                'mode': 'basic',
                'profile': 'basic',
                'multiplier': 1,
                'apply_to': 'train',
                'offline': {},
                'online': dict(BASIC_AUGMENTATION_ONLINE),
            }
        if raw.get('mode') in {'hybrid', 'advanced'}:
            multiplier = int(raw.get('multiplier') or 1)
            multiplier = min(max(multiplier, 1), 5)
            return {
                'mode': 'advanced',
                'profile': raw.get('profile', 'custom'),
                'multiplier': multiplier,
                'apply_to': 'train',
                'offline': raw.get('offline') or {},
                'online': self._online_augmentation_args(raw),
            }
        profile = raw.get('profile', 'baseline')
        online = {}
        if profile == 'standard':
            online = {'fliplr': 0.5, 'degrees': 5.0, 'translate': 0.05, 'scale': 0.25, 'mosaic': 0.5}
        return {
            'mode': 'advanced',
            'profile': profile,
            'multiplier': 1,
            'apply_to': 'train',
            'offline': {},
            'online': online,
        }

    def _online_augmentation_args(self, augmentation_config: dict) -> dict:
        allowed = {
            'hsv_h', 'hsv_s', 'hsv_v', 'degrees', 'translate', 'scale', 'shear', 'perspective',
            'flipud', 'fliplr', 'bgr', 'mosaic', 'mixup', 'copy_paste', 'erasing', 'close_mosaic',
        }
        online = augmentation_config.get('online') or {}
        cleaned = {}
        for key, value in online.items():
            if key not in allowed or value in (None, ''):
                continue
            try:
                cleaned[key] = float(value)
            except (TypeError, ValueError):
                continue
        return cleaned

    def _read_entry_image(self, entry: dict) -> np.ndarray:
        if entry.get('image_bytes') is not None:
            arr = np.frombuffer(entry['image_bytes'], np.uint8)
            image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        else:
            image = cv2.imread(entry['image_path'])
        if image is None:
            raise ValueError(f"Unable to read image {entry.get('export_filename', 'image')}")
        return image

    def _clamp_box(self, box: list[float], width: int, height: int) -> list[float] | None:
        x1, y1, x2, y2 = [float(value) for value in box]
        x1 = min(max(x1, 0.0), float(width))
        x2 = min(max(x2, 0.0), float(width))
        y1 = min(max(y1, 0.0), float(height))
        y2 = min(max(y2, 0.0), float(height))
        if x2 <= x1 or y2 <= y1:
            return None
        return [x1, y1, x2, y2]

    def _derive_box_from_mask(self, mask: list, width: int, height: int) -> list[float] | None:
        points = self._normalize_polygon(mask, width, height)
        if not points:
            return None
        xs = [points[index] * width for index in range(0, len(points), 2)]
        ys = [points[index] * height for index in range(1, len(points), 2)]
        return self._clamp_box([min(xs), min(ys), max(xs), max(ys)], width, height)

    def _sanitize_detections(self, detections: list[dict], width: int, height: int, task_type: str) -> list[dict]:
        sanitized = []
        for det in detections:
            box = self._clamp_box(det.get('box', []), width, height) if len(det.get('box', [])) == 4 else None
            mask = det.get('mask')
            if task_type == 'segment':
                polygon = self._normalize_polygon(mask or [], width, height)
                if not polygon:
                    continue
                mask_points = [[polygon[i] * width, polygon[i + 1] * height] for i in range(0, len(polygon), 2)]
                box = self._derive_box_from_mask(mask_points, width, height)
                if not box:
                    continue
                sanitized.append({**det, 'box': box, 'mask': mask_points})
            elif box:
                next_det = {**det, 'box': box}
                if task_type == 'pose':
                    keypoints = []
                    for point in det.get('keypoints') or []:
                        try:
                            x = min(max(float(point.get('x', 0.0)), 0.0), float(width))
                            y = min(max(float(point.get('y', 0.0)), 0.0), float(height))
                        except (TypeError, ValueError):
                            continue
                        keypoints.append({**point, 'x': x, 'y': y})
                    if not keypoints:
                        continue
                    next_det['keypoints'] = keypoints
                sanitized.append(next_det)
        return sanitized

    def _pascal_to_detections(self, bboxes: list, labels: list[str], originals: list[dict], width: int, height: int, task_type: str, masks: list | None = None) -> list[dict]:
        detections = []
        for index, bbox in enumerate(bboxes):
            box = self._clamp_box(list(bbox), width, height)
            if not box:
                continue
            det = {**originals[index], 'label': labels[index], 'box': box}
            if task_type == 'segment' and masks is not None:
                mask = masks[index].astype(np.uint8)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    continue
                contour = max(contours, key=cv2.contourArea)
                if cv2.contourArea(contour) < 4:
                    continue
                points = contour.reshape(-1, 2).astype(float).tolist()
                if len(points) < 3:
                    continue
                det['mask'] = points
            detections.append(det)
        return detections

    def _detections_to_masks(self, detections: list[dict], width: int, height: int) -> list[np.ndarray]:
        masks = []
        for det in detections:
            mask = np.zeros((height, width), dtype=np.uint8)
            polygon = det.get('mask') or []
            if polygon:
                points = np.array([[
                    min(max(float(point[0]), 0.0), float(width - 1)),
                    min(max(float(point[1]), 0.0), float(height - 1)),
                ] for point in polygon], dtype=np.int32)
                if len(points) >= 3:
                    cv2.fillPoly(mask, [points], 1)
            masks.append(mask)
        return masks

    def _build_albumentations_transform(self, offline: dict, force: bool = False):
        if A is None:
            return None
        transforms = []
        fliplr = float(offline.get('fliplr') or 0.0)
        flipud = float(offline.get('flipud') or 0.0)
        if fliplr > 0:
            transforms.append(A.HorizontalFlip(p=1.0 if force else min(fliplr, 1.0)))
        if flipud > 0:
            transforms.append(A.VerticalFlip(p=1.0 if force else min(flipud, 1.0)))
        degrees = float(offline.get('degrees') or 0.0)
        shear = float(offline.get('shear') or 0.0)
        translate = float(offline.get('translate') or 0.0)
        scale = float(offline.get('scale') or 0.0)
        if any(abs(value) > 0 for value in (degrees, shear, translate, scale)):
            affine_kwargs = {
                'rotate': (-abs(degrees), abs(degrees)),
                'shear': (-abs(shear), abs(shear)),
                'translate_percent': (-abs(translate), abs(translate)),
                'p': 1.0,
            }
            if scale:
                affine_kwargs['scale'] = (max(0.1, 1 - abs(scale)), 1 + abs(scale))
            transforms.append(A.Affine(**affine_kwargs))
        hsv_h = float(offline.get('hsv_h') or 0.0)
        hsv_s = float(offline.get('hsv_s') or 0.0)
        hsv_v = float(offline.get('hsv_v') or 0.0)
        if any(value > 0 for value in (hsv_h, hsv_s, hsv_v)):
            transforms.append(A.HueSaturationValue(
                hue_shift_limit=int(hsv_h * 180),
                sat_shift_limit=int(hsv_s * 100),
                val_shift_limit=int(hsv_v * 100),
                p=1.0,
            ))
        exposure = float(offline.get('exposure') or 0.0)
        if exposure > 0:
            transforms.append(A.RandomBrightnessContrast(brightness_limit=exposure, contrast_limit=exposure, p=1.0))
        blur = float(offline.get('blur') or 0.0)
        if blur > 0:
            transforms.append(A.GaussianBlur(blur_limit=(3, 5), p=min(blur, 1.0)))
        noise = float(offline.get('noise') or 0.0)
        if noise > 0:
            transforms.append(A.GaussNoise(p=min(noise, 1.0)))
        if not transforms:
            return None
        return A.Compose(
            transforms,
            bbox_params=A.BboxParams(format='pascal_voc', label_fields=['labels'], min_visibility=0.05),
        )

    def _manual_augment(self, image: np.ndarray, detections: list[dict], offline: dict, task_type: str) -> tuple[np.ndarray, list[dict]]:
        height, width = image.shape[:2]
        augmented = image.copy()
        output = [dict(det) for det in detections]
        if float(offline.get('fliplr') or 0.0) > 0:
            augmented = cv2.flip(augmented, 1)
            for det in output:
                x1, y1, x2, y2 = det['box']
                det['box'] = [width - x2, y1, width - x1, y2]
                if det.get('mask'):
                    det['mask'] = [[width - float(point[0]), float(point[1])] for point in det['mask']]
                if det.get('keypoints'):
                    det['keypoints'] = [{**point, 'x': width - float(point.get('x', 0.0))} for point in det['keypoints']]
        if float(offline.get('flipud') or 0.0) > 0:
            augmented = cv2.flip(augmented, 0)
            for det in output:
                x1, y1, x2, y2 = det['box']
                det['box'] = [x1, height - y2, x2, height - y1]
                if det.get('mask'):
                    det['mask'] = [[float(point[0]), height - float(point[1])] for point in det['mask']]
                if det.get('keypoints'):
                    det['keypoints'] = [{**point, 'y': height - float(point.get('y', 0.0))} for point in det['keypoints']]
        noise = float(offline.get('noise') or 0.0)
        if noise > 0:
            sigma = max(1.0, noise * 24.0)
            jitter = np.random.default_rng(42).normal(0, sigma, augmented.shape).astype(np.int16)
            augmented = np.clip(augmented.astype(np.int16) + jitter, 0, 255).astype(np.uint8)
        output = self._sanitize_detections(output, width, height, task_type)
        return augmented, output

    def _augment_entry(self, image: np.ndarray, detections: list[dict], augmentation_config: dict, task_type: str, force: bool = False) -> tuple[np.ndarray, list[dict]]:
        height, width = image.shape[:2]
        detections = self._sanitize_detections(detections, width, height, task_type)
        if not detections:
            return image, []
        offline = augmentation_config.get('offline') or {}
        if not any(float(value or 0) > 0 for value in offline.values()):
            return image, detections
        if task_type == 'pose':
            return self._manual_augment(image, detections, offline, task_type)
        transform = self._build_albumentations_transform(offline, force=force)
        if transform is None:
            return self._manual_augment(image, detections, offline, task_type)
        labels = [det['label'] for det in detections]
        bboxes = [det['box'] for det in detections]
        payload = {'image': image, 'bboxes': bboxes, 'labels': labels}
        masks = None
        if task_type == 'segment':
            masks = self._detections_to_masks(detections, width, height)
            payload['masks'] = masks
        transformed = transform(**payload)
        next_image = transformed['image']
        next_height, next_width = next_image.shape[:2]
        next_detections = self._pascal_to_detections(
            transformed['bboxes'],
            list(transformed['labels']),
            detections,
            next_width,
            next_height,
            task_type,
            transformed.get('masks'),
        )
        return next_image, next_detections

    def _write_image_and_label(self, dataset_path: str, subset: str, filename: str, image: np.ndarray, detections: list[dict], class_to_id: dict[str, int], task_type: str, pose_template: dict | None = None) -> bool:
        height, width = image.shape[:2]
        detections = self._sanitize_detections(detections, width, height, task_type)
        if not detections:
            return False
        image_path = os.path.join(dataset_path, 'images', subset, filename)
        label_name = f"{os.path.splitext(filename)[0]}.txt"
        label_path = os.path.join(dataset_path, 'labels', subset, label_name)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        os.makedirs(os.path.dirname(label_path), exist_ok=True)
        cv2.imwrite(image_path, image)
        Path(label_path).write_text(self._build_yolo_lines(detections, class_to_id, width, height, task_type, pose_template) + '\n')
        return True

    def _write_classification_image(self, dataset_path: str, subset: str, filename: str, image: np.ndarray, label: str) -> bool:
        class_dir = os.path.join(dataset_path, subset, self._slugify(label, 'class'))
        os.makedirs(class_dir, exist_ok=True)
        return bool(cv2.imwrite(os.path.join(class_dir, filename), image))

    def _write_classification_snapshot_files(self, dataset_path: str, split_map: dict[str, list[dict]], config: dict) -> dict:
        preprocessing_config = self._normalize_preprocessing_config(config)
        augmentation_config = self._normalize_augmentation_config(config)
        split_counts = {subset: 0 for subset in ('train', 'val', 'test')}
        train_original = len(split_map.get('train', []))
        train_generated = 0
        for subset in ('train', 'val', 'test'):
            os.makedirs(os.path.join(dataset_path, subset), exist_ok=True)
            for entry in split_map[subset]:
                image = self._read_entry_image(entry)
                if preprocessing_config.get('resize_mode') != 'keep':
                    target = int(preprocessing_config.get('target_size') or 640)
                    image = cv2.resize(image, (target, target), interpolation=cv2.INTER_AREA)
                if self._write_classification_image(dataset_path, subset, entry['export_filename'], image, entry['label']):
                    split_counts[subset] += 1
        multiplier = int(augmentation_config.get('multiplier') or 1)
        offline = augmentation_config.get('offline') or {}
        has_offline_steps = any(float(value or 0) > 0 for value in offline.values())
        if multiplier > 1 and train_original > 0 and has_offline_steps:
            for copy_index in range(1, multiplier):
                for entry in split_map.get('train', []):
                    image = self._read_entry_image(entry)
                    if preprocessing_config.get('resize_mode') != 'keep':
                        target = int(preprocessing_config.get('target_size') or 640)
                        image = cv2.resize(image, (target, target), interpolation=cv2.INTER_AREA)
                    aug_image, _ = self._manual_augment(image, [], offline, 'detect')
                    stem, ext = os.path.splitext(entry['export_filename'])
                    filename = self._unique_name(f'{stem}-aug-{copy_index}{ext or ".jpg"}', set())
                    if self._write_classification_image(dataset_path, 'train', filename, aug_image, entry['label']):
                        split_counts['train'] += 1
                        train_generated += 1
        primary = next((subset for subset in ('train', 'val', 'test') if split_counts[subset] > 0), 'train')
        split_counts.update({
            'primary': primary,
            'train_original': train_original,
            'train_generated': train_generated,
            'final_total': split_counts['train'] + split_counts['val'] + split_counts['test'],
        })
        return {
            'split_counts': split_counts,
            'preprocessing_config': preprocessing_config,
            'augmentation_config': augmentation_config,
        }

    def _write_snapshot_files(self, dataset_path: str, split_map: dict[str, list[dict]], class_to_id: dict[str, int], task_type: str, config: dict) -> dict:
        if task_type == 'classify_single':
            return self._write_classification_snapshot_files(dataset_path, split_map, config)
        preprocessing_config = self._normalize_preprocessing_config(config)
        augmentation_config = self._normalize_augmentation_config(config)
        pose_template = (config.get('task_config') or {}).get('pose_template') or config.get('pose_template')
        split_counts = {subset: 0 for subset in ('train', 'val', 'test')}
        train_original = len(split_map.get('train', []))
        train_generated = 0
        for subset in ('train', 'val', 'test'):
            os.makedirs(os.path.join(dataset_path, 'images', subset), exist_ok=True)
            os.makedirs(os.path.join(dataset_path, 'labels', subset), exist_ok=True)
            for entry in split_map[subset]:
                image = self._read_entry_image(entry)
                detections = self._sanitize_detections(entry['detections'], image.shape[1], image.shape[0], task_type)
                image, detections = self._preprocess_entry_image(image, detections, preprocessing_config, task_type)
                if self._write_image_and_label(dataset_path, subset, entry['export_filename'], image, detections, class_to_id, task_type, pose_template):
                    split_counts[subset] += 1
        multiplier = int(augmentation_config.get('multiplier') or 1)
        has_offline_steps = any(float(value or 0) > 0 for value in (augmentation_config.get('offline') or {}).values())
        if multiplier > 1 and train_original > 0 and has_offline_steps:
            for copy_index in range(1, multiplier):
                for entry in split_map.get('train', []):
                    image = self._read_entry_image(entry)
                    detections = self._sanitize_detections(entry['detections'], image.shape[1], image.shape[0], task_type)
                    image, detections = self._preprocess_entry_image(image, detections, preprocessing_config, task_type)
                    aug_image, aug_detections = self._augment_entry(image, detections, augmentation_config, task_type, force=True)
                    stem, ext = os.path.splitext(entry['export_filename'])
                    filename = self._unique_name(f'{stem}-aug-{copy_index}{ext or ".jpg"}', set())
                    if self._write_image_and_label(dataset_path, 'train', filename, aug_image, aug_detections, class_to_id, task_type, pose_template):
                        split_counts['train'] += 1
                        train_generated += 1
        primary = next((subset for subset in ('train', 'val', 'test') if split_counts[subset] > 0), 'train')
        split_counts.update({
            'primary': primary,
            'train_original': train_original,
            'train_generated': train_generated,
            'final_total': split_counts['train'] + split_counts['val'] + split_counts['test'],
        })
        return {
            'split_counts': split_counts,
            'preprocessing_config': preprocessing_config,
            'augmentation_config': augmentation_config,
        }

    def _annotation_preview(self, detections: list[dict]) -> list[dict]:
        annotations = []
        for det in detections:
            item = {'label': det.get('label', ''), 'box': [round(float(value), 2) for value in det.get('box', [])]}
            if det.get('mask'):
                item['mask'] = [[round(float(point[0]), 2), round(float(point[1]), 2)] for point in det['mask']]
            if det.get('keypoints'):
                item['keypoints'] = [
                    {
                        'name': point.get('name'),
                        'x': round(float(point.get('x', 0.0)), 2),
                        'y': round(float(point.get('y', 0.0)), 2),
                        'visibility': point.get('visibility', 'visible'),
                    }
                    for point in det['keypoints']
                ]
            annotations.append(item)
        return annotations

    def _encode_preview(self, image: np.ndarray, detections: list[dict]) -> dict:
        rendered = image.copy()
        for det in detections:
            color = (62, 207, 142)
            box = [int(round(value)) for value in det.get('box', [])]
            if len(box) == 4:
                cv2.rectangle(rendered, (box[0], box[1]), (box[2], box[3]), color, 2)
                cv2.putText(rendered, det.get('label', ''), (box[0], max(12, box[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
            if det.get('mask'):
                pts = np.array(det['mask'], dtype=np.int32)
                if len(pts) >= 3:
                    cv2.polylines(rendered, [pts], True, (37, 99, 235), 2)
            for point in det.get('keypoints') or []:
                if point.get('visibility') == 'missing':
                    continue
                cv2.circle(rendered, (int(round(point.get('x', 0))), int(round(point.get('y', 0)))), 3, (245, 158, 11), -1)
        ok, buffer = cv2.imencode('.jpg', rendered, [cv2.IMWRITE_JPEG_QUALITY, 86])
        if not ok:
            raise ValueError('Unable to encode preview image')
        return {
            'image': 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode(),
            'annotations': self._annotation_preview(detections),
        }

    def _version_summary(self, entries: list[dict], source_count: int, classes: list[str]) -> dict:
        annotations = sum(len(entry['detections']) for entry in entries)
        return {
            'original_file_count': source_count,
            'usable_labeled_images': len(entries),
            'total_annotations': annotations,
            'class_count': len(classes),
            'classes': classes,
            'average_annotations_per_image': round(annotations / len(entries), 2) if entries else 0,
        }

    def _version_payload(self, version_id: str) -> dict:
        return self._read_json(self._version_meta_path(version_id), {})

    def _job_training_config(self, job: dict) -> dict:
        return {
            'family': job.get('architecture_family', 'yolo11'),
            'size': job.get('architecture_size', 'n'),
            'base_checkpoint': job.get('base_checkpoint', ''),
            'epochs': job.get('epochs', 50),
            'patience': job.get('patience', 30),
            'imgsz': job.get('imgsz', 640),
            'batch': job.get('batch', -1),
            'workers': job.get('workers', 2),
            'training_mode': job.get('training_mode', 'standard'),
        }

    def _with_training_config(self, version: dict) -> dict:
        if version.get('training_config'):
            return version
        version_id = version.get('id')
        linked_jobs = [job for job in self.list_training_jobs() if job.get('dataset_version_id') == version_id]
        if linked_jobs:
            latest = sorted(linked_jobs, key=lambda job: job.get('created_at') or '', reverse=True)[0]
            return {**version, 'training_config': self._job_training_config(latest)}
        return {**version, 'training_config': self._normalize_dataset_training_config({}, version.get('task_type', 'detect'))}

    def list_dataset_versions(self) -> list[dict]:
        self._ensure_root()
        versions = []
        for name in sorted(os.listdir(self._versions_dir())):
            meta_path = self._version_meta_path(name)
            if os.path.isfile(meta_path):
                versions.append(self._with_training_config(self._read_json(meta_path, {})))
        return versions

    def get_dataset_version(self, version_id: str) -> dict:
        payload = self._version_payload(version_id)
        if not payload:
            raise FileNotFoundError(f'Dataset version {version_id} not found')
        return self._with_training_config(payload)

    def delete_dataset_version(self, version_id: str) -> None:
        self.get_dataset_version(version_id)
        used_by_job = any(job.get('dataset_version_id') == version_id for job in self.list_training_jobs())
        used_by_model = any(model.get('dataset_version_id') == version_id for model in self.list_model_versions())
        if used_by_job or used_by_model:
            raise RuntimeError('Dataset version is referenced by training history and cannot be deleted')
        shutil.rmtree(self._version_dir(version_id))

    def _live_dataset_entries(self, dataset_name: str, task_type: str) -> tuple[list[dict], int, list[str]]:
        pdir = self.dataset_service._project_dir(dataset_name)
        ann_dir = os.path.join(pdir, 'annotations')
        img_dir = os.path.join(pdir, 'images')
        if not os.path.isdir(ann_dir):
            raise FileNotFoundError(f"Dataset '{dataset_name}' not found")
        meta = self.dataset_service._read_meta(dataset_name)
        project_task = meta.get('task_type', 'detect')
        if project_task != task_type and not (project_task == 'detect' and task_type == 'segment'):
            raise ValueError(f"Dataset task_type '{project_task}' does not match Train Tune task_type '{task_type}'")

        entries = []
        used_filenames: set[str] = set()
        class_names: set[str] = set()
        all_annotation_files = [f for f in sorted(os.listdir(ann_dir)) if f.endswith('.json')]
        for fname in all_annotation_files:
            ann = self._read_json(os.path.join(ann_dir, fname), {})
            image_name = ann.get('image')
            image_path = os.path.join(img_dir, image_name)
            if not os.path.isfile(image_path):
                continue
            export_filename = self._unique_name(ann.get('original_filename') or image_name, used_filenames)
            if task_type == 'classify_single':
                labels = [label for label in ann.get('labels', []) if label.get('accepted', True) and label.get('label')]
                if len(labels) != 1:
                    continue
                class_names.add(labels[0]['label'])
                entries.append({
                    'img_id': os.path.splitext(fname)[0],
                    'image_path': image_path,
                    'export_filename': export_filename,
                    'width': int(ann['width']),
                    'height': int(ann['height']),
                    'label': labels[0]['label'],
                    'detections': [{'label': labels[0]['label'], 'box': [0, 0, int(ann['width']), int(ann['height'])]}],
                })
                continue
            if task_type == 'pose':
                poses = [p for p in ann.get('poses', []) if p.get('accepted', True)]
                valid_poses = [p for p in poses if p.get('label') and len(p.get('box', [])) == 4 and p.get('keypoints')]
                if not valid_poses:
                    continue
                for pose in valid_poses:
                    class_names.add(pose['label'])
                entries.append({
                    'img_id': os.path.splitext(fname)[0],
                    'image_path': image_path,
                    'export_filename': export_filename,
                    'width': int(ann['width']),
                    'height': int(ann['height']),
                    'detections': valid_poses,
                })
                continue
            detections = [d for d in ann.get('detections', []) if d.get('accepted', True)]
            valid_dets = [d for d in detections if d.get('label') and len(d.get('box', [])) == 4]
            if not valid_dets:
                continue
            for det in valid_dets:
                class_names.add(det['label'])
            entries.append({
                'img_id': os.path.splitext(fname)[0],
                'image_path': image_path,
                'export_filename': export_filename,
                'width': int(ann['width']),
                'height': int(ann['height']),
                'detections': valid_dets,
            })

        if not entries:
            raise ValueError('Dataset has no accepted annotations to train on')
        if task_type == 'segment':
            missing = self._missing_segment_masks(entries)
            if missing:
                raise MissingSegmentationMasksError(missing)
        return entries, len(all_annotation_files), sorted(class_names)

    def create_dataset_version_from_live_dataset(self, dataset_name: str, config: dict) -> dict:
        task_type = self._task_type(config)
        entries, source_count, classes = self._live_dataset_entries(dataset_name, task_type)
        class_to_id = {name: idx for idx, name in enumerate(classes)}
        split_map = self._assign_splits(entries, config)
        version_id = uuid.uuid4().hex
        version_dir = self._version_dir(version_id)
        dataset_path = os.path.join(version_dir, 'dataset')
        task_config = self.dataset_service._read_meta(dataset_name).get('task_config', {})
        if task_config:
            config = {**config, 'task_config': task_config}
        snapshot = self._write_snapshot_files(dataset_path, split_map, class_to_id, task_type, config)
        self._write_dataset_yaml(dataset_path, class_to_id, task_type, task_config.get('pose_template'))
        dataset_data_path = dataset_path if task_type == 'classify_single' else os.path.join(dataset_path, 'dataset.yaml')

        summary = self._version_summary(entries, source_count, classes)
        summary.update({
            'generated_images': snapshot['split_counts']['train_generated'],
            'final_image_count': snapshot['split_counts']['final_total'],
            'final_train_images': snapshot['split_counts']['train'],
        })
        payload = {
            'id': version_id,
            'source_type': 'live_dataset',
            'source_name': dataset_name,
            'source_ref': dataset_name,
            'version_name': config.get('version_name') or f'{dataset_name}-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
            'created_at': datetime.now().isoformat(),
            'class_to_id': class_to_id,
            'classes': classes,
            'task_type': task_type,
            'task_config': task_config,
            'split_config': config.get('split_config') or {'train': 70, 'val': 20, 'test': 10},
            'training_config': self._normalize_dataset_training_config(config, task_type),
            'preprocessing_config': snapshot['preprocessing_config'],
            'augmentation_config': snapshot['augmentation_config'],
            'storage_path': version_dir,
            'dataset_yaml': dataset_data_path,
            'split_counts': snapshot['split_counts'],
            'summary': summary,
        }
        self._write_json(self._version_meta_path(version_id), payload)
        return payload

    def _parse_dataset_yaml_names(self, raw: str) -> dict[int, str]:
        names: dict[int, str] = {}
        in_names = False
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('names:'):
                in_names = True
                continue
            if not in_names or ':' not in stripped:
                continue
            key, value = stripped.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key.isdigit() and value:
                names[int(key)] = value
        return names

    def _parse_dataset_yaml_list(self, raw: str, key: str) -> list | None:
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped.startswith(f'{key}:'):
                continue
            value = stripped.split(':', 1)[1].strip()
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                return None
            return parsed if isinstance(parsed, list) else None
        return None

    def _validate_label_text(self, raw: str, task_type: str, image_name: str, classes: list[str], pose_template: dict | None = None) -> int:
        count = 0
        pose_kpts = int(((pose_template or {}).get('kpt_shape') or [0])[0] or 0)
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            try:
                cls_id = int(float(parts[0]))
                values = [float(value) for value in parts[1:]]
            except (IndexError, TypeError, ValueError) as exc:
                raise ValueError(f'Invalid label row for {image_name}') from exc
            if cls_id < 0 or cls_id >= len(classes):
                raise ValueError(f'Invalid class id in label for {image_name}')
            if task_type == 'segment':
                if len(parts) < 7 or len(values) % 2 != 0:
                    raise ValueError(f'Segmentation labels for {image_name} must use polygon format')
            elif task_type == 'pose':
                expected_values = 4 + pose_kpts * 3 if pose_kpts else None
                if len(values) < 7 or (len(values) - 4) % 3 != 0 or (expected_values and len(values) != expected_values):
                    raise ValueError(f'Pose labels for {image_name} must use bbox plus keypoint format')
            elif len(parts) != 5:
                raise ValueError(f'Detection labels for {image_name} must use bbox format')
            count += 1
        if count <= 0:
            raise ValueError(f'Label for {image_name} has no annotations')
        return count

    def _detections_from_yolo_label(self, raw: str, task_type: str, image_name: str, classes: list[str], width: int, height: int, pose_template: dict | None = None) -> list[dict]:
        detections = []
        keypoint_names = (pose_template or {}).get('keypoint_names') or []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            cls_id = int(float(parts[0]))
            label = classes[cls_id]
            values = [float(value) for value in parts[1:]]
            if task_type == 'segment':
                if len(values) < 6 or len(values) % 2 != 0:
                    raise ValueError(f'Segmentation labels for {image_name} must use polygon format')
                mask = [[values[i] * width, values[i + 1] * height] for i in range(0, len(values), 2)]
                box = self._derive_box_from_mask(mask, width, height)
                if box:
                    detections.append({'label': label, 'box': box, 'mask': mask})
            elif task_type == 'pose':
                if len(values) < 7 or (len(values) - 4) % 3 != 0:
                    raise ValueError(f'Pose labels for {image_name} must use bbox plus keypoint format')
                x_center, y_center, bw, bh = values[:4]
                box = [
                    (x_center - bw / 2) * width,
                    (y_center - bh / 2) * height,
                    (x_center + bw / 2) * width,
                    (y_center + bh / 2) * height,
                ]
                box = self._clamp_box(box, width, height)
                if not box:
                    continue
                keypoints = []
                for index in range(4, len(values), 3):
                    kp_index = (index - 4) // 3
                    keypoints.append({
                        'name': keypoint_names[kp_index] if kp_index < len(keypoint_names) else f'kpt_{kp_index}',
                        'x': values[index] * width,
                        'y': values[index + 1] * height,
                        'visibility': 'missing' if int(values[index + 2]) == 0 else 'occluded' if int(values[index + 2]) == 1 else 'visible',
                    })
                detections.append({'label': label, 'box': box, 'keypoints': keypoints})
            else:
                if len(values) != 4:
                    raise ValueError(f'Detection labels for {image_name} must use bbox format')
                x_center, y_center, bw, bh = values
                box = [
                    (x_center - bw / 2) * width,
                    (y_center - bh / 2) * height,
                    (x_center + bw / 2) * width,
                    (y_center + bh / 2) * height,
                ]
                box = self._clamp_box(box, width, height)
                if box:
                    detections.append({'label': label, 'box': box})
        if not detections:
            raise ValueError(f'Label for {image_name} has no annotations')
        return detections

    def _classification_zip_entries(self, zf: zipfile.ZipFile, names: list[str]) -> tuple[list[dict], list[str], dict[str, int]]:
        entries = []
        used_filenames: set[str] = set()
        classes = sorted({
            parts[1]
            for name in names
            for parts in [name.split('/')]
            if len(parts) >= 3 and parts[0] in {'train', 'val', 'test'} and not name.endswith('/')
        })
        if not classes:
            raise ValueError('Classification export zip must use train/val/test class folders')
        class_to_id = {name: idx for idx, name in enumerate(classes)}
        for name in names:
            parts = name.split('/')
            if len(parts) < 3 or parts[0] not in {'train', 'val', 'test'} or name.endswith('/'):
                continue
            image_bytes = zf.read(name)
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f'Invalid image in export zip: {name}')
            height, width = image.shape[:2]
            label = parts[1]
            export_filename = self._unique_name(os.path.basename(name), used_filenames)
            entries.append({
                'subset': parts[0],
                'image_name': name,
                'export_filename': export_filename,
                'image_bytes': image_bytes,
                'width': width,
                'height': height,
                'label': label,
                'detections': [{'label': label, 'box': [0, 0, width, height]}],
            })
        if not entries:
            raise ValueError('Classification export zip contains no images')
        return entries, classes, class_to_id

    def _zip_dataset_entries(self, zip_bytes: bytes, task_type: str) -> tuple[list[dict], list[str], dict[str, int]]:
        used_filenames: set[str] = set()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            if task_type == 'classify_single':
                return self._classification_zip_entries(zf, names)
            yaml_name = next((name for name in names if name.endswith('dataset.yaml')), None)
            if yaml_name is None:
                raise ValueError('dataset.yaml not found in export zip')
            yaml_raw = zf.read(yaml_name).decode()
            class_names_map = self._parse_dataset_yaml_names(yaml_raw)
            if not class_names_map:
                raise ValueError('dataset.yaml names are required')
            classes = [class_names_map[idx] for idx in sorted(class_names_map)]
            class_to_id = {name: idx for idx, name in enumerate(classes)}
            pose_template = None
            if task_type == 'pose':
                kpt_shape = self._parse_dataset_yaml_list(yaml_raw, 'kpt_shape')
                flip_idx = self._parse_dataset_yaml_list(yaml_raw, 'flip_idx')
                if not kpt_shape:
                    raise ValueError('Pose dataset.yaml must define kpt_shape')
                pose_template = {
                    'kpt_shape': kpt_shape,
                    'flip_idx': flip_idx or list(range(int(kpt_shape[0]))),
                    'keypoint_names': [f'kpt_{index}' for index in range(int(kpt_shape[0]))],
                }
            entries = []
            for subset in ('train', 'val', 'test'):
                prefix = f'images/{subset}/'
                image_names = [name for name in names if name.startswith(prefix) and not name.endswith('/')]
                for image_name in image_names:
                    label_name = f'labels/{subset}/{Path(image_name).stem}.txt'
                    if label_name not in names:
                        raise ValueError(f'Missing label for {image_name}')
                    image_bytes = zf.read(image_name)
                    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if image is None:
                        raise ValueError(f'Invalid image in export zip: {image_name}')
                    height, width = image.shape[:2]
                    label_raw = zf.read(label_name).decode()
                    self._validate_label_text(label_raw, task_type, image_name, classes, pose_template)
                    detections = self._detections_from_yolo_label(label_raw, task_type, image_name, classes, width, height, pose_template)
                    export_filename = self._unique_name(os.path.basename(image_name), used_filenames)
                    entries.append({
                        'subset': subset,
                        'image_name': image_name,
                        'label_name': label_name,
                        'export_filename': export_filename,
                        'image_bytes': image_bytes,
                        'width': width,
                        'height': height,
                        'detections': detections,
                        'task_config': {'pose_template': pose_template} if pose_template else {},
                    })
        if not entries:
            raise ValueError('Export zip contains no labeled images')
        return entries, classes, class_to_id

    def create_dataset_version_from_zip(self, zip_bytes: bytes, source_name: str, config: dict) -> dict:
        task_type = self._task_type(config)
        entries, classes, class_to_id = self._zip_dataset_entries(zip_bytes, task_type)
        split_mode = config.get('split_mode', 'existing')
        if split_mode == 'existing':
            split_map = {'train': [], 'val': [], 'test': []}
            for entry in entries:
                split_map[entry['subset']].append(entry)
        else:
            normalized = [dict(entry, subset=None) for entry in entries]
            split_map = self._assign_splits(normalized, {'split_config': config.get('split_config') or {'train': 70, 'val': 20, 'test': 10}})

        version_id = uuid.uuid4().hex
        version_dir = self._version_dir(version_id)
        dataset_path = os.path.join(version_dir, 'dataset')
        task_config = next((entry.get('task_config') for entry in entries if entry.get('task_config')), {})
        if task_config:
            config = {**config, 'task_config': task_config}
        snapshot = self._write_snapshot_files(dataset_path, split_map, class_to_id, task_type, config)
        self._write_dataset_yaml(dataset_path, class_to_id, task_type, task_config.get('pose_template'))
        dataset_data_path = dataset_path if task_type == 'classify_single' else os.path.join(dataset_path, 'dataset.yaml')

        summary = self._version_summary(entries, len(entries), classes)
        summary.update({
            'generated_images': snapshot['split_counts']['train_generated'],
            'final_image_count': snapshot['split_counts']['final_total'],
            'final_train_images': snapshot['split_counts']['train'],
        })
        payload = {
            'id': version_id,
            'source_type': 'export_zip',
            'source_name': source_name,
            'source_ref': source_name,
            'version_name': config.get('version_name') or f'{Path(source_name).stem}-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
            'created_at': datetime.now().isoformat(),
            'class_to_id': class_to_id,
            'classes': classes,
            'task_type': task_type,
            'task_config': task_config,
            'split_config': config.get('split_config') or {'train': 70, 'val': 20, 'test': 10},
            'training_config': self._normalize_dataset_training_config(config, task_type),
            'preprocessing_config': snapshot['preprocessing_config'],
            'augmentation_config': snapshot['augmentation_config'],
            'storage_path': version_dir,
            'dataset_yaml': dataset_data_path,
            'split_counts': snapshot['split_counts'],
            'summary': summary,
        }
        self._write_json(self._version_meta_path(version_id), payload)
        return payload

    def preview_dataset_policy(self, config: dict) -> dict:
        task_type = self._task_type(config)
        source_type = config.get('source_type', 'live')
        if source_type == 'zip':
            zip_bytes = config.get('zip_bytes')
            if not zip_bytes:
                raise ValueError('zip file is required for zip preview')
            entries, classes, _class_to_id = self._zip_dataset_entries(zip_bytes, task_type)
            source_name = config.get('source_name') or 'export zip'
        else:
            dataset_name = config.get('dataset_name')
            if not dataset_name:
                raise ValueError('dataset_name is required')
            entries, _source_count, classes = self._live_dataset_entries(dataset_name, task_type)
            source_name = dataset_name
        augmentation_config = self._normalize_augmentation_config(config)
        preprocessing_config = self._normalize_preprocessing_config(config)
        samples = []
        for entry in entries[:3]:
            image = self._read_entry_image(entry)
            detections = self._sanitize_detections(entry['detections'], image.shape[1], image.shape[0], task_type)
            preprocessed_image, preprocessed_detections = self._preprocess_entry_image(image, detections, preprocessing_config, task_type)
            aug_image, aug_detections = self._augment_entry(preprocessed_image, preprocessed_detections, augmentation_config, task_type, force=True)
            samples.append({
                'filename': entry['export_filename'],
                'original': self._encode_preview(image, detections),
                'preprocessed': self._encode_preview(preprocessed_image, preprocessed_detections),
                'augmented': self._encode_preview(aug_image, aug_detections),
            })
        return {
            'source_type': source_type,
            'source_name': source_name,
            'task_type': task_type,
            'classes': classes,
            'preprocessing_config': preprocessing_config,
            'augmentation_config': augmentation_config,
            'samples': samples,
        }

    def estimate_training(self, version_id: str, config: dict) -> dict:
        version = self.get_dataset_version(version_id)
        images = int(version['summary'].get('final_image_count') or version['summary']['usable_labeled_images'])
        epochs = int(config.get('epochs', 50))
        imgsz = int(config.get('imgsz', 640))
        size = config.get('size', 'n')
        scale = {'n': 1.0, 's': 1.4, 'm': 2.0, 'l': 2.8}.get(size, 1.0)
        minutes = max(2, int(images * epochs * scale * max(imgsz / 640, 1) / 80))
        return {
            'dataset_version_id': version_id,
            'estimated_disk_usage_mb': max(64, images * 2),
            'estimated_vram_tier': 'high' if size in {'m', 'l'} else 'medium',
            'estimated_time_range_minutes': [minutes, int(minutes * 1.6)],
            'family': config.get('family', 'yolo11'),
            'size': size,
            'task_type': version.get('task_type', 'detect'),
        }

    def recommend_training_settings(self, version_id: str, config: dict | None = None) -> dict:
        version = self.get_dataset_version(version_id)
        images = int(version['summary'].get('final_image_count') or version['summary'].get('usable_labeled_images') or 0)
        if images < 50:
            epochs, patience, reason = 200, 40, 'Very small dataset; use a higher epoch cap with early stopping.'
        elif images < 100:
            epochs, patience, reason = 150, 30, 'Small dataset; allow extra passes while early stopping controls overfit.'
        elif images < 500:
            epochs, patience, reason = 100, 25, 'Medium dataset; balanced epoch cap with early stopping.'
        else:
            epochs, patience, reason = 75, 20, 'Larger dataset; lower epoch cap is usually enough with early stopping.'
        return {
            'dataset_version_id': version_id,
            'image_count': images,
            'epochs': epochs,
            'patience': patience,
            'batch': -1,
            'imgsz': int((config or {}).get('imgsz') or 640),
            'augmentation_mode': 'basic',
            'reason': reason,
        }

    def _normalize_dataset_training_config(self, config: dict, task_type: str) -> dict:
        raw = config.get('training_config') if isinstance(config.get('training_config'), dict) else config
        family = raw.get('family', 'yolo11')
        if family not in TRAINING_FAMILIES:
            family = 'yolo11'
        size = raw.get('size', 'n')
        if size not in TRAINING_SIZES:
            size = 'n'
        mode = raw.get('training_mode', 'standard')
        if mode not in TRAINING_MODES:
            mode = 'standard'
        suffix = '-seg' if task_type == 'segment' else '-pose' if task_type == 'pose' else '-cls' if task_type == 'classify_single' else ''
        default_checkpoint = f"yolo11{size}{suffix}.pt" if family == 'yolo11' else f"yolo26{size}{suffix}.pt"

        def int_value(key: str, default: int, minimum: int, maximum: int) -> int:
            try:
                value = int(raw.get(key, default))
            except (TypeError, ValueError):
                value = default
            return min(max(value, minimum), maximum)

        try:
            batch = int(raw.get('batch', -1))
        except (TypeError, ValueError):
            batch = -1
        if batch != -1:
            batch = min(max(batch, 1), 128)

        return {
            'family': family,
            'size': size,
            'base_checkpoint': str(raw.get('base_checkpoint') or default_checkpoint).strip() or default_checkpoint,
            'epochs': int_value('epochs', 50, 1, 500),
            'patience': int_value('patience', 30, 0, 100),
            'imgsz': int_value('imgsz', 640, 320, 2048),
            'batch': batch,
            'workers': int_value('workers', 2, 0, 16),
            'training_mode': mode,
        }

    def _validate_training_config(self, config: dict, version: dict) -> dict:
        try:
            epochs = int(config.get('epochs', 50))
            patience = int(config.get('patience', 30))
            imgsz = int(config.get('imgsz', 640))
            batch = int(config.get('batch', 8))
            workers = int(config.get('workers', 2))
        except (TypeError, ValueError) as exc:
            raise ValueError('epochs, patience, imgsz, batch, and workers must be integers') from exc
        if not 1 <= epochs <= 500:
            raise ValueError('epochs must be between 1 and 500')
        if not 0 <= patience <= 100:
            raise ValueError('patience must be between 0 and 100')
        if imgsz < 320 or imgsz > 2048 or imgsz % 32 != 0:
            raise ValueError('imgsz must be a multiple of 32 between 320 and 2048')
        if batch != -1 and not 1 <= batch <= 128:
            raise ValueError('batch must be -1 or between 1 and 128')
        if not 0 <= workers <= 16:
            raise ValueError('workers must be between 0 and 16')

        family = config.get('family', 'yolo11')
        if family not in TRAINING_FAMILIES:
            raise ValueError("family must be 'yolo11' or 'yolo26'")
        size = config.get('size', 'n')
        if size not in TRAINING_SIZES:
            raise ValueError("size must be one of 'n', 's', 'm', or 'l'")
        mode = config.get('training_mode', 'standard')
        if mode not in TRAINING_MODES:
            raise ValueError("training_mode must be 'standard' or 'high_speed'")

        base_checkpoint = str(config.get('base_checkpoint') or '').strip()
        if not base_checkpoint:
            raise ValueError('base_checkpoint is required')
        checkpoint_path = Path(base_checkpoint)
        if any(part == '..' for part in checkpoint_path.parts):
            raise ValueError('base_checkpoint must not contain parent directory traversal')
        if checkpoint_path.is_absolute() and not checkpoint_path.is_file():
            raise ValueError('absolute base_checkpoint must point to an existing file')

        task_type = version.get('task_type', self._task_type(config))
        requested_task = self._task_type(config) if config.get('task_type') else task_type
        if requested_task != task_type:
            raise ValueError('Training job task_type must match the Dataset Version task_type')

        return {
            'family': family,
            'size': size,
            'training_mode': mode,
            'epochs': epochs,
            'patience': patience,
            'imgsz': imgsz,
            'batch': batch,
            'workers': workers,
            'base_checkpoint': base_checkpoint,
            'task_type': task_type,
        }

    def _last_checkpoint_for_job(self, job: dict) -> str | None:
        explicit = job.get('last_checkpoint_path')
        if explicit and os.path.isfile(explicit):
            return explicit
        output_dir = job.get('output_dir')
        if not output_dir:
            return None
        candidate = os.path.join(output_dir, 'weights', 'last.pt')
        return candidate if os.path.isfile(candidate) else None

    def list_training_jobs(self) -> list[dict]:
        self._ensure_root()
        jobs = []
        for name in sorted(os.listdir(self._jobs_dir())):
            if name.endswith('.json'):
                jobs.append(self._read_json(os.path.join(self._jobs_dir(), name), {}))
        jobs.sort(key=lambda item: item.get('created_at', ''), reverse=True)
        return jobs

    def get_training_job(self, job_id: str) -> dict:
        job = self._read_json(self._job_path(job_id), {})
        if not job:
            raise FileNotFoundError(f'Training job {job_id} not found')
        return job

    def create_training_job(self, config: dict, inference_active: bool = False) -> dict:
        version = self.get_dataset_version(config['dataset_version_id'])
        validated = self._validate_training_config(config, version)
        task_type = validated['task_type']
        mode = validated['training_mode']
        if mode == 'high_speed' and inference_active:
            raise RuntimeError('Inference must be idle before starting High-Speed Mode training')
        job_id = uuid.uuid4().hex
        queue_position = sum(1 for job in self.list_training_jobs() if job.get('status') in {'queued', 'preparing', 'running'}) + 1
        output_slug = self._slugify(config.get('job_name', 'train-tune-job'), f'train-tune-{job_id[:8]}')
        output_dir = os.path.join(self._workspace_root(), f'{output_slug}-{job_id[:8]}')
        results_csv_path = os.path.join(output_dir, 'results.csv')
        train_log_path = os.path.join(output_dir, 'train.log')
        payload = {
            'id': job_id,
            'job_name': config.get('job_name', output_slug),
            'status': 'queued',
            'dataset_version_id': version['id'],
            'architecture_family': validated['family'],
            'architecture_size': validated['size'],
            'task_type': task_type,
            'base_checkpoint': validated['base_checkpoint'],
            'device_policy': 'dual_5080' if mode == 'high_speed' else 'second_5080',
            'training_mode': mode,
            'epochs': validated['epochs'],
            'patience': validated['patience'],
            'imgsz': validated['imgsz'],
            'batch': validated['batch'],
            'workers': validated['workers'],
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'finished_at': None,
            'queue_position': queue_position,
            'output_dir': output_dir,
            'train_log_path': train_log_path,
            'raw_results_csv_path': results_csv_path,
            'best_model_path': None,
            'last_checkpoint_path': None,
            'resume': bool(config.get('resume', False)),
            'resume_from_checkpoint': config.get('resume_from_checkpoint'),
            'amp': None,
            'cuda_device_order': None,
            'cuda_visible_devices': None,
            'train_device': None,
            'training_summary': version['summary'],
            'failure_reason': None,
            'metrics_latest': None,
            'dataset_version_name': version['version_name'],
            'class_names': version['classes'],
        }
        self._write_json(self._job_path(job_id), payload)
        self._write_json(self._metrics_path(job_id), [])
        return payload

    def update_training_job(self, job_id: str, **updates) -> dict:
        with self._lock:
            job = self.get_training_job(job_id)
            job.update(updates)
            self._write_json(self._job_path(job_id), job)
            return job

    def append_metric(self, job_id: str, metric: dict) -> dict:
        metric = self._sanitize_json_value(metric)
        metrics = self._read_json(self._metrics_path(job_id), [])
        metrics.append(metric)
        self._write_json(self._metrics_path(job_id), metrics)
        self.update_training_job(job_id, metrics_latest=metric)
        return metric

    def list_training_metrics(self, job_id: str) -> list[dict]:
        return self._read_json(self._metrics_path(job_id), [])

    def cancel_training_job(self, job_id: str) -> dict:
        return self.update_training_job(job_id, status='cancelled', finished_at=datetime.now().isoformat())

    def delete_training_job(self, job_id: str) -> None:
        job = self.get_training_job(job_id)
        if job.get('status') != 'failed':
            raise RuntimeError('Only failed training jobs can be deleted')
        output_dir = job.get('output_dir')
        if output_dir and os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        for path in (self._job_path(job_id), self._metrics_path(job_id)):
            if os.path.exists(path):
                os.remove(path)

    def recompute_training_job(self, job_id: str, inference_active: bool = False) -> dict:
        job = self.get_training_job(job_id)
        if job.get('status') != 'failed':
            raise RuntimeError('Only failed training jobs can be re-computed')
        return self.create_training_job(
            {
                'job_name': job.get('job_name') or 'train-tune-job',
                'dataset_version_id': job['dataset_version_id'],
                'family': job.get('architecture_family', 'yolo11'),
                'size': job.get('architecture_size', 'n'),
                'base_checkpoint': job.get('base_checkpoint', ''),
                'epochs': job.get('epochs', 50),
                'patience': job.get('patience', 30),
                'imgsz': job.get('imgsz', 640),
                'batch': job.get('batch', 8),
                'workers': job.get('workers', 2),
                'training_mode': job.get('training_mode', 'standard'),
                'task_type': job.get('task_type', 'detect'),
            },
            inference_active=inference_active,
        )

    def resume_training_job(self, job_id: str, inference_active: bool = False) -> dict:
        job = self.get_training_job(job_id)
        if job.get('status') not in {'failed', 'cancelled'}:
            raise RuntimeError('Only failed or cancelled training jobs can be resumed')
        last_checkpoint = self._last_checkpoint_for_job(job)
        if not last_checkpoint:
            raise RuntimeError('A last checkpoint is required before a training job can be resumed')
        return self.create_training_job(
            {
                'job_name': job.get('job_name') or 'train-tune-job',
                'dataset_version_id': job['dataset_version_id'],
                'family': job.get('architecture_family', 'yolo11'),
                'size': job.get('architecture_size', 'n'),
                'base_checkpoint': last_checkpoint,
                'epochs': job.get('epochs', 50),
                'patience': job.get('patience', 30),
                'imgsz': job.get('imgsz', 640),
                'batch': job.get('batch', 8),
                'workers': job.get('workers', 2),
                'training_mode': job.get('training_mode', 'standard'),
                'task_type': job.get('task_type', 'detect'),
                'resume': True,
                'resume_from_checkpoint': last_checkpoint,
            },
            inference_active=inference_active,
        )

    def mark_interrupted_jobs_failed(self) -> int:
        count = 0
        for job in self.list_training_jobs():
            if job.get('status') in {'preparing', 'running'}:
                self.fail_training_job(job['id'], 'interrupted by server restart')
                count += 1
        return count

    def fail_training_job(self, job_id: str, reason: str) -> dict:
        return self.update_training_job(job_id, status='failed', failure_reason=reason, finished_at=datetime.now().isoformat())

    def complete_training_job(
        self,
        job_id: str,
        best_model_path: str,
        last_checkpoint_path: str | None = None,
        metrics_best: dict | None = None,
    ) -> dict:
        job = self.get_training_job(job_id)
        metrics = self.list_training_metrics(job_id)
        selected_metrics_best = _sanitize_json_value(metrics_best) if metrics_best else _select_best_metric(
            metrics,
            job.get('task_type', 'detect'),
        )
        job = self.update_training_job(
            job_id,
            status='completed',
            best_model_path=best_model_path,
            last_checkpoint_path=last_checkpoint_path or best_model_path,
            finished_at=datetime.now().isoformat(),
            metrics_best=selected_metrics_best,
        )
        model_id = uuid.uuid4().hex
        model_payload = {
            'id': model_id,
            'model_name': job['job_name'],
            'version_name': f"{job['job_name']}-v1",
            'job_id': job_id,
            'dataset_version_id': job['dataset_version_id'],
            'family': job['architecture_family'],
            'size': job['architecture_size'],
            'task_type': job.get('task_type', 'detect'),
            'best_model_path': best_model_path,
            'class_names': job.get('class_names', []),
            'metrics_best': job.get('metrics_best') or job.get('metrics_latest'),
            'created_at': datetime.now().isoformat(),
            'status': 'ready',
        }
        self._write_json(self._model_path(model_id), model_payload)
        return job

    def list_model_versions(self) -> list[dict]:
        self._ensure_root()
        models = []
        for name in sorted(os.listdir(self._models_dir())):
            if name.endswith('.json'):
                models.append(self._read_json(os.path.join(self._models_dir(), name), {}))
        models.sort(key=lambda item: item.get('created_at', ''), reverse=True)
        return models

    def get_model_version(self, model_id: str) -> dict:
        model = self._read_json(self._model_path(model_id), {})
        if not model:
            raise FileNotFoundError(f'Model version {model_id} not found')
        return model

    def delete_model_version(self, model_id: str) -> None:
        model = self.get_model_version(model_id)
        job_id = model.get('job_id')
        job = self._read_json(self._job_path(job_id), {}) if job_id else {}
        output_dir = job.get('output_dir')
        if output_dir and os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        if job_id:
            for path in (self._job_path(job_id), self._metrics_path(job_id)):
                if os.path.exists(path):
                    os.remove(path)
        model_path = self._model_path(model_id)
        if os.path.exists(model_path):
            os.remove(model_path)


training_service = TrainingService()
