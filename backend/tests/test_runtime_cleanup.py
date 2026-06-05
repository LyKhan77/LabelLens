import tempfile
import unittest
from pathlib import Path

from backend.scripts.reset_runtime_data import reset_runtime_data


class RuntimeCleanupTest(unittest.TestCase):
    def test_reset_removes_datasets_and_train_tune_but_keeps_model_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "datasets" / "demo").mkdir(parents=True)
            (root / "datasets" / "demo" / "meta.json").write_text("{}")
            (root / "datasets" / "_train_tune" / "jobs").mkdir(parents=True)
            (root / "datasets" / "_train_tune" / "jobs" / "job.json").write_text("{}")
            (root / "models").mkdir()
            (root / "models" / "yoloe-26l-seg.pt").write_text("weights")

            result = reset_runtime_data(root)

            self.assertFalse((root / "datasets" / "demo").exists())
            self.assertFalse((root / "datasets" / "_train_tune" / "jobs" / "job.json").exists())
            self.assertTrue((root / "datasets").exists())
            self.assertTrue((root / "datasets" / "_train_tune").exists())
            self.assertTrue((root / "models" / "yoloe-26l-seg.pt").exists())
            self.assertIn("datasets/demo", result["removed"])
            self.assertIn("datasets/_train_tune", result["removed"])


if __name__ == "__main__":
    unittest.main()
