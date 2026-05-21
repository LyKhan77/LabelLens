import io
import os
import tempfile
import unittest
import zipfile
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

    def test_list_images_includes_detection_preview_for_gallery_overlays(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))

        self.service.label_image(
            "demo",
            saved["img_id"],
            [
                {
                    "box": [4, 6, 28, 30],
                    "label": "car",
                    "confidence": 0.91,
                    "mask": [[4, 6], [28, 6], [28, 30], [4, 30]],
                },
                {
                    "box": [30, 10, 50, 32],
                    "label": "truck",
                    "confidence": 0.72,
                },
            ],
        )

        result = self.service.list_images("demo")

        preview = result["images"][0]["detections_preview"]
        self.assertEqual(len(preview), 2)
        self.assertEqual(preview[0]["box"], [4, 6, 28, 30])
        self.assertEqual(preview[0]["label"], "car")
        self.assertEqual(preview[0]["confidence"], 0.91)
        self.assertTrue(preview[0]["accepted"])
        self.assertEqual(preview[0]["mask"], [[4, 6], [28, 6], [28, 30], [4, 30]])


    def test_add_manual_detection_to_unlabeled_image_updates_classes_and_stats(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))

        ann = self.service.add_detection(
            "demo",
            saved["img_id"],
            {"label": "car", "box": [4, 6, 28, 30]},
        )
        det = ann["detections"][0]
        stats = self.service.list_projects()[0]["stats"]
        meta = self.service._read_meta("demo")

        self.assertEqual(ann["labeled"], True)
        self.assertEqual(det["id"], 0)
        self.assertEqual(det["box"], [4.0, 6.0, 28.0, 30.0])
        self.assertEqual(det["label"], "car")
        self.assertEqual(det["confidence"], 1.0)
        self.assertEqual(det["cls_id"], 0)
        self.assertTrue(det["accepted"])
        self.assertTrue(det["manual"])
        self.assertEqual(meta["class_to_id"], {"car": 0})
        self.assertEqual(stats["accepted"], 1)

    def test_add_assisted_detection_persists_visual_prompt_metadata(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))

        ann = self.service.add_detection(
            "demo",
            saved["img_id"],
            {
                "label": "bolt",
                "box": [4, 6, 28, 30],
                "assisted": True,
                "source": "visual_prompt",
                "confidence": 0.82,
            },
        )
        det = ann["detections"][0]

        self.assertTrue(det["assisted"])
        self.assertEqual(det["source"], "visual_prompt")
        self.assertEqual(det["confidence"], 0.82)

    def test_update_detection_label_and_bbox_clamps_box_and_removes_stale_mask(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))
        self.service.label_image(
            "demo",
            saved["img_id"],
            [{
                "box": [4, 6, 28, 30],
                "label": "car",
                "confidence": 0.91,
                "mask": [[4, 6], [28, 6], [28, 30], [4, 30]],
                "mask_rle": {"x": 4, "y": 6, "width": 24, "height": 24, "counts": [1, 2]},
            }],
        )

        ann = self.service.update_detection(
            "demo",
            saved["img_id"],
            0,
            {"label": "truck", "box": [-5, 8, 80, 40]},
        )
        det = ann["detections"][0]
        meta = self.service._read_meta("demo")

        self.assertEqual(det["label"], "truck")
        self.assertEqual(det["cls_id"], 1)
        self.assertEqual(det["box"], [0.0, 8.0, 64.0, 40.0])
        self.assertNotIn("mask", det)
        self.assertNotIn("mask_rle", det)
        self.assertEqual(meta["class_to_id"], {"car": 0, "truck": 1})

    def test_update_detection_label_only_keeps_existing_bbox(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))
        self.service.add_detection(
            "demo",
            saved["img_id"],
            {"label": "car", "box": [4, 6, 28, 30]},
        )

        ann = self.service.update_detection(
            "demo",
            saved["img_id"],
            0,
            {"label": "van"},
        )
        det = ann["detections"][0]

        self.assertEqual(det["label"], "van")
        self.assertEqual(det["box"], [4.0, 6.0, 28.0, 30.0])

    def test_delete_detection_removes_it_from_export(self):
        self.service.create_project("demo", ["car", "truck"])
        saved = self.service.save_image(
            "demo",
            jpg_bytes(width=64, height=48),
            [
                {"box": [4, 6, 28, 30], "label": "car", "confidence": 0.91},
                {"box": [30, 10, 50, 32], "label": "truck", "confidence": 0.72},
            ],
        )

        ann = self.service.delete_detection("demo", saved["img_id"], 1)
        zip_bytes = self.service.export_yolo("demo")

        self.assertEqual([d["label"] for d in ann["detections"]], ["car"])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            label_names = [n for n in zf.namelist() if n.endswith(".txt")]
            label_text = zf.read(label_names[0]).decode()
        self.assertIn("0 ", label_text)
        self.assertNotIn("1 ", label_text)

    def test_delete_assisted_detection_removes_it_from_export(self):
        self.service.create_project("demo", ["bolt"])
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))
        self.service.add_detection(
            "demo",
            saved["img_id"],
            {
                "box": [4, 6, 28, 30],
                "label": "bolt",
                "confidence": 0.82,
                "assisted": True,
                "source": "visual_prompt",
            },
        )

        ann = self.service.delete_detection("demo", saved["img_id"], 0)
        zip_bytes = self.service.export_yolo("demo")

        self.assertEqual(ann["detections"], [])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            label_names = [n for n in zf.namelist() if n.endswith(".txt")]
        self.assertEqual(label_names, [])

    def test_rejected_detection_is_excluded_from_export(self):
        self.service.create_project("demo", ["car", "truck"])
        saved = self.service.save_image(
            "demo",
            jpg_bytes(width=64, height=48),
            [
                {"box": [4, 6, 28, 30], "label": "car", "confidence": 0.91},
                {"box": [30, 10, 50, 32], "label": "truck", "confidence": 0.72},
            ],
        )

        self.service.review_image("demo", saved["img_id"], [{"id": 1, "accepted": False}])
        zip_bytes = self.service.export_yolo("demo")

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            label_names = [n for n in zf.namelist() if n.endswith(".txt")]
            label_text = zf.read(label_names[0]).decode()
        self.assertIn("0 ", label_text)
        self.assertNotIn("1 ", label_text)


if __name__ == "__main__":
    unittest.main()
