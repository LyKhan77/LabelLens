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
        self.dataset_patcher = patch('backend.services.dataset.DATASETS_DIR', self.datasets_root)
        self.training_patcher = patch('backend.services.training.TRAIN_TUNE_DIR', self.training_root)
        self.dataset_patcher.start()
        self.training_patcher.start()
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
