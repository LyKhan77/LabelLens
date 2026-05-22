from __future__ import annotations

import gc
import logging
import os
import shutil
import threading
import time

import numpy as np
import torch
from ultralytics import SAM

from backend.config import SAM_DEVICE, SAM_ENABLED, SAM_MODEL
from backend.utils.masks import extract_mask_polygon, extract_mask_rle

logger = logging.getLogger(__name__)


class SAMService:
    def __init__(self):
        self.model: SAM | None = None
        self.device = SAM_DEVICE
        self._loaded = False
        self._loading = False
        self._lock = threading.Lock()

    def _ensure_loaded(self):
        if not SAM_ENABLED:
            raise RuntimeError("SAM is disabled (SAM_ENABLED=false)")
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if self._loading:
                raise RuntimeError("SAM model is currently loading")
            self._loading = True
            try:
                logger.info("Loading SAM2.1 on cuda:%s...", self.device)
                model_path = f"models/{SAM_MODEL}"
                local_exists = os.path.isfile(model_path)
                source = model_path if local_exists else SAM_MODEL
                self.model = SAM(source)
                # If auto-downloaded, move to models/
                if not local_exists:
                    os.makedirs("models", exist_ok=True)
                    cwd_spawn = SAM_MODEL
                    if os.path.isfile(cwd_spawn):
                        shutil.move(cwd_spawn, model_path)
                self._loaded = True
                logger.info("SAM2.1 loaded successfully.")
            except Exception:
                self.model = None
                logger.exception("Failed to load SAM model")
                raise
            finally:
                self._loading = False

    def get_status(self) -> dict:
        return {
            "enabled": SAM_ENABLED,
            "loaded": self._loaded,
            "loading": self._loading,
            "model": SAM_MODEL if self._loaded else None,
            "device": f"cuda:{self.device}",
        }

    def predict_mask_from_bbox(
        self,
        image: np.ndarray,
        bbox: list[float],
    ) -> dict:
        """Run SAM with a single bbox prompt. Returns mask data."""
        self._ensure_loaded()
        t0 = time.perf_counter()
        results = self.model.predict(
            source=image,
            bboxes=[[bbox]],
            device=self.device,
            verbose=False,
        )
        inference_ms = (time.perf_counter() - t0) * 1000
        return self._parse_single(results, inference_ms)

    def predict_masks_from_bboxes(
        self,
        image: np.ndarray,
        bboxes: list[list[float]],
    ) -> list[dict]:
        """Run SAM with multiple bbox prompts. Returns list of mask data."""
        self._ensure_loaded()
        results = []
        t_total = 0.0
        for bbox in bboxes:
            t0 = time.perf_counter()
            res = self.model.predict(
                source=image,
                bboxes=[[bbox]],
                device=self.device,
                verbose=False,
            )
            t_total += (time.perf_counter() - t0) * 1000
            results.append(self._parse_single(res, 0))
        if results:
            avg_ms = t_total / len(bboxes)
            for r in results:
                r["inference_ms"] = round(avg_ms, 1)
        return results

    def _parse_single(self, results, inference_ms: float) -> dict:
        mask_data = {}
        if results and len(results) > 0:
            r = results[0]
            masks = getattr(r, "masks", None)
            orig_shape = getattr(r, "orig_shape", None)
            if masks is not None and len(masks) > 0:
                box = [0, 0, orig_shape[1], orig_shape[0]] if orig_shape is not None else None
                rle = extract_mask_rle(masks, 0, orig_shape, box)
                if rle:
                    mask_data["mask_rle"] = rle
                polygon = extract_mask_polygon(masks, 0, orig_shape, box)
                if polygon:
                    mask_data["mask"] = polygon
        mask_data["inference_ms"] = round(inference_ms, 1)
        return mask_data

    def unload(self):
        if self.model is not None:
            del self.model
            self.model = None
        self._loaded = False
        gc.collect()
        if torch.cuda.is_available():
            with torch.cuda.device(self.device):
                torch.cuda.empty_cache()
        logger.info("SAM unloaded from cuda:%s", self.device)


sam_service = SAMService()
