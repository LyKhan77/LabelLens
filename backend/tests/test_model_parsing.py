import unittest

import numpy as np

from backend.services.model import ModelService
from backend.utils.drawing import draw_detections


class _T:
    """Minimal tensor-like wrapper supporting .cpu().numpy()/indexing used by the parser."""

    def __init__(self, arr):
        self.a = np.array(arr)

    def cpu(self):
        return self

    def numpy(self):
        return self.a

    def tolist(self):
        return self.a.tolist()

    def __getitem__(self, i):
        return _T(self.a[i])

    def __len__(self):
        return len(self.a)

    def __int__(self):
        return int(self.a)

    def __float__(self):
        return float(self.a)


class _Box:
    def __init__(self, xyxy, cls_id, conf):
        self.xyxy = _T([xyxy])
        self.cls = _T([cls_id])
        self.conf = _T([conf])


class _Keypoints:
    def __init__(self, xy, conf):
        self.xy = [_T(row) for row in xy]
        self.conf = [_T(row) for row in conf]


class _Probs:
    def __init__(self, top5, top5conf):
        self.top5 = top5
        self.top5conf = _T(top5conf)


class _Result:
    def __init__(self, names, boxes=None, keypoints=None, probs=None, masks=None):
        self.names = names
        self.boxes = boxes
        self.keypoints = keypoints
        self.probs = probs
        self.masks = masks
        self.orig_shape = (480, 640)


class ModelParsingTest(unittest.TestCase):
    def setUp(self):
        self.svc = ModelService()

    def test_parse_pose_attaches_keypoints(self):
        self.svc.current_task_type = "pose"
        boxes = [_Box([10, 10, 50, 90], 0, 0.9)]
        kpts = _Keypoints(xy=[[[20, 20], [30, 40]]], conf=[[0.8, 0.2]])
        result = _Result({0: "person"}, boxes=boxes, keypoints=kpts)

        out = self.svc._parse_results([result], 12.0)

        self.assertEqual(len(out["detections"]), 1)
        self.assertEqual(out["detections"][0]["keypoints"], [[20.0, 20.0, 0.8], [30.0, 40.0, 0.2]])
        self.assertNotIn("classification", out)

    def test_parse_classification_returns_top1_and_top5(self):
        self.svc.current_task_type = "classify_single"
        probs = _Probs(top5=[2, 0, 1], top5conf=[0.7, 0.2, 0.1])
        result = _Result({0: "close-range", 1: "long-range", 2: "medium-range"}, probs=probs)

        out = self.svc._parse_results([result], 5.0)

        self.assertEqual(out["detections"], [])
        self.assertEqual(out["classification"]["top1"], {"label": "medium-range", "confidence": 0.7})
        self.assertEqual(len(out["classification"]["top5"]), 3)
        self.assertEqual(out["stats"]["total_objects"], 1)

    def test_parse_detect_has_no_keypoints_or_classification(self):
        self.svc.current_task_type = "detect"
        boxes = [_Box([10, 10, 50, 90], 0, 0.9)]
        result = _Result({0: "bolt"}, boxes=boxes)

        out = self.svc._parse_results([result], 8.0)

        self.assertEqual(len(out["detections"]), 1)
        self.assertNotIn("keypoints", out["detections"][0])
        self.assertNotIn("classification", out)


class DrawTaskTest(unittest.TestCase):
    def test_draw_pose_keypoints_changes_image(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        det = {"box": [10, 10, 50, 90], "label": "person", "confidence": 0.9,
               "keypoints": [[20, 20, 0.9], [40, 60, 0.9]]}
        out = draw_detections(img, [det])
        self.assertTrue(np.any(out != 0))

    def test_draw_classification_banner(self):
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        out = draw_detections(img, [], classification={"top1": {"label": "cat", "confidence": 0.88}})
        # banner drawn in top-left region
        self.assertTrue(np.any(out[0:30, 0:100] != 0))


if __name__ == "__main__":
    unittest.main()
