import json
import os
from pathlib import Path

os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", os.getenv("LABELLENS_CUDA_VISIBLE_DEVICES", "1,2"))

MODEL_PATH = os.getenv("MODEL_PATH", "models/yoloe-26l-seg.pt")
SAM_MODEL = os.getenv("SAM_MODEL", "sam2.1_l.pt")
SAM_ENABLED = os.getenv("SAM_ENABLED", "true").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "3131"))
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Load persisted GPU config, fall back to env defaults
_gpu_config_path = Path(os.getenv("GPU_CONFIG_PATH", "gpu_config.json"))
if _gpu_config_path.exists():
    try:
        _cfg = json.loads(_gpu_config_path.read_text())
        DEVICE = str(_cfg.get("yoloe_device", os.getenv("DEVICE", "0")))
        SAM_DEVICE = str(_cfg.get("sam_device", os.getenv("SAM_DEVICE", "1")))
    except (json.JSONDecodeError, OSError):
        DEVICE = os.getenv("DEVICE", "0")
        SAM_DEVICE = os.getenv("SAM_DEVICE", "1")
else:
    DEVICE = os.getenv("DEVICE", "0")
    SAM_DEVICE = os.getenv("SAM_DEVICE", "1")
