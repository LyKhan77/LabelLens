import argparse
import csv
import json
import math
import os
import sys
import threading
import time
import traceback
from pathlib import Path


def emit(event: dict):
    print(json.dumps(event), flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-json', required=True)
    parser.add_argument('--version-json', required=True)
    return parser.parse_args()


def read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def emit_traceback(exc: Exception, context: str):
    emit({'event': 'log_line', 'line': f'[{context}] {exc}'})
    for line in traceback.format_exc().strip().splitlines():
        emit({'event': 'log_line', 'line': line})


def simulate(job: dict):
    epochs = max(1, int(job.get('epochs', 1)))
    output_dir = Path(job['output_dir'])
    weights_dir = output_dir / 'weights'
    weights_dir.mkdir(parents=True, exist_ok=True)
    emit({'event': 'job_started', 'phase': 'running'})
    for epoch in range(1, epochs + 1):
        time.sleep(0.2)
        metric = {
            'event': 'metric_update',
            'epoch': epoch,
            'total_epochs': epochs,
            'train_loss': round(max(0.05, 1.0 / epoch), 4),
            'val_loss': round(max(0.04, 0.8 / epoch), 4),
            'map50': round(min(0.95, 0.45 + epoch * 0.03), 4),
            'map50_95': round(min(0.9, 0.3 + epoch * 0.025), 4),
            'precision': round(min(0.98, 0.5 + epoch * 0.025), 4),
            'recall': round(min(0.96, 0.45 + epoch * 0.024), 4),
            'lr': round(max(1e-5, 0.001 * (1 - epoch / (epochs + 1))), 6),
            'time_per_epoch_sec': 0.2,
            'elapsed_sec': round(epoch * 0.2, 2),
            'eta_sec': round((epochs - epoch) * 0.2, 2),
        }
        emit(metric)
    best_path = weights_dir / 'best.pt'
    last_path = weights_dir / 'last.pt'
    best_path.write_bytes(b'mock-best-model')
    last_path.write_bytes(b'mock-last-model')
    emit({'event': 'checkpoint_saved', 'path': str(best_path)})
    emit({'event': 'job_completed', 'best_model_path': str(best_path), 'last_checkpoint_path': str(last_path)})


ONLINE_AUGMENTATION_KEYS = {
    'hsv_h', 'hsv_s', 'hsv_v', 'degrees', 'translate', 'scale', 'shear', 'perspective',
    'flipud', 'fliplr', 'bgr', 'mosaic', 'mixup', 'copy_paste', 'erasing', 'close_mosaic',
}


def _local_device_arg(cuda_visible_devices: str) -> str:
    devices = [device.strip() for device in cuda_visible_devices.split(',') if device.strip()]
    return ','.join(str(index) for index in range(len(devices))) or '0'


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}


def resolve_training_device_policy(job: dict) -> dict:
    high_speed = job.get('training_mode') == 'high_speed'
    visible_key = 'TRAIN_VISIBLE_DEVICES_HIGH_SPEED' if high_speed else 'TRAIN_VISIBLE_DEVICES_STANDARD'
    local_key = 'TRAIN_DEVICE_HIGH_SPEED' if high_speed else 'TRAIN_DEVICE_STANDARD'
    amp_key = 'TRAIN_AMP_HIGH_SPEED' if high_speed else 'TRAIN_AMP_STANDARD'
    visible_default = '1,2' if high_speed else '1'
    cuda_visible_devices = os.getenv(visible_key, visible_default)
    return {
        'cuda_device_order': os.getenv('CUDA_DEVICE_ORDER', 'PCI_BUS_ID'),
        'cuda_visible_devices': cuda_visible_devices,
        'device': os.getenv(local_key, cuda_visible_devices),
        'local_device': _local_device_arg(cuda_visible_devices),
        'amp': _env_bool(amp_key, not high_speed),
    }


def apply_training_device_policy(policy: dict):
    os.environ['CUDA_DEVICE_ORDER'] = policy['cuda_device_order']
    os.environ['CUDA_VISIBLE_DEVICES'] = policy['cuda_visible_devices']


