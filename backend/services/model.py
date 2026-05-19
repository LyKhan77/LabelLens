import os
import tempfile
import time

os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

import cv2
import numpy as np
from ultralytics import YOLOE
from ultralytics.models.yolo.yoloe.predict import YOLOEVPSegPredictor
from ultralytics.utils import ops

from backend.config import MODEL_PATH, DEVICE


class ModelService:
    def __init__(self):
        self.model: YOLOE | None = None
        self.current_classes: list[str] = []
        self._is_seg_model = False
        self._vpe_labels: list[str] = []
        self.device = DEVICE

    def load(self, model_path: str = MODEL_PATH):
        self.model = YOLOE(model_path)
        self._is_seg_model = "seg" in model_path.lower()

    def predict_text(
        self,
        image: np.ndarray,
        labels: list[str],
        conf: float = 0.5,
    ) -> dict:
        if set(labels) != set(self.current_classes):
            self.model.set_classes(labels)
            self.current_classes = list(labels)

        t0 = time.perf_counter()
        results = self.model.predict(image, conf=conf, device=self.device, verbose=False)
        inference_ms = (time.perf_counter() - t0) * 1000

        return self._parse_results(results, inference_ms)

    def setup_visual_prompt(
        self,
        refer_image: np.ndarray,
        bboxes: list[list[float]],
        cls: list[str],
    ) -> list[str]:
        """Extract VPE from refer_image and set on model. Call once before predict_with_vpe()."""
        # Map string labels to integer indices
        unique_labels: list[str] = []
        label_to_idx: dict[str, int] = {}
        cls_indices: list[int] = []

        for label in cls:
            if label not in label_to_idx:
                label_to_idx[label] = len(unique_labels)
                unique_labels.append(label)
            cls_indices.append(label_to_idx[label])

        visual_prompts = {"bboxes": bboxes, "cls": cls_indices}
        predictor_cls = YOLOEVPSegPredictor if self._is_seg_model else None

        # Save refer_image to temp file (get_vpe works better with paths)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            cv2.imwrite(f.name, refer_image)
            refer_path = f.name

        try:
            # This call extracts VPE via get_vpe(), sets classes on model,
            # resets predictor, then runs standard predict on the refer_image itself.
            # We only care about the VPE setup side-effect.
            self.model.predict(
                source=refer_path,
                visual_prompts=visual_prompts,
                refer_image=refer_path,
                predictor=predictor_cls,
                device=self.device,
                conf=0.01,
                verbose=False,
            )
        finally:
            os.unlink(refer_path)

        self._vpe_labels = unique_labels
        return unique_labels

    def predict_with_vpe(
        self,
        image: np.ndarray,
        conf: float = 0.5,
    ) -> dict:
        """Predict on a frame using pre-set VPE from setup_visual_prompt()."""
        t0 = time.perf_counter()
        results = self.model.predict(image, conf=conf, device=self.device, verbose=False)
        inference_ms = (time.perf_counter() - t0) * 1000

        result = self._parse_results(results, inference_ms)

        # Remap generic names (object0, object1...) to actual labels
        for det in result["detections"]:
            idx = int(det.get("cls_id", -1))
            if 0 <= idx < len(self._vpe_labels):
                det["label"] = self._vpe_labels[idx]

        return result

    def predict_visual(
        self,
        image: np.ndarray,
        refer_image: np.ndarray,
        bboxes: list[list[float]],
        cls: list[str],
        conf: float = 0.5,
    ) -> dict:
        """One-shot visual prompt detection. For repeated calls, use setup + predict_with_vpe."""
        self.setup_visual_prompt(refer_image, bboxes, cls)
        return self.predict_with_vpe(image, conf)

    def _parse_results(self, results, inference_ms: float) -> dict:
        boxes_data = []
        classes_count: dict[str, int] = {}

        if results and len(results) > 0:
            r = results[0]
            masks = getattr(r, "masks", None)
            orig_shape = getattr(r, "orig_shape", None)
            if r.boxes is not None and len(r.boxes) > 0:
                for i, box in enumerate(r.boxes):
                    xyxy = box.xyxy[0].cpu().numpy().tolist()
                    cls_id = int(box.cls[0])
                    label = r.names.get(cls_id, str(cls_id))
                    confidence = float(box.conf[0])
                    detection = {
                        "box": [round(v, 1) for v in xyxy],
                        "label": label,
                        "confidence": round(confidence, 3),
                        "cls_id": cls_id,
                    }
                    mask_rle = self._extract_mask_rle(masks, i, orig_shape)
                    if mask_rle:
                        detection["mask_rle"] = mask_rle

                    mask = self._extract_mask_polygon(masks, i, orig_shape)
                    if mask:
                        detection["mask"] = mask
                    boxes_data.append(detection)
                    classes_count[label] = classes_count.get(label, 0) + 1

        return {
            "detections": boxes_data,
            "stats": {
                "total_objects": len(boxes_data),
                "classes_count": classes_count,
                "inference_ms": round(inference_ms, 1),
            },
        }

    def _extract_mask_rle(self, masks, index: int, orig_shape) -> dict | None:
        if masks is None or getattr(masks, "data", None) is None or index >= len(masks.data):
            return None

        binary = self._mask_bitmap(masks.data[index], orig_shape)
        if binary is None:
            return None

        ys, xs = np.where(binary > 0)
        if len(xs) == 0 or len(ys) == 0:
            return None

        x1, x2 = int(xs.min()), int(xs.max()) + 1
        y1, y2 = int(ys.min()), int(ys.max()) + 1
        crop = binary[y1:y2, x1:x2].astype(np.uint8).ravel()

        counts: list[int] = []
        current = 0
        run = 0
        for value in crop:
            value = int(value)
            if value == current:
                run += 1
            else:
                counts.append(run)
                current = value
                run = 1
        counts.append(run)

        return {
            "x": x1,
            "y": y1,
            "width": x2 - x1,
            "height": y2 - y1,
            "counts": counts,
        }

    def _mask_bitmap(self, mask_data, orig_shape) -> np.ndarray | None:
        if orig_shape is None:
            orig_h, orig_w = mask_data.shape[-2:]
        else:
            orig_h, orig_w = int(orig_shape[0]), int(orig_shape[1])

        mask_tensor = mask_data.unsqueeze(0).unsqueeze(0).float()
        scaled = ops.scale_masks(mask_tensor, (orig_h, orig_w))[0, 0]
        binary = (scaled > 0).detach().cpu().numpy().astype(np.uint8)
        if binary.max() == 0:
            return None
        return binary

    def _extract_mask_polygon(self, masks, index: int, orig_shape) -> list[list[float]] | None:
        if masks is None:
            return None

        if getattr(masks, "data", None) is not None and index < len(masks.data):
            polygon = self._polygon_from_mask_bitmap(masks.data[index], orig_shape)
            if polygon:
                return polygon

        masks_xy = getattr(masks, "xy", [])
        if index < len(masks_xy):
            return [[round(float(x), 1), round(float(y), 1)] for x, y in masks_xy[index].tolist()]

        return None

    def _polygon_from_mask_bitmap(self, mask_data, orig_shape) -> list[list[float]] | None:
        binary = self._mask_bitmap(mask_data, orig_shape)
        if binary is None:
            return None

        binary = binary * 255
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return None

        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 4:
            return None

        epsilon = max(1.0, cv2.arcLength(contour, True) * 0.0015)
        contour = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(contour) < 3:
            return None

        return [[round(float(x), 1), round(float(y), 1)] for x, y in contour]


model_service = ModelService()
