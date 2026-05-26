import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend import train_worker


class TrainWorkerTest(unittest.TestCase):
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
