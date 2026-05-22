import argparse
import csv
import json
import os
import sys
import threading
import time
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


def metric_value(row: dict, keys: list[str]) -> float:
    for key in keys:
        if key in row and row[key] not in ('', None):
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return 0.0


def actual_train(job: dict, version: dict):
    from ultralytics import YOLO

    output_dir = Path(job['output_dir'])
    project = str(output_dir.parent)
    name = output_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    results_csv = output_dir / 'results.csv'
    state = {'done': False, 'error': None}

    device = os.getenv('TRAIN_DEVICE_STANDARD', '1')
    if job.get('training_mode') == 'high_speed':
        device = os.getenv('TRAIN_DEVICE_HIGH_SPEED', '0,1')

    def train_runner():
        try:
            model = YOLO(job['base_checkpoint'])
            model.train(
                data=version['dataset_yaml'],
                epochs=int(job.get('epochs', 50)),
                imgsz=int(job.get('imgsz', 640)),
                batch=int(job.get('batch', 8)),
                workers=int(job.get('workers', 2)),
                project=project,
                name=name,
                exist_ok=True,
                device=device,
                verbose=False,
            )
        except Exception as exc:  # pragma: no cover - runtime path
            state['error'] = str(exc)
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
                    'train_loss': metric_value(row, ['train/box_loss', 'train/loss']),
                    'val_loss': metric_value(row, ['val/box_loss', 'val/loss']),
                    'map50': metric_value(row, ['metrics/mAP50(B)', 'metrics/mAP50']),
                    'map50_95': metric_value(row, ['metrics/mAP50-95(B)', 'metrics/mAP50-95']),
                    'precision': metric_value(row, ['metrics/precision(B)', 'metrics/precision']),
                    'recall': metric_value(row, ['metrics/recall(B)', 'metrics/recall']),
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
        emit({'event': 'job_failed', 'error': str(exc)})
        sys.exit(1)
