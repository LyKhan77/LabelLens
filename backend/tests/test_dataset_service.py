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

    def test_create_project_assigns_class_colors_to_initial_classes(self):
        meta = self.service.create_project("demo", ["car", "truck"])

        self.assertEqual(set(meta["class_colors"]), {"car", "truck"})
        self.assertRegex(meta["class_colors"]["car"], r"^#[0-9A-F]{6}$")
        self.assertRegex(meta["class_colors"]["truck"], r"^#[0-9A-F]{6}$")
        self.assertNotEqual(meta["class_colors"]["car"], meta["class_colors"]["truck"])

        listed = self.service.list_projects()[0]
        self.assertEqual(listed["class_colors"], meta["class_colors"])

    def test_create_project_requires_task_type_and_stores_task_metadata(self):
        meta = self.service.create_project("poses", task_type="pose", task_config={
            "pose_template": {
                "name": "Box Corners",
                "keypoint_names": ["top_left", "top_right", "bottom_right", "bottom_left"],
                "skeleton": [[0, 1], [1, 2], [2, 3], [3, 0]],
                "flip_idx": [1, 0, 3, 2],
                "kpt_shape": [4, 3],
            },
        })

        self.assertEqual(meta["schema_version"], 2)
        self.assertEqual(meta["task_type"], "pose")
        self.assertEqual(meta["class_to_id"], {})
        self.assertEqual(meta["class_colors"], {})
        self.assertEqual(meta["task_config"]["pose_template"]["kpt_shape"], [4, 3])

        listed = self.service.list_projects()[0]
        self.assertEqual(listed["schema_version"], 2)
        self.assertEqual(listed["task_type"], "pose")
        self.assertEqual(listed["task_config"]["pose_template"]["name"], "Box Corners")

    def test_create_project_rejects_invalid_task_type(self):
        with self.assertRaises(ValueError):
            self.service.create_project("bad", task_type="caption")

    def test_create_pose_project_rejects_invalid_template(self):
        with self.assertRaises(ValueError):
            self.service.create_project("bad-pose", task_type="pose", task_config={
                "pose_template": {
                    "name": "Broken",
                    "keypoint_names": ["a", "b"],
                    "skeleton": [[0, 2]],
                    "flip_idx": [0, 1],
                    "kpt_shape": [2, 3],
                },
            })

    def test_new_classes_receive_persisted_colors_from_rapid_inference_and_manual_labels(self):
        self.service.create_project("demo")
        saved = self.service.upload_raw("demo", jpg_bytes(width=64, height=48))

        self.service.label_image(
            "demo",
            saved["img_id"],
            [
                {"box": [4, 6, 28, 30], "label": "car", "confidence": 0.91},
                {"box": [30, 10, 50, 32], "label": "truck", "confidence": 0.72},
            ],
        )
        self.service.add_detection(
            "demo",
            saved["img_id"],
            {"label": "bottle", "box": [8, 8, 20, 24]},
        )

        meta = self.service._read_meta("demo")

        self.assertEqual(set(meta["class_colors"]), {"car", "truck", "bottle"})
        self.assertEqual(len(set(meta["class_colors"].values())), 3)
        for color in meta["class_colors"].values():
            self.assertRegex(color, r"^#[0-9A-F]{6}$")

    def test_update_class_color_persists_hex_color(self):
        self.service.create_project("demo", ["car"])

        meta = self.service.update_class_color("demo", "car", "#7C3AED")

        self.assertEqual(meta["class_colors"]["car"], "#7C3AED")
        self.assertEqual(self.service._read_meta("demo")["class_colors"]["car"], "#7C3AED")

    def test_update_class_color_rejects_invalid_color(self):
        self.service.create_project("demo", ["car"])

        with self.assertRaises(ValueError):
            self.service.update_class_color("demo", "car", "purple")

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

    def test_classify_single_accepts_one_image_label(self):
        self.service.create_project("cls", task_type="classify_single")
        saved = self.service.upload_raw("cls", jpg_bytes())

        ann = self.service.set_image_labels("cls", saved["img_id"], [{"label": "ok", "confidence": 1.0}])

        self.assertEqual(len(ann["labels"]), 1)
        self.assertEqual(ann["labels"][0]["label"], "ok")
        self.assertTrue(ann["labeled"])
        self.assertEqual(self.service._read_meta("cls")["class_to_id"], {"ok": 0})

    def test_list_images_counts_classification_labels_as_annotations(self):
        self.service.create_project("cls", task_type="classify_single")
        saved = self.service.upload_raw("cls", jpg_bytes())
        self.service.set_image_labels("cls", saved["img_id"], [{"label": "ok", "confidence": 1.0}])

        result = self.service.list_images("cls")

        image = result["images"][0]
        self.assertEqual(image["status"], "accepted")
        self.assertEqual(image["accepted"], 1)
        self.assertEqual(image["rejected"], 0)

    def test_classify_single_rejects_multiple_labels(self):
        self.service.create_project("cls", task_type="classify_single")
        saved = self.service.upload_raw("cls", jpg_bytes())

        with self.assertRaises(ValueError):
            self.service.set_image_labels("cls", saved["img_id"], [{"label": "ok"}, {"label": "bad"}])

    def test_classify_multi_accepts_multiple_image_labels(self):
        self.service.create_project("multi", task_type="classify_multi")
        saved = self.service.upload_raw("multi", jpg_bytes())

        ann = self.service.set_image_labels("multi", saved["img_id"], [{"label": "red"}, {"label": "damaged"}])

        self.assertEqual([label["label"] for label in ann["labels"]], ["red", "damaged"])
        self.assertEqual(self.service._read_meta("multi")["class_to_id"], {"red": 0, "damaged": 1})

    def test_pose_annotation_persists_bbox_keypoints_and_visibility(self):
        self.service.create_project("pose", task_type="pose")
        saved = self.service.upload_raw("pose", jpg_bytes(width=100, height=80))

        ann = self.service.add_pose(
            "pose",
            saved["img_id"],
            {
                "label": "box",
                "box": [10, 10, 50, 50],
                "keypoints": [
                    {"name": "top_left", "x": 10, "y": 10, "visibility": "visible"},
                    {"name": "top_right", "x": 50, "y": 10, "visibility": "occluded"},
                    {"name": "bottom_right", "x": 50, "y": 50, "visibility": "visible"},
                    {"name": "bottom_left", "x": 10, "y": 50, "visibility": "missing"},
                ],
            },
        )

        self.assertEqual(ann["poses"][0]["box"], [10.0, 10.0, 50.0, 50.0])
        self.assertEqual(ann["poses"][0]["keypoints"][1]["visibility"], "occluded")
        self.assertEqual(self.service._read_meta("pose")["class_to_id"], {"box": 0})

    def test_update_pose_changes_box_keypoints_and_label(self):
        self.service.create_project("pose", task_type="pose")
        saved = self.service.upload_raw("pose", jpg_bytes(width=100, height=80))
        kps = [
            {"name": "top_left", "x": 10, "y": 10, "visibility": "visible"},
            {"name": "top_right", "x": 50, "y": 10, "visibility": "visible"},
            {"name": "bottom_right", "x": 50, "y": 50, "visibility": "visible"},
            {"name": "bottom_left", "x": 10, "y": 50, "visibility": "visible"},
        ]
        self.service.add_pose("pose", saved["img_id"], {"label": "box", "box": [10, 10, 50, 50], "keypoints": kps})
        pose_id = self.service.get_image("pose", saved["img_id"])["annotations"]["poses"][0]["id"]

        moved = [{**kp, "x": kp["x"] + 5} for kp in kps]
        ann = self.service.update_pose(
            "pose", saved["img_id"], pose_id,
            {"label": "person", "box": [12, 12, 60, 60], "keypoints": moved},
        )
        pose = ann["poses"][0]
        self.assertEqual(pose["label"], "person")
        self.assertEqual(pose["box"], [12.0, 12.0, 60.0, 60.0])
        self.assertEqual(pose["keypoints"][0]["x"], 15.0)

    def test_update_pose_unknown_id_returns_none(self):
        self.service.create_project("pose", task_type="pose")
        saved = self.service.upload_raw("pose", jpg_bytes(width=100, height=80))
        self.assertIsNone(self.service.update_pose("pose", saved["img_id"], 999, {"label": "x"}))

    def test_delete_pose_removes_and_recomputes_labeled(self):
        self.service.create_project("pose", task_type="pose")
        saved = self.service.upload_raw("pose", jpg_bytes(width=100, height=80))
        kps = [
            {"name": "top_left", "x": 10, "y": 10, "visibility": "visible"},
            {"name": "top_right", "x": 50, "y": 10, "visibility": "visible"},
            {"name": "bottom_right", "x": 50, "y": 50, "visibility": "visible"},
            {"name": "bottom_left", "x": 10, "y": 50, "visibility": "visible"},
        ]
        self.service.add_pose("pose", saved["img_id"], {"label": "box", "box": [10, 10, 50, 50], "keypoints": kps})
        pose_id = self.service.get_image("pose", saved["img_id"])["annotations"]["poses"][0]["id"]

        ann = self.service.delete_pose("pose", saved["img_id"], pose_id)
        self.assertEqual(ann["poses"], [])
        self.assertFalse(ann["labeled"])
        self.assertIsNone(self.service.delete_pose("pose", saved["img_id"], pose_id))

    def test_export_yolo_for_single_label_classification_writes_class_folders(self):
        self.service.create_project("cls", task_type="classify_single")
        saved = self.service.upload_raw("cls", jpg_bytes(), original_filename="sample.jpg")
        self.service.set_image_labels("cls", saved["img_id"], [{"label": "ok"}])

        zip_bytes = self.service.export_yolo("cls", split=1.0)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            self.assertIn("train/ok/sample.jpg", names)
            self.assertIn("labellens.json", names)

    def test_export_yolo_for_multi_label_classification_writes_manifest(self):
        self.service.create_project("multi", task_type="classify_multi")
        saved = self.service.upload_raw("multi", jpg_bytes(), original_filename="sample.jpg")
        self.service.set_image_labels("multi", saved["img_id"], [{"label": "red"}, {"label": "damaged"}])

        zip_bytes = self.service.export_yolo("multi", split=1.0)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            labels_csv = zf.read("labels.csv").decode()
            self.assertIn("filename,labels", labels_csv)
            self.assertIn("images/sample.jpg", labels_csv)
            self.assertIn("red|damaged", labels_csv)
            self.assertIn("labellens.json", zf.namelist())

    def test_export_yolo_for_pose_writes_pose_labels_and_yaml(self):
        self.service.create_project("pose", task_type="pose")
        saved = self.service.upload_raw("pose", jpg_bytes(width=100, height=80), original_filename="pose.jpg")
        self.service.add_pose(
            "pose",
            saved["img_id"],
            {
                "label": "box",
                "box": [10, 10, 50, 50],
                "keypoints": [
                    {"name": "top_left", "x": 10, "y": 10, "visibility": "visible"},
                    {"name": "top_right", "x": 50, "y": 10, "visibility": "occluded"},
                    {"name": "bottom_right", "x": 50, "y": 50, "visibility": "visible"},
                    {"name": "bottom_left", "x": 10, "y": 50, "visibility": "missing"},
                ],
            },
        )

        zip_bytes = self.service.export_yolo("pose", split=1.0)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            yaml_text = zf.read("dataset.yaml").decode()
            label_text = zf.read("labels/train/img_0001.txt").decode()
            self.assertIn("kpt_shape: [4, 3]", yaml_text)
            self.assertIn("flip_idx: [1, 0, 3, 2]", yaml_text)
            self.assertIn("kpt_names:", yaml_text)
            self.assertEqual(len(label_text.split()), 17)

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

    def test_delete_class_removes_classification_labels(self):
        self.service.create_project("cls", task_type="classify_multi")
        saved = self.service.upload_raw("cls", jpg_bytes(width=64, height=48))
        self.service.set_image_labels(
            "cls",
            saved["img_id"],
            [{"label": "long-range"}, {"label": "close-range"}],
        )

        meta = self.service.delete_class("cls", "long-range")
        image = self.service.get_image("cls", saved["img_id"])

        self.assertEqual(meta["class_to_id"], {"close-range": 1})
        self.assertEqual([label["label"] for label in image["annotations"]["labels"]], ["close-range"])
        self.assertTrue(image["annotations"]["labeled"])

    def test_delete_class_removes_pose_instances(self):
        self.service.create_project("pose", task_type="pose")
        saved = self.service.upload_raw("pose", jpg_bytes(width=100, height=80))
        self.service.add_pose(
            "pose",
            saved["img_id"],
            {
                "label": "person",
                "box": [10, 10, 50, 50],
                "keypoints": [
                    {"name": "top_left", "x": 10, "y": 10, "visibility": "visible"},
                    {"name": "top_right", "x": 50, "y": 10, "visibility": "visible"},
                    {"name": "bottom_right", "x": 50, "y": 50, "visibility": "visible"},
                    {"name": "bottom_left", "x": 10, "y": 50, "visibility": "visible"},
                ],
            },
        )

        meta = self.service.delete_class("pose", "person")
        image = self.service.get_image("pose", saved["img_id"])

        self.assertEqual(meta["class_to_id"], {})
        self.assertEqual(image["annotations"]["poses"], [])
        self.assertFalse(image["annotations"]["labeled"])

    def test_rename_class_updates_classification_labels_and_pose_instances(self):
        self.service.create_project("cls", task_type="classify_single")
        cls_saved = self.service.upload_raw("cls", jpg_bytes(width=64, height=48))
        self.service.set_image_labels("cls", cls_saved["img_id"], [{"label": "old"}])

        self.service.rename_class("cls", "old", "new")
        cls_image = self.service.get_image("cls", cls_saved["img_id"])

        self.assertEqual(cls_image["annotations"]["labels"][0]["label"], "new")

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
