import io
import json
import math
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

    def test_create_dataset_version_persists_training_config(self):
        self.dataset_service.create_project("training-config-demo", ["bolt"])
        self.dataset_service.save_image(
            "training-config-demo",
            jpg_bytes(),
            [{"box": [2, 4, 20, 18], "label": "bolt", "confidence": 0.91}],
            original_filename="panel-top.jpg",
        )

        version = self.training_service.create_dataset_version_from_live_dataset(
            "training-config-demo",
            {
                "version_name": "training-config-v1",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"auto_orient": True},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
                "task_type": "detect",
                "training_config": {
                    "family": "yolo26",
                    "size": "s",
                    "base_checkpoint": "yolo26s.pt",
                    "epochs": 120,
                    "patience": 25,
                    "imgsz": 768,
                    "batch": 8,
                    "workers": 4,
                    "training_mode": "high_speed",
                },
            },
        )

        self.assertEqual(
            version["training_config"],
            {
                "family": "yolo26",
                "size": "s",
                    "base_checkpoint": "yolo26s.pt",
                "epochs": 120,
                "patience": 25,
                "imgsz": 768,
                "batch": 8,
                "workers": 4,
                "training_mode": "high_speed",
            },
        )
        meta = json.loads(Path(self.training_service._version_meta_path(version["id"])).read_text())
        self.assertEqual(meta["training_config"], version["training_config"])

    def test_existing_dataset_version_uses_linked_job_training_config_fallback(self):
        version = self._create_demo_version()
        meta_path = Path(self.training_service._version_meta_path(version["id"]))
        meta = json.loads(meta_path.read_text())
        meta.pop("training_config", None)
        meta_path.write_text(json.dumps(meta))

        self.training_service.create_training_job(
            {
                "job_name": "legacy-yolo26-job",
                "dataset_version_id": version["id"],
                "family": "yolo26",
                "size": "m",
                "base_checkpoint": "yolo26m.pt",
                "epochs": 75,
                "patience": 20,
                "imgsz": 768,
                "batch": 8,
                "workers": 4,
                "training_mode": "high_speed",
                "task_type": "detect",
            }
        )

        loaded = self.training_service.get_dataset_version(version["id"])

        self.assertEqual(loaded["training_config"]["family"], "yolo26")
        self.assertEqual(loaded["training_config"]["size"], "m")
        self.assertEqual(loaded["training_config"]["base_checkpoint"], "yolo26m.pt")

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

    def test_letterbox_resize_strategy_resizes_image_and_preserves_bbox_geometry(self):
        self.dataset_service.create_project("resize-demo", ["bolt"])
        self.dataset_service.save_image(
            "resize-demo",
            jpg_bytes(width=80, height=40),
            [{"box": [20, 10, 60, 30], "label": "bolt", "confidence": 0.91}],
            original_filename="wide-panel.jpg",
        )

        version = self.training_service.create_dataset_version_from_live_dataset(
            "resize-demo",
            {
                "version_name": "resize-demo-v1",
                "split_config": {"train": 100, "val": 0, "test": 0},
                "preprocessing_config": {"auto_orient": True, "resize_mode": "letterbox", "target_size": 64},
                "augmentation_config": {"mode": "hybrid", "multiplier": 1, "apply_to": "train"},
            },
        )

        image_path = os.path.join(version["storage_path"], "dataset", "images", "train", "wide-panel.jpg")
        image = cv2.imread(image_path)
        self.assertEqual(image.shape[:2], (64, 64))
        label_path = os.path.join(version["storage_path"], "dataset", "labels", "train", "wide-panel.txt")
        values = [float(value) for value in Path(label_path).read_text().strip().split()[1:]]
        self.assertEqual([round(value, 3) for value in values], [0.5, 0.5, 0.5, 0.25])
        self.assertEqual(version["preprocessing_config"]["resize_mode"], "letterbox")
        self.assertEqual(version["preprocessing_config"]["target_size"], 64)

    def test_hybrid_multiplier_materializes_augmented_images_only_in_train_split(self):
        self.dataset_service.create_project("aug-demo", ["bolt"])
        for index in range(4):
            self.dataset_service.save_image(
                "aug-demo",
                jpg_bytes(width=80, height=60),
                [{"box": [10, 12, 40, 36], "label": "bolt", "confidence": 0.91}],
                original_filename=f"panel-{index}.jpg",
            )

        version = self.training_service.create_dataset_version_from_live_dataset(
            "aug-demo",
            {
                "version_name": "aug-demo-v1",
                "split_config": {"train": 50, "val": 25, "test": 25},
                "preprocessing_config": {"auto_orient": True, "resize_mode": "keep"},
                "augmentation_config": {
                    "mode": "hybrid",
                    "multiplier": 3,
                    "apply_to": "train",
                    "offline": {"fliplr": 1.0, "degrees": 5, "noise": 0.0},
                    "online": {"mosaic": 0.5, "mixup": 0.1},
                },
            },
        )

        train_images = os.listdir(os.path.join(version["storage_path"], "dataset", "images", "train"))
        val_images = os.listdir(os.path.join(version["storage_path"], "dataset", "images", "val"))
        test_images = os.listdir(os.path.join(version["storage_path"], "dataset", "images", "test"))
        self.assertEqual(version["split_counts"]["train_original"], 2)
        self.assertEqual(version["split_counts"]["train_generated"], 4)
        self.assertEqual(version["split_counts"]["train"], 6)
        self.assertEqual(version["split_counts"]["val"], 1)
        self.assertEqual(version["split_counts"]["test"], 1)
        self.assertEqual(len(train_images), 6)
        self.assertEqual(len(val_images), 1)
        self.assertEqual(len(test_images), 1)
        self.assertTrue(any("-aug-" in name for name in train_images))

        for filename in train_images:
            label_path = os.path.join(version["storage_path"], "dataset", "labels", "train", f"{Path(filename).stem}.txt")
            values = [float(value) for value in Path(label_path).read_text().strip().split()[1:]]
            self.assertEqual(len(values), 4)
            self.assertTrue(all(0.0 <= value <= 1.0 for value in values))

    def test_basic_augmentation_normalizes_to_online_only_safe_preset(self):
        normalized = self.training_service._normalize_augmentation_config({
            "augmentation_config": {
                "mode": "basic",
                "multiplier": 5,
                "offline": {"fliplr": 1.0},
                "online": {"mixup": 1.0},
            }
        })

        self.assertEqual(normalized["mode"], "basic")
        self.assertEqual(normalized["profile"], "basic")
        self.assertEqual(normalized["multiplier"], 1)
        self.assertEqual(normalized["offline"], {})
        self.assertEqual(normalized["apply_to"], "train")
        self.assertEqual(normalized["online"]["fliplr"], 0.5)
        self.assertEqual(normalized["online"]["mosaic"], 0.5)
        self.assertEqual(normalized["online"]["close_mosaic"], 10.0)
        self.assertNotIn("mixup", normalized["online"])

    def test_advanced_augmentation_keeps_materialized_train_only_behavior(self):
        normalized = self.training_service._normalize_augmentation_config({
            "augmentation_config": {
                "mode": "advanced",
                "profile": "custom",
                "multiplier": 4,
                "offline": {"fliplr": 1.0},
                "online": {"mosaic": 0.25},
            }
        })

        self.assertEqual(normalized["mode"], "advanced")
        self.assertEqual(normalized["profile"], "custom")
        self.assertEqual(normalized["multiplier"], 4)
        self.assertEqual(normalized["offline"], {"fliplr": 1.0})
        self.assertEqual(normalized["online"], {"mosaic": 0.25})

    def test_legacy_standard_profile_stays_compatible(self):
        normalized = self.training_service._normalize_augmentation_config({
            "augmentation_config": {"profile": "standard"}
        })

        self.assertEqual(normalized["mode"], "advanced")
        self.assertEqual(normalized["profile"], "standard")
        self.assertEqual(normalized["multiplier"], 1)
        self.assertEqual(normalized["offline"], {})
        self.assertEqual(normalized["online"]["mosaic"], 0.5)

    def test_preview_policy_returns_samples_without_creating_dataset_version(self):
        self.dataset_service.create_project("preview-demo", ["bolt"])
        for index in range(3):
            self.dataset_service.save_image(
                "preview-demo",
                jpg_bytes(width=80, height=60),
                [{"box": [10, 12, 40, 36], "label": "bolt", "confidence": 0.91}],
                original_filename=f"preview-{index}.jpg",
            )

        before = self.training_service.list_dataset_versions()
        preview = self.training_service.preview_dataset_policy(
            {
                "source_type": "live",
                "dataset_name": "preview-demo",
                "task_type": "detect",
                "preprocessing_config": {"auto_orient": True, "resize_mode": "keep"},
                "augmentation_config": {
                    "mode": "hybrid",
                    "multiplier": 2,
                    "apply_to": "train",
                    "offline": {"fliplr": 1.0, "degrees": 5},
                },
            }
        )

        self.assertEqual(len(preview["samples"]), 3)
        self.assertEqual(self.training_service.list_dataset_versions(), before)
        first = preview["samples"][0]
        self.assertEqual(set(first.keys()), {"filename", "original", "preprocessed", "augmented"})
        self.assertTrue(first["original"]["image"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(first["augmented"]["annotations"][0]["label"], "bolt")
        self.assertTrue(all(0 <= value <= 80 for value in first["augmented"]["annotations"][0]["box"][::2]))


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

    def test_create_classification_dataset_version_from_live_dataset_writes_class_folders(self):
        self.dataset_service.create_project("cls-demo", ["pass", "fail"], task_type="classify_single")
        uploaded = self.dataset_service.upload_raw("cls-demo", jpg_bytes(), original_filename="panel-ok.jpg")
        self.dataset_service.set_image_labels("cls-demo", uploaded["img_id"], [{"label": "pass", "confidence": 1.0}])

        version = self.training_service.create_dataset_version_from_live_dataset(
            "cls-demo",
            {
                "version_name": "cls-demo-v1",
                "task_type": "classify_single",
                "split_config": {"train": 100, "val": 0, "test": 0},
                "preprocessing_config": {"resize_mode": "keep"},
                "augmentation_config": {"profile": "baseline"},
            },
        )

        self.assertEqual(version["task_type"], "classify_single")
        self.assertEqual(version["dataset_yaml"], os.path.join(version["storage_path"], "dataset"))
        self.assertTrue(os.path.isfile(os.path.join(version["storage_path"], "dataset", "train", "pass", "panel-ok.jpg")))
        self.assertFalse(os.path.exists(os.path.join(version["storage_path"], "dataset", "dataset.yaml")))

    def test_create_pose_dataset_version_from_live_dataset_writes_keypoint_labels(self):
        self.dataset_service.create_project(
            "pose-demo",
            ["part"],
            task_type="pose",
            task_config={
                "pose_template": {
                    "name": "Two Point",
                    "keypoint_names": ["left", "right"],
                    "skeleton": [[0, 1]],
                    "flip_idx": [1, 0],
                    "kpt_shape": [2, 3],
                }
            },
        )
        uploaded = self.dataset_service.upload_raw("pose-demo", jpg_bytes(width=40, height=30), original_filename="pose.jpg")
        self.dataset_service.add_pose(
            "pose-demo",
            uploaded["img_id"],
            {
                "label": "part",
                "box": [4, 6, 24, 21],
                "keypoints": [
                    {"name": "left", "x": 8, "y": 9, "visibility": "visible"},
                    {"name": "right", "x": 20, "y": 18, "visibility": "occluded"},
                ],
            },
        )

        version = self.training_service.create_dataset_version_from_live_dataset(
            "pose-demo",
            {
                "version_name": "pose-demo-v1",
                "task_type": "pose",
                "split_config": {"train": 100, "val": 0, "test": 0},
                "preprocessing_config": {"resize_mode": "keep"},
                "augmentation_config": {"profile": "baseline"},
            },
        )

        self.assertEqual(version["task_type"], "pose")
        yaml_text = Path(os.path.join(version["storage_path"], "dataset", "dataset.yaml")).read_text()
        self.assertIn("kpt_shape: [2, 3]", yaml_text)
        self.assertIn("flip_idx: [1, 0]", yaml_text)
        label_path = os.path.join(version["storage_path"], "dataset", "labels", "train", "pose.txt")
        row = Path(label_path).read_text().strip().split()
        self.assertEqual(row[0], "0")
        self.assertEqual(len(row), 11)
        self.assertEqual([round(float(value), 6) for value in row[1:5]], [0.35, 0.45, 0.5, 0.5])
        self.assertEqual(row[-1], "1")

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

    def test_create_training_job_rejects_invalid_training_config(self):
        version = self._create_demo_version()

        with self.assertRaisesRegex(ValueError, "epochs must be between"):
            self.training_service.create_training_job(
                {
                    "job_name": "bad",
                    "dataset_version_id": version["id"],
                    "family": "yolo99",
                    "size": "n",
                    "base_checkpoint": "../bad.pt",
                    "epochs": 0,
                    "imgsz": 641,
                    "batch": 0,
                    "workers": -1,
                    "training_mode": "turbo",
                },
                inference_active=False,
            )

    def test_recommend_training_settings_uses_dataset_size_buckets(self):
        version = self._create_demo_version()
        version["summary"]["final_image_count"] = 42
        small = self.training_service.recommend_training_settings(version["id"], {})
        version["summary"]["final_image_count"] = 80
        self.training_service._write_json(self.training_service._version_meta_path(version["id"]), version)
        medium = self.training_service.recommend_training_settings(version["id"], {})
        version["summary"]["final_image_count"] = 300
        self.training_service._write_json(self.training_service._version_meta_path(version["id"]), version)
        larger = self.training_service.recommend_training_settings(version["id"], {})

        self.assertEqual(small["epochs"], 200)
        self.assertEqual(small["patience"], 40)
        self.assertEqual(small["batch"], -1)
        self.assertEqual(small["augmentation_mode"], "basic")
        self.assertIn("small dataset", small["reason"])
        self.assertEqual(medium["epochs"], 150)
        self.assertEqual(medium["patience"], 30)
        self.assertEqual(larger["epochs"], 100)
        self.assertEqual(larger["patience"], 25)

    def test_create_training_job_persists_patience_and_auto_batch(self):
        version = self._create_demo_version()

        job = self.training_service.create_training_job(
            {
                "job_name": "auto-batch",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "mock",
                "epochs": 100,
                "patience": 25,
                "imgsz": 640,
                "batch": -1,
                "workers": 2,
                "training_mode": "standard",
            },
            inference_active=False,
        )

        self.assertEqual(job["patience"], 25)
        self.assertEqual(job["batch"], -1)

    def test_create_training_job_rejects_invalid_patience(self):
        version = self._create_demo_version()

        with self.assertRaisesRegex(ValueError, "patience must be between"):
            self.training_service.create_training_job(
                {
                    "job_name": "bad-patience",
                    "dataset_version_id": version["id"],
                    "family": "yolo11",
                    "size": "n",
                    "base_checkpoint": "mock",
                    "epochs": 100,
                    "patience": 101,
                    "imgsz": 640,
                    "batch": 8,
                    "workers": 2,
                    "training_mode": "standard",
                },
                inference_active=False,
            )

    def test_resume_training_job_queues_from_existing_last_checkpoint(self):
        version = self._create_demo_version()
        job = self.training_service.create_training_job(
            {
                "job_name": "resume-demo",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "mock",
                "epochs": 3,
                "imgsz": 640,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
            },
            inference_active=False,
        )
        last_path = os.path.join(job["output_dir"], "weights", "last.pt")
        os.makedirs(os.path.dirname(last_path), exist_ok=True)
        Path(last_path).write_bytes(b"checkpoint")
        self.training_service.cancel_training_job(job["id"])
        self.training_service.update_training_job(job["id"], last_checkpoint_path=last_path)

        resumed = self.training_service.resume_training_job(job["id"], inference_active=False)

        self.assertNotEqual(resumed["id"], job["id"])
        self.assertTrue(resumed["resume"])
        self.assertEqual(resumed["resume_from_checkpoint"], last_path)
        self.assertEqual(resumed["base_checkpoint"], last_path)

    def test_resume_training_job_requires_last_checkpoint(self):
        version = self._create_demo_version()
        job = self.training_service.create_training_job(
            {
                "job_name": "resume-missing",
                "dataset_version_id": version["id"],
                "family": "yolo11",
                "size": "n",
                "base_checkpoint": "mock",
                "epochs": 3,
                "imgsz": 640,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
            },
            inference_active=False,
        )
        self.training_service.fail_training_job(job["id"], "boom")

        with self.assertRaisesRegex(RuntimeError, "last checkpoint"):
            self.training_service.resume_training_job(job["id"], inference_active=False)

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

    def test_complete_training_job_uses_best_epoch_metrics_for_segment_model_version(self):
        self.dataset_service.create_project("seg-demo", ["pcb"])
        self.dataset_service.save_image(
            "seg-demo",
            jpg_bytes(),
            [
                {
                    "box": [2, 4, 20, 18],
                    "label": "pcb",
                    "confidence": 0.91,
                    "mask": [[2, 4], [20, 4], [20, 18], [2, 18]],
                }
            ],
            original_filename="panel-top.jpg",
        )
        version = self.training_service.create_dataset_version_from_live_dataset(
            "seg-demo",
            {
                "version_name": "seg-demo-v1",
                "task_type": "segment",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"resize_mode": "keep"},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )
        job = self.training_service.create_training_job(
            {
                "job_name": "pcb-segmenter",
                "dataset_version_id": version["id"],
                "family": "yolo26",
                "size": "l",
                "base_checkpoint": "yolo26l.pt",
                "epochs": 3,
                "imgsz": 640,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
                "task_type": "segment",
            },
            inference_active=False,
        )

        self.training_service.append_metric(
            job["id"],
            {
                "epoch": 1,
                "map50": 0.61786,
                "map50_95": 0.599,
                "precision": 0.82504,
                "recall": 0.33333,
                "val_loss": 0.22,
            },
        )
        self.training_service.append_metric(
            job["id"],
            {
                "epoch": 3,
                "map50": 0.0022,
                "map50_95": 0.00022,
                "precision": 0.00281,
                "recall": 0.33333,
                "val_loss": 2.41,
            },
        )

        completed = self.training_service.complete_training_job(
            job["id"],
            best_model_path="/tmp/best.pt",
            last_checkpoint_path="/tmp/last.pt",
        )

        self.assertEqual(completed["metrics_latest"]["epoch"], 3)
        self.assertEqual(completed["metrics_best"]["epoch"], 1)
        self.assertEqual(completed["metrics_best"]["map50"], 0.61786)
        self.assertEqual(completed["metrics_best"]["map50_95"], 0.599)
        model = next(model for model in self.training_service.list_model_versions() if model["job_id"] == job["id"])
        self.assertEqual(model["metrics_best"], completed["metrics_best"])

    def test_complete_training_job_uses_accuracy_for_classification_best_metrics(self):
        self.dataset_service.create_project("cls-demo", ["ok", "ng"], task_type="classify_single")
        uploaded = self.dataset_service.upload_raw("cls-demo", jpg_bytes(), original_filename="panel-ok.jpg")
        self.dataset_service.set_image_labels("cls-demo", uploaded["img_id"], [{"label": "ok", "confidence": 1.0}])
        version = self.training_service.create_dataset_version_from_live_dataset(
            "cls-demo",
            {
                "version_name": "cls-demo-v1",
                "task_type": "classify_single",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"resize_mode": "keep"},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )
        with patch.object(
            self.training_service,
            "_validate_training_config",
            return_value={
                "family": "yolo26",
                "size": "n",
                "base_checkpoint": "yolo26n-cls.pt",
                "epochs": 2,
                "patience": 30,
                "imgsz": 224,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
                "task_type": "classify_single",
            },
        ):
            job = self.training_service.create_training_job(
                {
                    "job_name": "panel-classifier",
                    "dataset_version_id": version["id"],
                    "family": "yolo26",
                    "size": "n",
                    "base_checkpoint": "yolo26n-cls.pt",
                    "epochs": 2,
                    "imgsz": 224,
                    "batch": 2,
                    "workers": 1,
                    "training_mode": "standard",
                    "task_type": "classify_single",
                },
                inference_active=False,
            )

        self.training_service.append_metric(
            job["id"],
            {"epoch": 1, "accuracy_top1": 0.91, "accuracy_top5": 1.0, "val_loss": 0.4},
        )
        self.training_service.append_metric(
            job["id"],
            {"epoch": 2, "accuracy_top1": 0.5, "accuracy_top5": 0.75, "val_loss": 0.8},
        )

        completed = self.training_service.complete_training_job(
            job["id"],
            best_model_path="/tmp/best.pt",
            last_checkpoint_path="/tmp/last.pt",
        )

        self.assertEqual(completed["metrics_latest"]["epoch"], 2)
        self.assertEqual(completed["metrics_best"]["epoch"], 1)
        self.assertEqual(completed["metrics_best"]["accuracy_top1"], 0.91)

    def test_complete_training_job_uses_runtime_accuracy_fields_for_classification_best_metrics(self):
        self.dataset_service.create_project("runtime-cls-demo", ["ok", "ng"], task_type="classify_single")
        uploaded = self.dataset_service.upload_raw("runtime-cls-demo", jpg_bytes(), original_filename="panel-ok.jpg")
        self.dataset_service.set_image_labels("runtime-cls-demo", uploaded["img_id"], [{"label": "ok", "confidence": 1.0}])
        version = self.training_service.create_dataset_version_from_live_dataset(
            "runtime-cls-demo",
            {
                "version_name": "runtime-cls-demo-v1",
                "task_type": "classify_single",
                "split_config": {"train": 70, "val": 20, "test": 10},
                "preprocessing_config": {"resize_mode": "keep"},
                "augmentation_config": {"profile": "baseline"},
                "resize_mode": "keep",
            },
        )
        with patch.object(
            self.training_service,
            "_validate_training_config",
            return_value={
                "family": "yolo26",
                "size": "n",
                "base_checkpoint": "yolo26n-cls.pt",
                "epochs": 2,
                "patience": 30,
                "imgsz": 224,
                "batch": 2,
                "workers": 1,
                "training_mode": "standard",
                "task_type": "classify_single",
            },
        ):
            job = self.training_service.create_training_job(
                {
                    "job_name": "runtime-panel-classifier",
                    "dataset_version_id": version["id"],
                    "family": "yolo26",
                    "size": "n",
                    "base_checkpoint": "yolo26n-cls.pt",
                    "epochs": 2,
                    "imgsz": 224,
                    "batch": 2,
                    "workers": 1,
                    "training_mode": "standard",
                    "task_type": "classify_single",
                },
                inference_active=False,
            )

        self.training_service.append_metric(
            job["id"],
            {"epoch": 1, "map50": 0.76, "map50_95": 0.9, "val_loss": 0.2},
        )
        self.training_service.append_metric(
            job["id"],
            {"epoch": 2, "map50": 0.91, "map50_95": 0.95, "val_loss": 0.8},
        )

        completed = self.training_service.complete_training_job(
            job["id"],
            best_model_path="/tmp/best.pt",
            last_checkpoint_path="/tmp/last.pt",
        )

        self.assertEqual(completed["metrics_latest"]["epoch"], 2)
        self.assertEqual(completed["metrics_best"]["epoch"], 2)
        self.assertEqual(completed["metrics_best"]["map50"], 0.91)
        self.assertEqual(completed["metrics_best"]["map50_95"], 0.95)

    def test_metrics_are_json_safe_when_training_outputs_nan(self):
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

        self.training_service.append_metric(job["id"], {"epoch": 1, "val_loss": math.nan, "map50": math.inf})

        metrics = self.training_service.list_training_metrics(job["id"])
        latest = self.training_service.get_training_job(job["id"])["metrics_latest"]
        self.assertEqual(metrics[0]["val_loss"], 0.0)
        self.assertEqual(metrics[0]["map50"], 0.0)
        self.assertEqual(latest["val_loss"], 0.0)
        self.assertEqual(latest["map50"], 0.0)


if __name__ == "__main__":
    unittest.main()
