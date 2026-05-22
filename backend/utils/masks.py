from __future__ import annotations

import cv2
import numpy as np
from ultralytics.utils import ops


def extract_mask_rle(masks, index: int, orig_shape, box: list[float]) -> dict | None:
    if masks is None or getattr(masks, "data", None) is None or index >= len(masks.data):
        return None
    binary = mask_bitmap(masks.data[index], orig_shape, box)
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
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1, "counts": counts}


def mask_bitmap(mask_data, orig_shape, box: list[float] | None = None) -> np.ndarray | None:
    if orig_shape is None:
        orig_h, orig_w = mask_data.shape[-2:]
    else:
        orig_h, orig_w = int(orig_shape[0]), int(orig_shape[1])
    mask_tensor = mask_data.unsqueeze(0).unsqueeze(0).float()
    scaled = ops.scale_masks(mask_tensor, (orig_h, orig_w))[0, 0]
    binary = (scaled > 0.5).detach().cpu().numpy().astype(np.uint8)
    if box is not None:
        binary = clip_binary_to_box(binary, box)
    if binary.max() == 0:
        return None
    return binary


def clip_binary_to_box(binary: np.ndarray, box: list[float]) -> np.ndarray:
    h, w = binary.shape[:2]
    x1 = max(0, min(w, int(np.floor(box[0]))))
    y1 = max(0, min(h, int(np.floor(box[1]))))
    x2 = max(0, min(w, int(np.ceil(box[2]))))
    y2 = max(0, min(h, int(np.ceil(box[3]))))
    clipped = np.zeros_like(binary, dtype=np.uint8)
    if x2 <= x1 or y2 <= y1:
        return clipped
    clipped[y1:y2, x1:x2] = binary[y1:y2, x1:x2]
    return clipped


def extract_mask_polygon(masks, index: int, orig_shape, box: list[float]) -> list[list[float]] | None:
    if masks is None:
        return None
    if getattr(masks, "data", None) is not None and index < len(masks.data):
        polygon = polygon_from_mask_bitmap(masks.data[index], orig_shape, box)
        if polygon:
            return polygon
    masks_xy = getattr(masks, "xy", [])
    if index < len(masks_xy):
        return clip_polygon_points(masks_xy[index].tolist(), box)
    return None


def clip_polygon_points(points, box: list[float]) -> list[list[float]] | None:
    x1, y1, x2, y2 = box
    clipped = [
        [round(float(min(max(x, x1), x2)), 1), round(float(min(max(y, y1), y2)), 1)]
        for x, y in points
    ]
    return clipped if len(clipped) >= 3 else None


def polygon_from_mask_bitmap(mask_data, orig_shape, box: list[float]) -> list[list[float]] | None:
    binary = mask_bitmap(mask_data, orig_shape, box)
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
