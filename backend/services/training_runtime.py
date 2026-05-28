import json
import os
import subprocess
import threading
from datetime import datetime

from backend.services.activity import activity_service
from backend.services.training import training_service
from backend.services.training_events import training_event_hub
from backend.train_worker import resolve_training_device_policy


class TrainingRuntime:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._current_process: subprocess.Popen | None = None
        self._current_job_id: str | None = None

    def ensure_worker(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def notify_job_queued(self):
        self.ensure_worker()
        self._wake.set()

    def cancel_job(self, job_id: str):
        training_service.cancel_training_job(job_id)
        training_event_hub.publish(job_id, {'event': 'job_cancelled'})
        with self._lock:
            if self._current_job_id == job_id and self._current_process is not None:
                self._current_process.terminate()
        self._wake.set()

    def _next_queued_job(self) -> dict | None:
        jobs = [job for job in training_service.list_training_jobs() if job.get('status') == 'queued']
        jobs.sort(key=lambda item: item.get('created_at', ''))
        return jobs[0] if jobs else None

    def _run_loop(self):
        while True:
            job = self._next_queued_job()
            if not job:
                self._wake.wait(timeout=2.0)
                self._wake.clear()
                continue
            self._run_job(job)

    def _run_job(self, job: dict):
        version = training_service.get_dataset_version(job['dataset_version_id'])
        training_service.update_training_job(job['id'], status='preparing', started_at=datetime.now().isoformat())
        training_event_hub.publish(job['id'], {'event': 'job_started', 'phase': 'preparing'})
        if job.get('training_mode') == 'high_speed':
            activity_service.set_high_speed_training(True)

        cmd = [
            'env/bin/python',
            'backend/train_worker.py',
            '--job-json',
            training_service._job_path(job['id']),
            '--version-json',
            training_service._version_meta_path(version['id']),
        ]
        env = os.environ.copy()
        env.setdefault('PYTHONUNBUFFERED', '1')
        device_policy = resolve_training_device_policy(job)
        env['CUDA_DEVICE_ORDER'] = device_policy['cuda_device_order']
        env['CUDA_VISIBLE_DEVICES'] = device_policy['cuda_visible_devices']

        process = subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        with self._lock:
            self._current_process = process
            self._current_job_id = job['id']

        try:
            if process.stdout is not None:
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        training_event_hub.publish(job['id'], {'event': 'log_line', 'line': line})
                        continue
                    self._handle_worker_event(job['id'], event)
            return_code = process.wait()
            if process.stdout is not None:
                process.stdout.close()
            latest = training_service.get_training_job(job['id'])
            if latest.get('status') not in {'completed', 'failed', 'cancelled'}:
                if return_code == 0:
                    training_service.complete_training_job(job['id'], latest.get('best_model_path') or '', latest.get('last_checkpoint_path') or latest.get('best_model_path') or '')
                    training_event_hub.publish(job['id'], {'event': 'job_completed', 'best_model_path': latest.get('best_model_path')})
                else:
                    training_service.fail_training_job(job['id'], f'Training process exited with code {return_code}')
                    training_event_hub.publish(job['id'], {'event': 'job_failed', 'error': f'Training process exited with code {return_code}'})
        finally:
            if job.get('training_mode') == 'high_speed':
                activity_service.set_high_speed_training(False)
            with self._lock:
                self._current_process = None
                self._current_job_id = None

    def _handle_worker_event(self, job_id: str, event: dict):
        kind = event.get('event')
        if kind == 'job_started':
            training_service.update_training_job(job_id, status='running')
        elif kind == 'metric_update':
            metric = {
                'epoch': event.get('epoch', 0),
                'total_epochs': event.get('total_epochs', 0),
                'train_loss': event.get('train_loss', 0),
                'val_loss': event.get('val_loss', 0),
                'map50': event.get('map50', 0),
                'map50_95': event.get('map50_95', 0),
                'precision': event.get('precision', 0),
                'recall': event.get('recall', 0),
                'lr': event.get('lr', 0),
                'time_per_epoch_sec': event.get('time_per_epoch_sec', 0),
                'elapsed_sec': event.get('elapsed_sec', 0),
                'eta_sec': event.get('eta_sec', 0),
            }
            training_service.append_metric(job_id, metric)
            training_service.update_training_job(job_id, status='running')
        elif kind == 'checkpoint_saved':
            training_service.update_training_job(job_id, last_checkpoint_path=event.get('path'))
        elif kind == 'job_completed':
            completed = training_service.complete_training_job(
                job_id,
                best_model_path=event.get('best_model_path') or '',
                last_checkpoint_path=event.get('last_checkpoint_path') or event.get('best_model_path') or '',
            )
            event = {**event, 'best_model_path': completed.get('best_model_path')}
        elif kind == 'job_failed':
            training_service.fail_training_job(job_id, event.get('error', 'Training failed'))
        training_event_hub.publish(job_id, event)


training_runtime = TrainingRuntime()
