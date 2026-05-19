import base64

import cv2
import numpy as np


def frame_to_base64(frame: np.ndarray, format: str = ".jpg", quality: int = 85) -> str:
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if format == ".jpg" else []
    ok, buf = cv2.imencode(format, frame, params)
    if not ok:
        raise ValueError("Failed to encode frame")
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def decode_image(file_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img
