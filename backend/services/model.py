import gc
import os
import shutil
import tempfile
import time

os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

import cv2
import numpy as np
import torch
from ultralytics import YOLO, YOLOE
from ultralytics.models.yolo.yoloe.predict import YOLOEVPSegPredictor

from backend.config import DEVICE
from backend.utils.masks import extract_mask_rle, extract_mask_polygon
from backend.utils.postprocess import nms_dedup

MODEL_MODES = {
    "prompt": "models/yoloe-26l-seg.pt",
    "free": "models/yoloe-26l-seg-pf.pt",
}


class ModelService:
    def __init__(self):
        self.model: YOLOE | YOLO | None = None
        self.current_mode: str | None = None
        self.model_path: str | None = None
        self.current_classes: list[str] = []
        self._is_seg_model = False
        self.current_task_type = 'detect'
        self._vpe_labels: list[str] = []
        self.device = DEVICE

    def set_device(self, device: str | int):
        """Update the device for future predictions and model loading."""
        s = str(device)
        self.device = s if s.startswith("cuda") or s == "cpu" else f"cuda:{s}"

    def load_model(self, mode: str):
        if mode not in MODEL_MODES:
            raise ValueError(f"Unknown mode: {mode}. Must be one of {list(MODEL_MODES)}")

        model_path = MODEL_MODES[mode]
        local_exists = os.path.isfile(model_path)
        source = model_path if local_exists else os.path.basename(model_path)

        # Unload previous model
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            torch.cuda.empty_cache()

        self.model = YOLOE(source)
        self.model.to(self.device)

        # If auto-downloaded, move to models/ and clean up CWD spawn
        if not local_exists:
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            # Check CWD (where ultralytics drops auto-downloads)
            cwd_spawn = os.path.basename(model_path)
            if os.path.isfile(cwd_spawn):
                shutil.move(cwd_spawn, model_path)

        self._is_seg_model = "seg" in model_path.lower()
        self.current_task_type = 'segment' if self._is_seg_model else 'detect'
        self.current_mode = mode
        self.model_path = model_path
        self.current_classes = []
        self._vpe_labels = []

    def load_custom_model(self, model_path: str, class_names: list[str], task_type: str = 'detect'):
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Custom model not found: {model_path}")

        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            torch.cuda.empty_cache()

        self.model = YOLO(model_path)

        model_task = getattr(self.model, 'task', None)
        self.current_task_type = task_type or model_task or 'detect'
        self._is_seg_model = self.current_task_type == 'segment' or model_task == 'segment'
        self.current_mode = "custom"
        self.model_path = model_path
        self.current_classes = list(class_names)
        self._vpe_labels = []

    def get_status(self) -> dict:
        return {
            "mode": self.current_mode,
            "loaded": self.model is not None,
            "model_name": os.path.basename(self.model_path) if self.model_path else None,
            "device": self.device,
            "class_names": self.current_classes if self.current_mode == "custom" else [],
            "task_type": self.current_task_type,
        }

    def _require_model(self):
        if self.model is None:
            raise RuntimeError("No model loaded. Select a mode first.")

    def predict_text(
        self,
        image: np.ndarray,
        labels: list[str],
        conf: float = 0.5,
    ) -> dict:
        self._require_model()
        if self.current_mode == "custom":
            t0 = time.perf_counter()
            results = self.model.predict(
                image, conf=conf, verbose=False, retina_masks=True
            )
            inference_ms = (time.perf_counter() - t0) * 1000
            return self._parse_results(results, inference_ms)

        if set(labels) != set(self.current_classes):
            self.model.set_classes(labels)
            self.current_classes = list(labels)

        t0 = time.perf_counter()
        results = self.model.predict(
            image, conf=conf, verbose=False, retina_masks=True
        )
        inference_ms = (time.perf_counter() - t0) * 1000

        return self._parse_results(results, inference_ms)

    def predict_free(
        self,
        image: np.ndarray,
        conf: float = 0.5,
    ) -> dict:
        self._require_model()
        t0 = time.perf_counter()
        results = self.model.predict(
            image, conf=conf, verbose=False, retina_masks=True
        )
        inference_ms = (time.perf_counter() - t0) * 1000
        return self._parse_results(results, inference_ms)

    def setup_visual_prompt(
        self,
        refer_image: np.ndarray,
        bboxes: list[list[float]],
        cls: list[str],
    ) -> list[str]:
        """Extract VPE from refer_image and set on model. Call once before predict_with_vpe()."""
        self._require_model()
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
                conf=0.01,
                verbose=False,
                retina_masks=True,
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
        self._require_model()
        t0 = time.perf_counter()
        results = self.model.predict(
            image, conf=conf, verbose=False, retina_masks=True
        )
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
                    mask_rle = extract_mask_rle(masks, i, orig_shape, xyxy)
                    if mask_rle:
                        detection["mask_rle"] = mask_rle

                    mask = extract_mask_polygon(masks, i, orig_shape, xyxy)
                    if mask:
                        detection["mask"] = mask
                    boxes_data.append(detection)
                    classes_count[label] = classes_count.get(label, 0) + 1

        boxes_data = nms_dedup(boxes_data, iou_threshold=0.5)

        # Recount after dedup
        classes_count.clear()
        for det in boxes_data:
            classes_count[det["label"]] = classes_count.get(det["label"], 0) + 1

        return {
            "detections": boxes_data,
            "stats": {
                "total_objects": len(boxes_data),
                "classes_count": classes_count,
                "inference_ms": round(inference_ms, 1),
            },
        }


model_service = ModelService()
