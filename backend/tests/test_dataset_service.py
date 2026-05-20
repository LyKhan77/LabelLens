import os
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from backend.services.dataset import DatasetService


def jpg_bytes(width: int = 32, height: int = 24) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 1] = 180
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


class DatasetServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch("backend.services.dataset.DATASETS_DIR", self.tmp.name)
        self.patcher.start()
        self.service = DatasetService()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_list_images_includes_image_url_dimensions_source_and_unlabeled_status(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(), source="video")

        result = self.service.list_images("demo")

        self.assertEqual(result["total"], 1)
        image = result["images"][0]
        self.assertEqual(image["img_id"], saved["img_id"])
        self.assertEqual(image["status"], "unlabeled")
        self.assertEqual(image["source"], "video")
        self.assertEqual(image["width"], 32)
        self.assertEqual(image["height"], 24)
        self.assertEqual(
            image["image_url"],
            f"/api/datasets/demo/images/{saved['img_id']}/file",
        )

    def test_label_image_marks_unlabeled_image_as_reviewable(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes())

        labeled = self.service.label_image(
            "demo",
            saved["img_id"],
            [{"box": [1, 2, 10, 12], "label": "part", "confidence": 0.9}],
        )
        result = self.service.list_images("demo")

        self.assertEqual(labeled["detections_count"], 1)
        self.assertEqual(result["images"][0]["status"], "accepted")
        self.assertEqual(result["images"][0]["accepted"], 1)
        self.assertEqual(result["images"][0]["rejected"], 0)


if __name__ == "__main__":
    unittest.main()