DDP_FIND_UNUSED_PATCH = """
    import torch.nn as nn
    _labellens_ddp = nn.parallel.DistributedDataParallel

    def _labellens_ddp_find_unused(*args, **kwargs):
        kwargs.setdefault("find_unused_parameters", True)
        return _labellens_ddp(*args, **kwargs)

    nn.parallel.DistributedDataParallel = _labellens_ddp_find_unused
"""


def _inject_ddp_find_unused_patch(content: str) -> str:
    marker = 'if __name__ == "__main__":'
    if 'find_unused_parameters' in content or marker not in content:
        return content
    return content.replace(marker, f'{marker}\n{DDP_FIND_UNUSED_PATCH}', 1)


def patch_ultralytics_ddp_find_unused_parameters():
    try:
        import ultralytics.utils.dist as ultralytics_dist
    except ImportError:
        return

    original = ultralytics_dist.generate_ddp_file
    if getattr(original, '_labellens_find_unused_patch', False):
        return

    def generate_ddp_file_with_find_unused(trainer):
        path = original(trainer)
        with open(path, encoding='utf-8') as f:
            content = f.read()
        patched = _inject_ddp_find_unused_patch(content)
        if patched != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(patched)
        return path

    generate_ddp_file_with_find_unused._labellens_find_unused_patch = True
    ultralytics_dist.generate_ddp_file = generate_ddp_file_with_find_unused


def maybe_patch_ultralytics_ddp_find_unused_parameters():
    if not _env_bool('LABELLENS_TRAIN_DDP_FIND_UNUSED', False):
        emit({'event': 'log_line', 'line': 'DDP find_unused_parameters patch disabled'})
        return
    patch_ultralytics_ddp_find_unused_parameters()
    emit({'event': 'log_line', 'line': 'DDP find_unused_parameters patch enabled'})


def online_augmentation_args(version: dict) -> dict:
    config = version.get('augmentation_config') or {}
    online = config.get('online') or {}
    args = {}
    for key, value in online.items():
        if key not in ONLINE_AUGMENTATION_KEYS or value in (None, ''):
            continue
        try:
            args[key] = float(value)
        except (TypeError, ValueError):
            continue
    return args


def metric_value(row: dict, keys: list[str]) -> float:
    for key in keys:
        if key in row and row[key] not in ('', None):
            try:
                value = float(row[key])
                if math.isfinite(value):
                    return value
            except (TypeError, ValueError):
                continue
    return 0.0


