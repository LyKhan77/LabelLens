import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from pathlib import Path

import cv2
import numpy as np

from backend.services.dataset import DatasetService
from backend.services.training import TrainingService


def jpg_bytes(width: int = 40, height: int = 30) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 2] = 200
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


class TrainingServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.datasets_root = os.path.join(self.tmp.name, "datasets")
        self.training_root = os.path.join(self.tmp.name, "train_tune")
        self.workspace_root = os.path.join(self.tmp.name, "traintune-workspace")
        self.dataset_patcher = patch("backend.services.dataset.DATASETS_DIR", self.datasets_root)
        self.training_patcher = patch("backend.services.training.TRAIN_TUNE_DIR", self.training_root)
        self.workspace_patcher = patch("backend.services.training.TRAIN_TUNE_WORKSPACE_DIR", self.workspace_root)
        self.dataset_patcher.start()
        self.training_patcher.start()
        self.workspace_patcher.start()
        self.dataset_service = DatasetService()
        self.training_service = TrainingService(self.dataset_service)

    def tearDown(self):
        self.workspace_patcher.stop()
        self.training_patcher.stop()
        self.dataset_patcher.stop()
        self.tmp.cleanup()

    def _create_demo_version(self):
        self.dataset_service.create_project("delete-demo", ["bolt"])
        self.dataset_service.save_image(
            "delete-demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )
        return self.training_service.create_dataset_version_from_live_dataset(
            "delete-demo",
            {
                "version_name": "delete-demo-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )

    def test_create_dataset_version_from_live_dataset_builds_immutable_snapshot(self):
        self.dataset_service.create_project("demo", ["bolt", "nut"])
        saved = self.dataset_service.save_image(
            "demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )
        self.dataset_service.upload_raw("demo", jpg_bytes(), original_filename="empty.jpg")
        version = self.training_service.create_dataset_version_from_live_dataset(
            "demo",
            {
                "version_name": "demo-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )

        self.assertEqual(version["source_type"], "live_dataset")
        self.assertEqual(version["source_name"], "demo")
        self.assertEqual(version["summary"]["usable_labeled_images"], 1)
        self.assertEqual(version["summary"]["original_file_count"], 2)
        self.assertEqual(version["summary"]["class_count"], 1)
        self.assertEqual(version["summary"]["classes"], ["bolt"])
        dataset_yaml = os.path.join(version["storage_path"], "dataset", "dataset.yaml")
        self.assertTrue(os.path.isfile(dataset_yaml))

        image_files = []
        for subset in ("train", "val", "test"):
            subset_dir = os.path.join(version["storage_path"], "dataset", "images", subset)
            if os.path.isdir(subset_dir):
                image_files.extend(os.listdir(subset_dir))
        self.assertEqual(image_files, ["panel-top.jpg"])
        label_path = os.path.join(version["storage_path"], "dataset", "labels", version["split_counts"]["primary"], "panel-top.txt")
        self.assertTrue(os.path.isfile(label_path))
        self.assertEqual(saved["image"], "img_0001.jpg")

    def test_create_dataset_version_from_export_zip_can_keep_existing_split(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dataset.yaml", "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: bolt\n")
            zf.writestr("images/train/train-a.jpg", jpg_bytes())
            zf.writestr("labels/train/train-a.txt", "0 0.5 0.5 0.5 0.5\n")
            zf.writestr("images/val/val-a.jpg", jpg_bytes())
            zf.writestr("labels/val/val-a.txt", "0 0.4 0.4 0.3 0.3\n")
            zf.writestr("images/test/test-a.jpg", jpg_bytes())
            zf.writestr("labels/test/test-a.txt", "0 0.3 0.3 0.2 0.2\n")

        version = self.training_service.create_dataset_version_from_zip(
            zip_buffer.getvalue(),
            "export-demo.zip",
            {
                "version_name": "zip-v1",
                "split_mode": "existing",
                "preprocessing_config": {"auto_orient": False},
                "augmentation_config": {"profile": "standard"},
            },
        )

        self.assertEqual(version["source_type"], "export_zip")
        self.assertEqual(version["summary"]["usable_labeled_images"], 3)
        self.assertEqual(version["split_counts"]["train"], 1)
        self.assertEqual(version["split_counts"]["val"], 1)
        self.assertEqual(version["split_counts"]["test"], 1)
        self.assertTrue(os.path.isfile(os.path.join(version["storage_path"], "dataset", "images", "train", "train-a.jpg")))
        self.assertTrue(os.path.isfile(os.path.join(version["storage_path"], "dataset", "labels", "test", "test-a.txt")))


    def test_create_segment_dataset_version_from_live_dataset_writes_polygon_labels(self):
        self.dataset_service.create_project("seg-demo", ["bolt"])
        saved = self.dataset_service.save_image(
            "seg-demo",
            jpg_bytes(width=40, height=30),
            [
                {
                    "box": [4, 6, 24, 21],
                    "label": "bolt",
                    "confidence": 0.91,
                    "mask": [[4, 6], [24, 6], [24, 21], [4, 21]],
                }
            ],
            original_filename="panel-seg.jpg",
        )

        version = self.training_service.create_dataset_version_from_live_dataset(
            "seg-demo",
            {
                "version_name": "seg-demo-v1",
                "task_type": "segment",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )

        self.assertEqual(version["task_type"], "segment")
        label_path = os.path.join(version["storage_path"], "dataset", "labels", version["split_counts"]["primary"], "panel-seg.txt")
        row = Path(label_path).read_text().strip().split()
        self.assertEqual(row[0], "0")
        self.assertEqual(len(row), 9)
        self.assertEqual([round(float(value), 6) for value in row[1:]], [0.1, 0.2, 0.6, 0.2, 0.6, 0.7, 0.1, 0.7])
        self.assertEqual(saved["image"], "img_0001.jpg")

    def test_create_segment_dataset_version_blocks_missing_masks(self):
        self.dataset_service.create_project("missing-mask", ["bolt"])
        self.dataset_service.save_image(
            "missing-mask",
            jpg_bytes(width=40, height=30),
            [{"box": [4, 6, 24, 21], "label": "bolt", "confidence": 0.91}],
            original_filename="needs-mask.jpg",
        )

        with self.assertRaises(Exception) as ctx:
            self.training_service.create_dataset_version_from_live_dataset(
                "missing-mask",
                {
                    "version_name": "missing-mask-v1",
                    "task_type": "segment",
                    "split_config": {"train": 70, "val": 20, "test": 10},
                    "preprocessing_config": {"auto_orient": True},
                    "augmentation_config": {"profile": "baseline"},
                    "resize_mode": "keep",
                },
            )

        self.assertEqual(ctx.exception.missing[0]["image"], "needs-mask.jpg")
        self.assertEqual(ctx.exception.missing[0]["label"], "bolt")

    def test_create_dataset_version_from_export_zip_accepts_segment_labels(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dataset.yaml", "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: bolt\n")
            zf.writestr("images/train/train-a.jpg", jpg_bytes())
            zf.writestr("labels/train/train-a.txt", "0 0.1 0.2 0.6 0.2 0.6 0.7 0.1 0.7\n")

        version = self.training_service.create_dataset_version_from_zip(
            zip_buffer.getvalue(),
            "seg-export.zip",
            {
                "version_name": "zip-seg-v1",
                "task_type": "segment",
                "split_mode": "existing",
                "preprocessing_config": {"auto_orient": False},
                "augmentation_config": {"profile": "standard"},
            },
        )

        self.assertEqual(version["task_type"], "segment")
        self.assertEqual(version["summary"]["total_annotations"], 1)
        label_path = os.path.join(version["storage_path"], "dataset", "labels", "train", "train-a.txt")
        self.assertEqual(Path(label_path).read_text().strip(), "0 0.1 0.2 0.6 0.2 0.6 0.7 0.1 0.7")

    def test_create_dataset_version_from_export_zip_rejects_bbox_labels_for_segment(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dataset.yaml", "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: bolt\n")
            zf.writestr("images/train/train-a.jpg", jpg_bytes())
            zf.writestr("labels/train/train-a.txt", "0 0.5 0.5 0.5 0.5\n")

        with self.assertRaisesRegex(ValueError, "polygon format"):
            self.training_service.create_dataset_version_from_zip(
                zip_buffer.getvalue(),
                "bad-seg.zip",
                {"version_name": "bad", "task_type": "segment", "split_mode": "existing"},
            )

    def test_delete_dataset_version_removes_unused_snapshot(self):
        version = self._create_demo_version()

        self.training_service.delete_dataset_version(version["id"])

        self.assertFalse(os.path.exists(version["storage_path"]))
        with self.assertRaises(FileNotFoundError):
            self.training_service.get_dataset_version(version["id"])

    def test_delete_dataset_version_blocks_snapshot_used_by_training_job(self):
        version = self._create_demo_version()
        self.training_service.create_training_job(
            {
                "job_name": "delete-guard",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 1,
                "imgsz": 640,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
            },
            inference_active=False,
        )

        with self.assertRaisesRegex(RuntimeError, "referenced by training history"):
            self.training_service.delete_dataset_version(version["id"])

        self.assertTrue(os.path.exists(version["storage_path"]))

    def test_delete_dataset_version_blocks_snapshot_used_by_model_version(self):
        version = self._create_demo_version()
        job = self.training_service.create_training_job(
            {
                "job_name": "model-delete-guard",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 1,
                "imgsz": 640,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
            },
            inference_active=False,
        )
        self.training_service.complete_training_job(job["id"], best_model_path="best.pt")
        os.remove(self.training_service._job_path(job["id"]))

        with self.assertRaisesRegex(RuntimeError, "referenced by training history"):
            self.training_service.delete_dataset_version(version["id"])

        self.assertTrue(os.path.exists(version["storage_path"]))

    def test_delete_model_version_removes_linked_training_history_and_output(self):
        version = self._create_demo_version()
        job = self.training_service.create_training_job(
            {
                "job_name": "delete-model",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 1,
                "imgsz": 640,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
            },
            inference_active=False,
        )
        os.makedirs(job["output_dir"], exist_ok=True)
        self.training_service.append_metric(job["id"], {"epoch": 1, "map50": 0.62})
        self.training_service.complete_training_job(job["id"], best_model_path="best.pt")
        model = next(model for model in self.training_service.list_model_versions() if model["job_id"] == job["id"])

        self.training_service.delete_model_version(model["id"])

        with self.assertRaises(FileNotFoundError):
            self.training_service.get_model_version(model["id"])
        with self.assertRaises(FileNotFoundError):
            self.training_service.get_training_job(job["id"])
        self.assertFalse(os.path.exists(self.training_service._metrics_path(job["id"])))
        self.assertFalse(os.path.exists(job["output_dir"]))

    def test_create_training_job_rejects_high_speed_when_inference_is_active(self):
        self.dataset_service.create_project("demo", ["bolt"])
        self.dataset_service.save_image(
            "demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )
        version = self.training_service.create_dataset_version_from_live_dataset(
            "demo",
            {
                "version_name": "demo-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )

        with self.assertRaisesRegex(RuntimeError, "Inference must be idle"):
            self.training_service.create_training_job(
                {
                    "job_name": "fast-lane",
                    "dataset_version_id": version["id"],
                    "family": "yolo11",
                    "size": "n",
                    "base_checkpoint": "yolo11n.pt",
                    "epochs": 10,
                    "imgsz": 640,
                    "batch": 8,
                    "workers": 2,
                    "training_mode": "high_speed",
                },
                inference_active=True,
            )

    def test_create_training_job_uses_unique_workspace_output_dir(self):
        self.dataset_service.create_project("demo", ["bolt"])
        self.dataset_service.save_image(
            "demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )
        version = self.training_service.create_dataset_version_from_live_dataset(
            "demo",
            {
                "version_name": "demo-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )

        first = self.training_service.create_training_job(
            {
                "job_name": "v1",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 10,
                "imgsz": 640,
                "batch": 8,
                "workers": 2,
                "training_mode": "standard",
            },
            inference_active=False,
        )
        second = self.training_service.create_training_job(
            {
                "job_name": "v1",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 10,
                "imgsz": 640,
                "batch": 8,
                "workers": 2,
                "training_mode": "standard",
            },
            inference_active=False,
        )

        self.assertTrue(first["output_dir"].startswith(self.workspace_root))
        self.assertTrue(second["output_dir"].startswith(self.workspace_root))
        self.assertNotEqual(first["output_dir"], second["output_dir"])
        self.assertIn('v1-', os.path.basename(first["output_dir"]))

    def test_failed_job_can_be_recomputed_and_deleted(self):
        self.dataset_service.create_project("demo", ["bolt"])
        self.dataset_service.save_image(
            "demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )
        version = self.training_service.create_dataset_version_from_live_dataset(
            "demo",
            {
                "version_name": "demo-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )
        job = self.training_service.create_training_job(
            {
                "job_name": "v1",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 10,
                "imgsz": 640,
                "batch": 8,
                "workers": 2,
                "training_mode": "standard",
            },
            inference_active=False,
        )
        os.makedirs(job["output_dir"], exist_ok=True)
        with open(os.path.join(job["output_dir"], 'partial.txt'), 'w') as f:
            f.write('partial')
        self.training_service.fail_training_job(job["id"], 'boom')

        retry = self.training_service.recompute_training_job(job["id"], inference_active=False)
        self.assertNotEqual(retry["id"], job["id"])
        self.assertEqual(retry["job_name"], job["job_name"])
        self.assertNotEqual(retry["output_dir"], job["output_dir"])

        self.training_service.delete_training_job(job["id"])
        self.assertFalse(os.path.exists(self.training_service._job_path(job["id"])))
        self.assertFalse(os.path.exists(self.training_service._metrics_path(job["id"])))
        self.assertFalse(os.path.exists(job["output_dir"]))

    def test_complete_training_job_persists_metrics_history_and_model_version(self):
        self.dataset_service.create_project("demo", ["bolt"])
        self.dataset_service.save_image(
            "demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )
        version = self.training_service.create_dataset_version_from_live_dataset(
            "demo",
            {
                "version_name": "demo-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )
        job = self.training_service.create_training_job(
            {
                "job_name": "bolt-detector",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "yolo11n.pt",
                "epochs": 10,
                "imgsz": 640,
                "batch": 8,
                "workers": 2,
                "training_mode": "standard",
            },
            inference_active=False,
        )

        self.training_service.append_metric(
            job["id"],
            {
                "epoch": 1,
                "train_loss": 1.2,
                "val_loss": 0.9,
                "map50": 0.61,
                "map50_95": 0.44,
                "precision": 0.7,
                "recall": 0.66,
                "lr": 0.001,
                "time_per_epoch_sec": 14.2,
            },
        )
        best_path = os.path.join(self.training_root, "weights", "best.pt")
        os.makedirs(os.path.dirname(best_path), exist_ok=True)
        with open(best_path, "wb") as f:
            f.write(b"model")
        completed = self.training_service.complete_training_job(
            job["id"],
            best_model_path=best_path,
            last_checkpoint_path=best_path,
        )

        self.assertEqual(completed["status"], "completed")
        metrics = self.training_service.list_training_metrics(job["id"])
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["map50"], 0.61)
        models = self.training_service.list_model_versions()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["job_id"], job["id"])
        self.assertEqual(models[0]["best_model_path"], best_path)
        self.assertEqual(models[0]["task_type"], "detect")


if __name__ == "__main__":
    unittest.main()
