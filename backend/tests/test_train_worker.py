import os
import tempfile
import unittest
import importlib
import math
from types import SimpleNamespace
from unittest.mock import patch

from backend import train_worker


class TrainWorkerTest(unittest.TestCase):
    def test_backend_config_defaults_hide_4090_from_labellens(self):
        with patch.dict(os.environ, {}, clear=True):
            import backend.config as config

            importlib.reload(config)
            self.assertEqual(os.environ["CUDA_DEVICE_ORDER"], "PCI_BUS_ID")
            self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "1,2")
            self.assertEqual(config.DEVICE, "0")
            self.assertEqual(config.SAM_DEVICE, "1")
        importlib.reload(config)

    def test_resolve_training_device_policy_uses_5080_visible_devices(self):
        with patch.dict(os.environ, {}, clear=True):
            standard = train_worker.resolve_training_device_policy({"training_mode": "standard"})
            high_speed = train_worker.resolve_training_device_policy({"training_mode": "high_speed"})

        self.assertEqual(standard["cuda_visible_devices"], "1")
        self.assertEqual(standard["device"], "1")
        self.assertEqual(standard["local_device"], "0")
        self.assertTrue(standard["amp"])
        self.assertEqual(standard["cuda_device_order"], "PCI_BUS_ID")
        self.assertEqual(high_speed["cuda_visible_devices"], "1,2")
        self.assertEqual(high_speed["device"], "1,2")
        self.assertEqual(high_speed["local_device"], "0,1")
        self.assertFalse(high_speed["amp"])
        self.assertEqual(high_speed["cuda_device_order"], "PCI_BUS_ID")

    def test_inject_ddp_patch_enables_unused_parameter_detection(self):
        content = 'before\nif __name__ == "__main__":\n    trainer.train()\n'
        patched = train_worker._inject_ddp_find_unused_patch(content)

        self.assertIn('find_unused_parameters', patched)
        self.assertIn('DistributedDataParallel', patched)
        self.assertEqual(train_worker._inject_ddp_find_unused_patch(patched), patched)

    def test_ddp_patch_is_disabled_by_default(self):
        emitted = []

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(train_worker, "emit", side_effect=emitted.append),
            patch.object(train_worker, "patch_ultralytics_ddp_find_unused_parameters") as patch_ddp,
        ):
            train_worker.maybe_patch_ultralytics_ddp_find_unused_parameters()

        patch_ddp.assert_not_called()
        self.assertTrue(any(item["event"] == "log_line" and "DDP find_unused_parameters patch disabled" in item["line"] for item in emitted))

    def test_ddp_patch_is_enabled_with_env_flag(self):
        emitted = []

        with (
            patch.dict(os.environ, {"LABELLENS_TRAIN_DDP_FIND_UNUSED": "1"}, clear=True),
            patch.object(train_worker, "emit", side_effect=emitted.append),
            patch.object(train_worker, "patch_ultralytics_ddp_find_unused_parameters") as patch_ddp,
        ):
            train_worker.maybe_patch_ultralytics_ddp_find_unused_parameters()

        patch_ddp.assert_called_once()
        self.assertTrue(any(item["event"] == "log_line" and "DDP find_unused_parameters patch enabled" in item["line"] for item in emitted))

    def test_metric_value_rejects_non_finite_values(self):
        self.assertEqual(train_worker.metric_value({"val/seg_loss": "nan"}, ["val/seg_loss"]), 0.0)
        self.assertEqual(train_worker.metric_value({"val/seg_loss": "inf"}, ["val/seg_loss"]), 0.0)
        self.assertEqual(train_worker.metric_value({"val/seg_loss": -math.inf}, ["val/seg_loss"]), 0.0)

    def test_emit_traceback_streams_error_and_stack_lines(self):
        emitted = []

        def capture(event):
            emitted.append(event)

        with patch.object(train_worker, "emit", side_effect=capture):
            try:
                raise RuntimeError("boom")
            except RuntimeError as exc:
                train_worker.emit_traceback(exc, "train_runner")

        self.assertGreaterEqual(len(emitted), 2)
        self.assertEqual(emitted[0]["event"], "log_line")
        self.assertIn("[train_runner] boom", emitted[0]["line"])
        self.assertTrue(any("Traceback" in item["line"] for item in emitted[1:]))
        self.assertTrue(any("RuntimeError: boom" in item["line"] for item in emitted[1:]))

    def test_actual_train_rejects_wrong_checkpoint_task_before_training(self):
        emitted = []
        train_called = []

        class SegmentModel:
            task = "segment"

            def train(self, **_kwargs):
                train_called.append(True)

        with tempfile.TemporaryDirectory() as tmp:
            ultralytics = SimpleNamespace(YOLO=lambda _checkpoint: SegmentModel())
            job = {
                "output_dir": os.path.join(tmp, "run"),
                "base_checkpoint": "models/yoloe-26n-seg.pt",
                "training_mode": "standard",
            }
            with (
                patch.dict("sys.modules", {"ultralytics": ultralytics}),
                patch.object(train_worker, "emit", side_effect=emitted.append),
            ):
                train_worker.actual_train(job, {"dataset_yaml": "dataset.yaml"})

        self.assertFalse(train_called)
        self.assertTrue(any(item["event"] == "job_failed" for item in emitted))
        self.assertTrue(any("detect checkpoint" in item.get("error", "") for item in emitted))


    def test_actual_train_forwards_online_augmentation_args(self):
        train_called = []

        class DetectModel:
            task = "detect"

            def train(self, **kwargs):
                train_called.append(kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            ultralytics = SimpleNamespace(YOLO=lambda _checkpoint: DetectModel())
            job = {
                "output_dir": os.path.join(tmp, "run"),
                "base_checkpoint": "models/yolo26n.pt",
                "training_mode": "standard",
                "task_type": "detect",
                "epochs": 1,
            }
            version = {
                "dataset_yaml": "dataset.yaml",
                "augmentation_config": {
                    "mode": "hybrid",
                    "online": {
                        "degrees": 7,
                        "fliplr": 0.5,
                        "mosaic": 0.25,
                        "close_mosaic": 10.0,
                        "unsupported": 99,
                    },
                },
            }
            with (
                patch.dict("sys.modules", {"ultralytics": ultralytics}),
                patch.object(train_worker, "emit"),
            ):
                train_worker.actual_train(job, version)

        self.assertEqual(train_called[0]["degrees"], 7)
        self.assertEqual(train_called[0]["fliplr"], 0.5)
        self.assertEqual(train_called[0]["mosaic"], 0.25)
        self.assertEqual(train_called[0]["close_mosaic"], 10)
        self.assertIsInstance(train_called[0]["close_mosaic"], int)
        self.assertEqual(train_called[0]["device"], "1")
        self.assertTrue(train_called[0]["amp"])
        self.assertNotIn("unsupported", train_called[0])

    def test_actual_train_forwards_patience_and_auto_batch(self):
        train_called = []

        class DetectModel:
            task = "detect"

            def train(self, **kwargs):
                train_called.append(kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            ultralytics = SimpleNamespace(YOLO=lambda _checkpoint: DetectModel())
            job = {
                "output_dir": os.path.join(tmp, "run"),
                "base_checkpoint": "models/yolo26n.pt",
                "training_mode": "standard",
                "task_type": "detect",
                "epochs": 100,
                "patience": 25,
                "batch": -1,
            }
            with (
                patch.dict("sys.modules", {"ultralytics": ultralytics}),
                patch.object(train_worker, "emit"),
            ):
                train_worker.actual_train(job, {"dataset_yaml": "dataset.yaml"})

        self.assertEqual(train_called[0]["patience"], 25)
        self.assertEqual(train_called[0]["batch"], -1)

    def test_actual_train_uses_local_devices_for_high_speed_visible_5080s(self):
        train_called = []

        class DetectModel:
            task = "detect"

            def train(self, **kwargs):
                train_called.append(kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            ultralytics = SimpleNamespace(YOLO=lambda _checkpoint: DetectModel())
            job = {
                "output_dir": os.path.join(tmp, "run"),
                "base_checkpoint": "models/yolo26n.pt",
                "training_mode": "high_speed",
                "task_type": "detect",
                "epochs": 1,
            }
            with (
                patch.dict("sys.modules", {"ultralytics": ultralytics}),
                patch.dict(os.environ, {}, clear=True),
                patch.object(train_worker, "emit"),
            ):
                train_worker.actual_train(job, {"dataset_yaml": "dataset.yaml"})
                self.assertEqual(os.environ["CUDA_DEVICE_ORDER"], "PCI_BUS_ID")
                self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "1,2")

        self.assertEqual(train_called[0]["device"], "1,2")
        self.assertFalse(train_called[0]["amp"])

    def test_actual_train_accepts_segment_checkpoint_for_segment_job(self):
        emitted = []
        train_called = []

        class SegmentModel:
            task = "segment"

            def train(self, **kwargs):
                train_called.append(kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            ultralytics = SimpleNamespace(YOLO=lambda _checkpoint: SegmentModel())
            job = {
                "output_dir": os.path.join(tmp, "run"),
                "base_checkpoint": "models/yolo26n-seg.pt",
                "training_mode": "standard",
                "task_type": "segment",
                "epochs": 1,
            }
            with (
                patch.dict("sys.modules", {"ultralytics": ultralytics}),
                patch.object(train_worker, "emit", side_effect=emitted.append),
            ):
                train_worker.actual_train(job, {"dataset_yaml": "dataset.yaml"})

        self.assertTrue(train_called)
        self.assertFalse(any(item.get("event") == "job_failed" for item in emitted))


if __name__ == "__main__":
    unittest.main()