def actual_train(job: dict, version: dict):
    policy = resolve_training_device_policy(job)
    apply_training_device_policy(policy)

    from ultralytics import YOLO
    maybe_patch_ultralytics_ddp_find_unused_parameters()

    output_dir = Path(job['output_dir'])
    project = str(output_dir.parent)
    name = output_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    results_csv = output_dir / 'results.csv'
    state = {'done': False, 'error': None}

    device = policy['device']
    torch = sys.modules.get('torch')
    cuda_devices = []
    cuda_device_count = 0
    if torch is not None:
        try:
            cuda_device_count = torch.cuda.device_count()
            if torch.cuda.is_available():
                cuda_devices = [torch.cuda.get_device_name(index) for index in range(cuda_device_count)]
        except Exception as exc:  # pragma: no cover - diagnostic fallback
            cuda_devices = [f'unavailable: {exc}']
    emit({
        'event': 'training_device_mapping',
        'cuda_device_order': policy['cuda_device_order'],
        'cuda_visible_devices': policy['cuda_visible_devices'],
        'device': device,
        'local_device': policy['local_device'],
        'amp': policy['amp'],
        'cuda_device_count': cuda_device_count,
        'cuda_devices': cuda_devices,
    })
    emit({'event': 'raw_results_csv_path', 'path': str(results_csv)})
    emit({
        'event': 'log_line',
        'line': (
            f"Training CUDA mapping: CUDA_DEVICE_ORDER={policy['cuda_device_order']} "
            f"CUDA_VISIBLE_DEVICES={policy['cuda_visible_devices']} "
            f"ultralytics_device={device} expected_local_device={policy['local_device']} "
            f"amp={policy['amp']} "
            f"visible_cuda_count={cuda_device_count} "
            f"visible_cuda_names={cuda_devices}"
        ),
    })

    def train_runner():
        try:
            checkpoint = job.get('resume_from_checkpoint') if job.get('resume') else job['base_checkpoint']
            model = YOLO(checkpoint)
            expected_task = job.get('task_type', 'detect')
            model_task = getattr(model, 'task', 'unknown')
            if model_task != expected_task:
                raise ValueError(f'Train Tune {expected_task} runs require a {expected_task} checkpoint; got {model_task} checkpoint.')
            train_args = {
                'data': version['dataset_yaml'],
                'epochs': int(job.get('epochs', 50)),
                'patience': int(job.get('patience', 30)),
                'imgsz': int(job.get('imgsz', 640)),
                'batch': int(job.get('batch', 8)),
                'workers': int(job.get('workers', 2)),
                'project': project,
                'name': name,
                'exist_ok': True,
                'device': device,
                'amp': policy['amp'],
                'verbose': False,
                **online_augmentation_args(version),
            }
            if job.get('resume'):
                train_args['resume'] = True
            model.train(**train_args)
        except Exception as exc:  # pragma: no cover - runtime path
            state['error'] = str(exc)
            emit_traceback(exc, 'train_runner')
        finally:
            state['done'] = True

    thread = threading.Thread(target=train_runner, daemon=True)
    thread.start()
    emit({'event': 'job_started', 'phase': 'running'})
    seen_epochs: set[int] = set()
    start = time.time()
    while not state['done']:
        if results_csv.is_file():
            with open(results_csv, newline='') as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                epoch = int(float(row.get('epoch', 0))) + 1
                if epoch in seen_epochs:
                    continue
                seen_epochs.add(epoch)
                metric = {
                    'event': 'metric_update',
                    'epoch': epoch,
                    'total_epochs': int(job.get('epochs', 50)),
                    'train_loss': metric_value(row, ['train/seg_loss', 'train/box_loss', 'train/loss']),
                    'val_loss': metric_value(row, ['val/seg_loss', 'val/box_loss', 'val/loss']),
                    'map50': metric_value(row, ['metrics/mAP50(M)', 'metrics/mAP50(B)', 'metrics/mAP50']),
                    'map50_95': metric_value(row, ['metrics/mAP50-95(M)', 'metrics/mAP50-95(B)', 'metrics/mAP50-95']),
                    'precision': metric_value(row, ['metrics/precision(M)', 'metrics/precision(B)', 'metrics/precision']),
                    'recall': metric_value(row, ['metrics/recall(M)', 'metrics/recall(B)', 'metrics/recall']),
                    'lr': metric_value(row, ['lr/pg0', 'lr/pg1', 'lr/pg2']),
                    'time_per_epoch_sec': round(max(0.0, (time.time() - start) / max(1, epoch)), 2),
                    'elapsed_sec': round(time.time() - start, 2),
                    'eta_sec': max(0.0, round(((time.time() - start) / max(1, epoch)) * (int(job.get('epochs', 50)) - epoch), 2)),
                }
                emit(metric)
        time.sleep(1.0)

    thread.join()
    if state['error']:
        emit({'event': 'job_failed', 'error': state['error']})
        return

    best_path = output_dir / 'weights' / 'best.pt'
    last_path = output_dir / 'weights' / 'last.pt'
    emit({'event': 'checkpoint_saved', 'path': str(best_path)})
    emit({'event': 'job_completed', 'best_model_path': str(best_path), 'last_checkpoint_path': str(last_path)})


def main():
    args = parse_args()
    job = read_json(args.job_json)
    version = read_json(args.version_json)
    if os.getenv('LABELLENS_TRAIN_TUNE_FAKE', '0') == '1' or job.get('base_checkpoint') == 'mock':
        simulate(job)
        return
    actual_train(job, version)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # pragma: no cover - worker protection
        emit_traceback(exc, 'worker')
        emit({'event': 'job_failed', 'error': str(exc)})
        sys.exit(1)
