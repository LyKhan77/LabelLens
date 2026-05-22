import io
import json
import os
import random
import re
import shutil
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from backend.services.dataset import DATASETS_DIR, DatasetService, dataset_service

TRAIN_TUNE_DIR = os.path.join(DATASETS_DIR, '_train_tune')


class TrainingService:
    def __init__(self, dataset_service_instance: DatasetService | None = None):
        self.dataset_service = dataset_service_instance or dataset_service
        self._lock = threading.Lock()
        self._ensure_root()

    def _ensure_root(self):
        for path in (
            self._root(),
            self._versions_dir(),
            self._jobs_dir(),
            self._metrics_dir(),
            self._models_dir(),
        ):
            os.makedirs(path, exist_ok=True)

    def _root(self) -> str:
        return TRAIN_TUNE_DIR

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
            return json.load(f)

    def _write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2)

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

    def _build_yolo_lines(self, detections: list[dict], class_to_id: dict[str, int], width: int, height: int) -> str:
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
            lines.append(f'{cls_id} {x_center:.6f} {y_center:.6f} {bw:.6f} {bh:.6f}')
        return '\n'.join(lines)

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

    def _write_dataset_yaml(self, dataset_path: str, class_to_id: dict[str, int]):
        names = {v: k for k, v in class_to_id.items()}
        lines = [
            f'path: {dataset_path}',
            'train: images/train',
            'val: images/val',
            'test: images/test',
            'names:',
        ]
        for cid, cname in sorted(names.items()):
            lines.append(f'  {cid}: {cname}')
        Path(dataset_path, 'dataset.yaml').write_text('\n'.join(lines) + '\n')

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

    def list_dataset_versions(self) -> list[dict]:
        self._ensure_root()
        versions = []
        for name in sorted(os.listdir(self._versions_dir())):
            meta_path = self._version_meta_path(name)
            if os.path.isfile(meta_path):
                versions.append(self._read_json(meta_path, {}))
        return versions

    def get_dataset_version(self, version_id: str) -> dict:
        payload = self._version_payload(version_id)
        if not payload:
            raise FileNotFoundError(f'Dataset version {version_id} not found')
        return payload

    def create_dataset_version_from_live_dataset(self, dataset_name: str, config: dict) -> dict:
        pdir = self.dataset_service._project_dir(dataset_name)
        ann_dir = os.path.join(pdir, 'annotations')
        img_dir = os.path.join(pdir, 'images')
        if not os.path.isdir(ann_dir):
            raise FileNotFoundError(f"Dataset '{dataset_name}' not found")

        entries = []
        used_filenames: set[str] = set()
        class_names: set[str] = set()
        all_annotation_files = [f for f in sorted(os.listdir(ann_dir)) if f.endswith('.json')]
        for fname in all_annotation_files:
            ann = self._read_json(os.path.join(ann_dir, fname), {})
            detections = [d for d in ann.get('detections', []) if d.get('accepted', True)]
            if not detections:
                continue
            image_name = ann.get('image')
            image_path = os.path.join(img_dir, image_name)
            if not os.path.isfile(image_path):
                continue
            export_filename = self._unique_name(ann.get('original_filename') or image_name, used_filenames)
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

        classes = sorted(class_names)
        class_to_id = {name: idx for idx, name in enumerate(classes)}
        split_map = self._assign_splits(entries, config)
        version_id = uuid.uuid4().hex
        version_dir = self._version_dir(version_id)
        dataset_path = os.path.join(version_dir, 'dataset')
        for subset in ('train', 'val', 'test'):
            os.makedirs(os.path.join(dataset_path, 'images', subset), exist_ok=True)
            os.makedirs(os.path.join(dataset_path, 'labels', subset), exist_ok=True)
            for entry in split_map[subset]:
                shutil.copy2(entry['image_path'], os.path.join(dataset_path, 'images', subset, entry['export_filename']))
                label_name = f"{os.path.splitext(entry['export_filename'])[0]}.txt"
                Path(dataset_path, 'labels', subset, label_name).write_text(
                    self._build_yolo_lines(entry['detections'], class_to_id, entry['width'], entry['height']) + '\n'
                )
        self._write_dataset_yaml(dataset_path, class_to_id)

        split_counts = {subset: len(items) for subset, items in split_map.items()}
        primary = next((subset for subset in ('train', 'val', 'test') if split_counts[subset] > 0), 'train')
        split_counts['primary'] = primary
        payload = {
            'id': version_id,
            'source_type': 'live_dataset',
            'source_name': dataset_name,
            'source_ref': dataset_name,
            'version_name': config.get('version_name') or f'{dataset_name}-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
            'created_at': datetime.now().isoformat(),
            'class_to_id': class_to_id,
            'classes': classes,
            'split_config': config.get('split_config') or {'train': 70, 'val': 20, 'test': 10},
            'preprocessing_config': config.get('preprocessing_config') or {},
            'augmentation_config': config.get('augmentation_config') or {'profile': 'baseline'},
            'storage_path': version_dir,
            'dataset_yaml': os.path.join(dataset_path, 'dataset.yaml'),
            'split_counts': split_counts,
            'summary': self._version_summary(entries, len(all_annotation_files), classes),
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

    def create_dataset_version_from_zip(self, zip_bytes: bytes, source_name: str, config: dict) -> dict:
        version_id = uuid.uuid4().hex
        version_dir = self._version_dir(version_id)
        dataset_path = os.path.join(version_dir, 'dataset')
        os.makedirs(dataset_path, exist_ok=True)

        used_filenames: set[str] = set()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            yaml_name = next((name for name in names if name.endswith('dataset.yaml')), None)
            if yaml_name is None:
                raise ValueError('dataset.yaml not found in export zip')
            yaml_raw = zf.read(yaml_name).decode()
            class_names_map = self._parse_dataset_yaml_names(yaml_raw)
            if not class_names_map:
                raise ValueError('dataset.yaml names are required')
            classes = [class_names_map[idx] for idx in sorted(class_names_map)]
            class_to_id = {name: idx for idx, name in enumerate(classes)}

            entries = []
            for subset in ('train', 'val', 'test'):
                prefix = f'images/{subset}/'
                image_names = [name for name in names if name.startswith(prefix) and not name.endswith('/')]
                for image_name in image_names:
                    label_name = f'labels/{subset}/{Path(image_name).stem}.txt'
                    if label_name not in names:
                        raise ValueError(f'Missing label for {image_name}')
                    export_filename = self._unique_name(os.path.basename(image_name), used_filenames)
                    entries.append({
                        'subset': subset,
                        'image_name': image_name,
                        'label_name': label_name,
                        'export_filename': export_filename,
                        'detections': [{'label': classes[0]}],
                    })

            if not entries:
                raise ValueError('Export zip contains no labeled images')

            split_mode = config.get('split_mode', 'existing')
            if split_mode == 'existing':
                split_map = {'train': [], 'val': [], 'test': []}
                for entry in entries:
                    split_map[entry['subset']].append(entry)
            else:
                normalized = [dict(entry, subset=None) for entry in entries]
                split_map = self._assign_splits(normalized, {'split_config': config.get('split_config') or {'train': 70, 'val': 20, 'test': 10}})

            for subset in ('train', 'val', 'test'):
                os.makedirs(os.path.join(dataset_path, 'images', subset), exist_ok=True)
                os.makedirs(os.path.join(dataset_path, 'labels', subset), exist_ok=True)
                for entry in split_map[subset]:
                    image_target = os.path.join(dataset_path, 'images', subset, entry['export_filename'])
                    with zf.open(entry['image_name']) as src, open(image_target, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    label_filename = f"{Path(entry['export_filename']).stem}.txt"
                    label_target = os.path.join(dataset_path, 'labels', subset, label_filename)
                    with zf.open(entry['label_name']) as src, open(label_target, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

        self._write_dataset_yaml(dataset_path, class_to_id)
        split_counts = {subset: len(items) for subset, items in split_map.items()}
        primary = next((subset for subset in ('train', 'val', 'test') if split_counts[subset] > 0), 'train')
        split_counts['primary'] = primary
        payload = {
            'id': version_id,
            'source_type': 'export_zip',
            'source_name': source_name,
            'source_ref': source_name,
            'version_name': config.get('version_name') or f'{Path(source_name).stem}-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
            'created_at': datetime.now().isoformat(),
            'class_to_id': class_to_id,
            'classes': classes,
            'split_config': config.get('split_config') or {'train': 70, 'val': 20, 'test': 10},
            'preprocessing_config': config.get('preprocessing_config') or {},
            'augmentation_config': config.get('augmentation_config') or {'profile': 'baseline'},
            'storage_path': version_dir,
            'dataset_yaml': os.path.join(dataset_path, 'dataset.yaml'),
            'split_counts': split_counts,
            'summary': {
                'original_file_count': len(entries),
                'usable_labeled_images': len(entries),
                'total_annotations': len(entries),
                'class_count': len(classes),
                'classes': classes,
                'average_annotations_per_image': 1,
            },
        }
        self._write_json(self._version_meta_path(version_id), payload)
        return payload

    def estimate_training(self, version_id: str, config: dict) -> dict:
        version = self.get_dataset_version(version_id)
        images = version['summary']['usable_labeled_images']
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
        }

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
        mode = config.get('training_mode', 'standard')
        if mode == 'high_speed' and inference_active:
            raise RuntimeError('Inference must be idle before starting High-Speed Mode training')
        job_id = uuid.uuid4().hex
        queue_position = sum(1 for job in self.list_training_jobs() if job.get('status') in {'queued', 'preparing', 'running'}) + 1
        output_slug = self._slugify(config.get('job_name', 'train-tune-job'), f'train-tune-{job_id[:8]}')
        output_dir = os.path.join(self._root(), 'runs', output_slug)
        payload = {
            'id': job_id,
            'job_name': config.get('job_name', output_slug),
            'status': 'queued',
            'dataset_version_id': version['id'],
            'architecture_family': config.get('family', 'yolo11'),
            'architecture_size': config.get('size', 'n'),
            'task_type': 'detect',
            'base_checkpoint': config.get('base_checkpoint', ''),
            'device_policy': 'dual_5080' if mode == 'high_speed' else 'second_5080',
            'training_mode': mode,
            'epochs': int(config.get('epochs', 50)),
            'imgsz': int(config.get('imgsz', 640)),
            'batch': int(config.get('batch', 8)),
            'workers': int(config.get('workers', 2)),
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'finished_at': None,
            'queue_position': queue_position,
            'output_dir': output_dir,
            'best_model_path': None,
            'last_checkpoint_path': None,
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
        metrics = self._read_json(self._metrics_path(job_id), [])
        metrics.append(metric)
        self._write_json(self._metrics_path(job_id), metrics)
        self.update_training_job(job_id, metrics_latest=metric)
        return metric

    def list_training_metrics(self, job_id: str) -> list[dict]:
        return self._read_json(self._metrics_path(job_id), [])

    def cancel_training_job(self, job_id: str) -> dict:
        return self.update_training_job(job_id, status='cancelled', finished_at=datetime.now().isoformat())

    def fail_training_job(self, job_id: str, reason: str) -> dict:
        return self.update_training_job(job_id, status='failed', failure_reason=reason, finished_at=datetime.now().isoformat())

    def complete_training_job(self, job_id: str, best_model_path: str, last_checkpoint_path: str | None = None) -> dict:
        job = self.update_training_job(
            job_id,
            status='completed',
            best_model_path=best_model_path,
            last_checkpoint_path=last_checkpoint_path or best_model_path,
            finished_at=datetime.now().isoformat(),
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
            'best_model_path': best_model_path,
            'class_names': job.get('class_names', []),
            'metrics_best': job.get('metrics_latest'),
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


training_service = TrainingService()
