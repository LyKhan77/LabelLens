import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services.training_runtime import TrainingRuntime


class TrainingRuntimeTest(unittest.TestCase):
    def test_preflight_rejects_missing_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset_dir = os.path.join(tmp, "dataset")
            os.makedirs(os.path.join(dataset_dir, "images", "train"))
            os.makedirs(os.path.join(dataset_dir, "labels", "train"))
            with open(os.path.join(dataset_dir, "dataset.yaml"), "w") as f:
                f.write("path: .\ntrain: images/train\nval: images/val\nnames:\n  0: bolt\n")
            with open(os.path.join(dataset_dir, "images", "train", "a.jpg"), "wb") as f:
                f.write(b"image")

            runtime = TrainingRuntime()

            with self.assertRaisesRegex(RuntimeError, "checkpoint not found"):
                runtime._preflight_job(
                    {
                        "base_checkpoint": os.path.join(tmp, "missing.pt"),
                        "output_dir": os.path.join(tmp, "run"),
                    },
                    {"dataset_yaml": os.path.join(dataset_dir, "dataset.yaml")},
                )

    def test_preflight_accepts_classification_dataset_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset_dir = os.path.join(tmp, "dataset")
            class_dir = os.path.join(dataset_dir, "train", "bolt")
            os.makedirs(class_dir)
            with open(os.path.join(class_dir, "a.jpg"), "wb") as f:
                f.write(b"image")
            checkpoint = os.path.join(tmp, "yolo11n-cls.pt")
            with open(checkpoint, "wb") as f:
                f.write(b"weights")

            runtime = TrainingRuntime()

            with patch("backend.services.training_runtime.os.getenv", return_value="1"):
                runtime._preflight_job(
                    {
                        "base_checkpoint": checkpoint,
                        "output_dir": os.path.join(tmp, "run"),
                    },
                    {"task_type": "classify_single", "dataset_yaml": dataset_dir},
                )

    def test_ensure_base_checkpoint_downloads_known_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                runtime = TrainingRuntime()

                def fake_download(path):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(b"weights")
                    return path

                job = {"id": "j1", "base_checkpoint": "yolo11n-cls.pt"}
                with (
                    patch("ultralytics.utils.downloads.attempt_download_asset", side_effect=fake_download),
                    patch("backend.services.training_runtime.training_service.update_training_job") as update,
                    patch("backend.services.training_runtime.training_event_hub.publish"),
                ):
                    resolved = runtime._ensure_base_checkpoint(job, "yolo11n-cls.pt")

                self.assertEqual(resolved, os.path.join("models", "yolo11n-cls.pt"))
                self.assertTrue(os.path.isfile(resolved))
                update.assert_called_once_with("j1", base_checkpoint=resolved)
            finally:
                os.chdir(cwd)

    def test_ensure_base_checkpoint_rejects_unknown_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                runtime = TrainingRuntime()
                with self.assertRaisesRegex(RuntimeError, "checkpoint not found"):
                    runtime._ensure_base_checkpoint({"id": "j2", "base_checkpoint": "notamodel.pt"}, "notamodel.pt")
            finally:
                os.chdir(cwd)

    def test_terminate_process_group_escalates_to_kill_after_timeout(self):
        runtime = TrainingRuntime()
        process = SimpleNamespace(pid=1234, poll=lambda: None, terminate=lambda: None, kill=lambda: None)

        with (
            patch("backend.services.training_runtime.os.killpg") as killpg,
            patch("backend.services.training_runtime.time.time", side_effect=[0, 6]),
            patch("backend.services.training_runtime.time.sleep"),
        ):
            runtime._terminate_process_group(process)

        self.assertEqual(killpg.call_count, 2)
        self.assertEqual(killpg.call_args_list[0].args[0], 1234)
        self.assertEqual(killpg.call_args_list[1].args[0], 1234)


if __name__ == "__main__":
    unittest.main()
