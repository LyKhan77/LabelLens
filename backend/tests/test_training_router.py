import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.activity import activity_service
from backend.services.dataset import dataset_service
from backend.services.training import training_service


def jpg_bytes(width: int = 40, height: int = 30) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 1] = 160
    ok, buffer = cv2.imencode('.jpg', image)
    assert ok
    return buffer.tobytes()


class TrainingRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.datasets_root = f'{self.tmp.name}/datasets'
        self.training_root = f'{self.tmp.name}/train_tune'
        self.workspace_root = f'{self.tmp.name}/traintune-workspace'
        self.dataset_patcher = patch('backend.services.dataset.DATASETS_DIR', self.datasets_root)
        self.training_patcher = patch('backend.services.training.TRAIN_TUNE_DIR', self.training_root)
        self.workspace_patcher = patch('backend.services.training.TRAIN_TUNE_WORKSPACE_DIR', self.workspace_root)
        self.dataset_patcher.start()
        self.training_patcher.start()
        self.workspace_patcher.start()
        training_service._ensure_root()
        self.client = TestClient(app)
        dataset_service.create_project('demo', ['bolt'])
        dataset_service.save_image(
            'demo',
            jpg_bytes(),
            [{'box': [2, 4, 20, 18], 'label': 'bolt', 'confidence': 0.91}],
            original_filename='panel-top.jpg',
        )

    def tearDown(self):
        while activity_service.inference_active():
            activity_service.stop_inference()
        activity_service.set_high_speed_training(False)
        self.workspace_patcher.stop()
        self.training_patcher.stop()
        self.dataset_patcher.stop()
        self.tmp.cleanup()

    def test_create_live_dataset_version_endpoint(self):
        response = self.client.post(
            '/api/training/dataset-versions/live',
            data={
                'dataset_name': 'demo',
                'version_name': 'demo-v1',
                'split_config': '{"train":70,"val":20,"test":10}',
                'preprocessing_config': '{"auto_orient":true}',
                'augmentation_config': '{"profile":"baseline"}',
                'resize_mode': 'keep',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['source_type'], 'live_dataset')
        self.assertEqual(payload['summary']['usable_labeled_images'], 1)

    def test_policy_preview_endpoint_returns_samples(self):
        response = self.client.post(
            '/api/training/dataset-versions/preview',
            data={
                'source_type': 'live',
                'dataset_name': 'demo',
                'task_type': 'detect',
                'preprocessing_config': '{"auto_orient":true,"resize_mode":"keep"}',
                'augmentation_config': '{"mode":"hybrid","multiplier":2,"apply_to":"train","offline":{"fliplr":1.0}}',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['samples']), 1)
        self.assertIn('augmented', payload['samples'][0])
        self.assertTrue(payload['samples'][0]['augmented']['image'].startswith('data:image/jpeg;base64,'))

    def test_delete_dataset_version_endpoint_removes_unused_version(self):
        version = training_service.create_dataset_version_from_live_dataset(
            'demo',
            {
                'version_name': 'demo-delete',
                'split_config': {'train': 70, 'val': 20, 'test': 10},
                'preprocessing_config': {},
                'augmentation_config': {'profile': 'baseline'},
            },
        )

        response = self.client.delete(f'/api/training/dataset-versions/{version["id"]}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f'/api/training/dataset-versions/{version["id"]}').status_code, 404)

    def test_delete_dataset_version_endpoint_blocks_used_version(self):
        version = training_service.create_dataset_version_from_live_dataset(
            'demo',
            {
                'version_name': 'demo-used',
                'split_config': {'train': 70, 'val': 20, 'test': 10},
                'preprocessing_config': {},
                'augmentation_config': {'profile': 'baseline'},
            },
        )
        training_service.create_training_job(
            {
                'job_name': 'used-version',
                'dataset_version_id': version['id'],
                'family': 'yolo11',
                'size': 'n',
                'base_checkpoint': 'mock',
                'epochs': 1,
                'imgsz': 640,
                'batch': 2,
                'workers': 1,
                'training_mode': 'standard',
            },
            inference_active=False,
        )

        response = self.client.delete(f'/api/training/dataset-versions/{version["id"]}')

        self.assertEqual(response.status_code, 409)
        self.assertIn('referenced by training history', response.json()['detail'])


    def test_mock_job_runtime_completes_and_registers_model(self):
        version = training_service.create_dataset_version_from_live_dataset(
            'demo',
            {
                'version_name': 'demo-v1',
                'split_config': {'train': 70, 'val': 20, 'test': 10},
                'preprocessing_config': {},
                'augmentation_config': {'profile': 'baseline'},
            },
        )
        with patch.dict('os.environ', {'LABELLENS_TRAIN_TUNE_FAKE': '1'}):
            response = self.client.post(
                '/api/training/jobs',
                json={
                    'job_name': 'mock-run',
                    'dataset_version_id': version['id'],
                    'family': 'yolo11',
                    'size': 'n',
                    'base_checkpoint': 'mock',
                    'epochs': 3,
                    'imgsz': 640,
                    'batch': 4,
                    'workers': 2,
                    'training_mode': 'standard',
                },
            )
            self.assertEqual(response.status_code, 200)
            job_id = response.json()['id']
            for _ in range(40):
                job_response = self.client.get(f'/api/training/jobs/{job_id}')
                self.assertEqual(job_response.status_code, 200)
                if job_response.json()['status'] == 'completed':
                    break
                import time
                time.sleep(0.2)
            final_job = self.client.get(f'/api/training/jobs/{job_id}').json()
            self.assertEqual(final_job['status'], 'completed')
            metrics = self.client.get(f'/api/training/jobs/{job_id}/metrics').json()
            self.assertGreaterEqual(len(metrics), 1)
            models = self.client.get('/api/training/models').json()
            self.assertTrue(any(model['job_id'] == job_id for model in models))

    def test_failed_job_can_be_recomputed_and_deleted_via_api(self):
        version = training_service.create_dataset_version_from_live_dataset(
            'demo',
            {
                'version_name': 'demo-v1',
                'split_config': {'train': 70, 'val': 20, 'test': 10},
                'preprocessing_config': {},
                'augmentation_config': {'profile': 'baseline'},
            },
        )
        job = training_service.create_training_job(
            {
                'job_name': 'v1',
                'dataset_version_id': version['id'],
                'family': 'yolo11',
                'size': 'n',
                'base_checkpoint': 'mock',
                'epochs': 3,
                'imgsz': 640,
                'batch': 4,
                'workers': 2,
                'training_mode': 'standard',
            },
            inference_active=False,
        )
        training_service.fail_training_job(job['id'], 'boom')

        with patch('backend.routers.training.training_runtime.notify_job_queued'):
            recompute_response = self.client.post(f'/api/training/jobs/{job["id"]}/recompute')
        self.assertEqual(recompute_response.status_code, 200)
        retry = recompute_response.json()
        self.assertNotEqual(retry['id'], job['id'])
        self.assertTrue(retry['output_dir'].startswith(self.workspace_root))

        delete_response = self.client.delete(f'/api/training/jobs/{job["id"]}')
        self.assertEqual(delete_response.status_code, 200)
        missing_response = self.client.get(f'/api/training/jobs/{job["id"]}')
        self.assertEqual(missing_response.status_code, 404)

    def test_model_version_delete_endpoint_removes_model_and_training_job(self):
        version = training_service.create_dataset_version_from_live_dataset(
            'demo',
            {
                'version_name': 'model-delete',
                'split_config': {'train': 70, 'val': 20, 'test': 10},
                'preprocessing_config': {},
                'augmentation_config': {'profile': 'baseline'},
            },
        )
        job = training_service.create_training_job(
            {
                'job_name': 'model-delete',
                'dataset_version_id': version['id'],
                'family': 'yolo11',
                'size': 'n',
                'base_checkpoint': 'mock',
                'epochs': 1,
                'imgsz': 640,
                'batch': 2,
                'workers': 1,
                'training_mode': 'standard',
            },
            inference_active=False,
        )
        training_service.complete_training_job(job['id'], best_model_path='best.pt')
        model = next(model for model in training_service.list_model_versions() if model['job_id'] == job['id'])

        response = self.client.delete(f'/api/training/models/{model["id"]}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f'/api/training/models/{model["id"]}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/training/jobs/{job["id"]}').status_code, 404)

    def test_high_speed_job_endpoint_rejects_when_inference_is_active(self):
        version = training_service.create_dataset_version_from_live_dataset(
            'demo',
            {
                'version_name': 'demo-v1',
                'split_config': {'train': 70, 'val': 20, 'test': 10},
                'preprocessing_config': {},
                'augmentation_config': {'profile': 'baseline'},
            },
        )
        activity_service.start_inference()
        try:
            response = self.client.post(
                '/api/training/jobs',
                json={
                    'job_name': 'fast-lane',
                    'dataset_version_id': version['id'],
                    'family': 'yolo11',
                    'size': 'n',
                    'base_checkpoint': 'mock',
                    'epochs': 3,
                    'imgsz': 640,
                    'batch': 4,
                    'workers': 2,
                    'training_mode': 'high_speed',
                },
            )
        finally:
            activity_service.stop_inference()

        self.assertEqual(response.status_code, 409)
        self.assertIn('Inference must be idle', response.json()['detail'])


if __name__ == '__main__':
    unittest.main()
