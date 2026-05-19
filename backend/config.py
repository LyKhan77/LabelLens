import os

MODEL_PATH = os.getenv("MODEL_PATH", "models/yoloe-26s-seg.pt")
DEVICE = os.getenv("DEVICE", "0")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "3131"))
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
