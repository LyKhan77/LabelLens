from __future__ import annotations

import json
import logging
import os

import torch

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class GpuService:
    """Detects CUDA GPUs and manages inference / training GPU configuration."""

    def __init__(self):
        self._inference_config_path = os.getenv("GPU_CONFIG_PATH", "gpu_config.json")
        self._training_config_path = os.getenv(
            "TRAINING_GPU_CONFIG_PATH", "training_gpu_config.json"
        )

    # ------------------------------------------------------------------
    # GPU detection
    # ------------------------------------------------------------------

    def detect_gpus(self) -> list[dict]:
        """Return a list of dicts describing every visible CUDA GPU."""
        if not torch.cuda.is_available():
            return []

        gpus: list[dict] = []
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append(
                {
                    "index": i,
                    "name": props.name,
                    "vram_total_mb": round(props.total_memory / (1024 * 1024)),
                    "vram_used_mb": round(
                        torch.cuda.memory_allocated(i) / (1024 * 1024)
                    ),
                    "uuid": props.uuid if hasattr(props, "uuid") else None,
                }
            )
        return gpus

    # ------------------------------------------------------------------
    # Inference GPU config
    # ------------------------------------------------------------------

    def get_inference_config(self) -> dict:
        """Load inference GPU config.

        Priority: persisted ``gpu_config.json`` > env vars ``DEVICE`` / ``SAM_DEVICE``.
        """
        if os.path.isfile(self._inference_config_path):
            try:
                with open(self._inference_config_path) as f:
                    data = json.load(f)
                return {
                    "yoloe_device": data["yoloe_device"],
                    "sam_device": data["sam_device"],
                }
            except Exception:
                logger.warning(
                    "Failed to read %s; falling back to env vars",
                    self._inference_config_path,
                )

        return {
            "yoloe_device": int(os.getenv("DEVICE", "0")),
            "sam_device": int(os.getenv("SAM_DEVICE", "1")),
        }

    def save_inference_config(self, yoloe_device: int, sam_device: int) -> dict:
        """Validate device indices against detected GPUs and persist config."""
        detected = self.detect_gpus()
        valid_indices = {g["index"] for g in detected}

        if not detected:
            raise RuntimeError("No CUDA GPUs detected")

        for label, value in (("yoloe_device", yoloe_device), ("sam_device", sam_device)):
            if value not in valid_indices:
                raise ValueError(
                    f"Invalid {label} '{value}'; "
                    f"available indices: {sorted(valid_indices)}"
                )

        data = {"yoloe_device": yoloe_device, "sam_device": sam_device}
        with open(self._inference_config_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved inference GPU config: %s", data)
        return data

    # ------------------------------------------------------------------
    # Training GPU config
    # ------------------------------------------------------------------

    def get_training_config(self) -> dict:
        """Load training GPU config.

        Priority: persisted ``training_gpu_config.json`` > env vars.
        """
        if os.path.isfile(self._training_config_path):
            try:
                with open(self._training_config_path) as f:
                    data = json.load(f)
                return {
                    "training_mode": data["training_mode"],
                    "training_device": data["training_device"],
                    "visible_devices": data["visible_devices"],
                    "amp": data["amp"],
                }
            except Exception:
                logger.warning(
                    "Failed to read %s; falling back to env vars",
                    self._training_config_path,
                )

        high_speed = os.getenv("TRAINING_MODE", "standard") == "high_speed"
        if high_speed:
            visible = os.getenv("TRAIN_VISIBLE_DEVICES_HIGH_SPEED", "1,2")
            amp = _env_bool("TRAIN_AMP_HIGH_SPEED", False)
        else:
            visible = os.getenv("TRAIN_VISIBLE_DEVICES_STANDARD", "1")
            amp = _env_bool("TRAIN_AMP_STANDARD", True)

        return {
            "training_mode": "high_speed" if high_speed else "standard",
            "training_device": visible,
            "visible_devices": visible,
            "amp": amp,
        }

    def save_training_config(
        self,
        training_mode: str,
        training_device: str,
        visible_devices: str,
        amp: bool,
    ) -> dict:
        """Validate training GPU params and persist config."""
        detected = self.detect_gpus()
        valid_indices = {str(g["index"]) for g in detected}

        if not detected:
            raise RuntimeError("No CUDA GPUs detected")

        mode = training_mode.lower()
        if mode not in ("standard", "high_speed"):
            raise ValueError(
                f"Invalid training_mode '{training_mode}'; must be 'standard' or 'high_speed'"
            )

        device_list = [d.strip() for d in visible_devices.split(",")]
        for dev in device_list:
            if dev not in valid_indices:
                raise ValueError(
                    f"Invalid device '{dev}' in visible_devices; "
                    f"available indices: {sorted(valid_indices, key=int)}"
                )

        gpu_count = len(device_list)
        if mode == "standard" and gpu_count != 1:
            raise ValueError(
                f"Standard mode requires exactly 1 GPU, got {gpu_count}"
            )
        if mode == "high_speed" and gpu_count < 2:
            raise ValueError(
                f"High-Speed mode requires at least 2 GPUs, got {gpu_count}"
            )

        data = {
            "training_mode": mode,
            "training_device": training_device,
            "visible_devices": visible_devices,
            "amp": amp,
        }
        with open(self._training_config_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved training GPU config: %s", data)
        return data


gpu_service = GpuService()
