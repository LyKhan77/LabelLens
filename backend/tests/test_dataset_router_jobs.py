import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import dataset


class DatasetLabelJobStatusTest(unittest.TestCase):
    def tearDown(self):
        dataset.label_jobs.clear()

    def test_new_label_job_status_includes_item_log(self):
        job = dataset._new_job("demo")

        self.assertEqual(job["items"], [])

    def test_create_dataset_accepts_task_type_without_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("backend.services.dataset.DATASETS_DIR", tmp):
                client = TestClient(app)

                response = client.post("/api/datasets", data={
                    "name": "classifier",
                    "task_type": "classify_multi",
                })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task_type"], "classify_multi")
        self.assertEqual(payload["task_config"]["classification_mode"], "multi")
        self.assertEqual(payload["class_to_id"], {})

    def test_infer_next_visual_prompt_returns_candidates_without_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "source.jpg")
            target_path = os.path.join(tmp, "target.jpg")
            image = np.zeros((24, 32, 3), dtype=np.uint8)
            cv2.imwrite(source_path, image)
            cv2.imwrite(target_path, image)

            def fake_get_image(_name, img_id):
                if img_id == "img1":
                    return {"image_path": source_path}
                if img_id == "img2":
                    return {"image_path": target_path}
                return None

            with (
                patch.object(dataset.dataset_service, "get_image", side_effect=fake_get_image),
                patch.object(dataset.dataset_service, "label_image") as label_image,
                patch.object(dataset.model_service, "model", object()),
                patch.object(dataset.model_service, "setup_visual_prompt") as setup_visual_prompt,
                patch.object(dataset.model_service, "predict_with_vpe", return_value={
                    "detections": [
                        {"box": [2, 3, 12, 14], "label": "part", "confidence": 0.82, "cls_id": 0},
                    ],
                }),
            ):
                result = asyncio.run(dataset.infer_next_visual_prompt(
                    "demo",
                    "img1",
                    {
                        "target_img_id": "img2",
                        "prompts": [{"box": [1, 2, 10, 12], "label": "part"}],
                        "confidence": 0.55,
                    },
                ))

            setup_visual_prompt.assert_called_once()
            label_image.assert_not_called()
            self.assertEqual(result["source_img_id"], "img1")
            self.assertEqual(result["target_img_id"], "img2")
            self.assertEqual(result["candidates"][0]["label"], "part")
            self.assertFalse(result["candidates"][0]["accepted"])
            self.assertTrue(result["candidates"][0]["assisted"])
            self.assertEqual(result["candidates"][0]["source"], "visual_prompt")


if __name__ == "__main__":
    unittest.main()
