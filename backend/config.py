import os

MODEL_PATH = os.getenv("MODEL_PATH", "models/yoloe-26l-seg.pt")
SAM_DEVICE = os.getenv("SAM_DEVICE", "1")
SAM_MODEL = os.getenv("SAM_MODEL", "sam2.1_l.pt")
SAM_ENABLED = os.getenv("SAM_ENABLED", "true").lower() == "true"
DEVICE = os.getenv("DEVICE", "0")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "3131"))
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
