import cv2
import numpy as np


COLORS = [
    (62, 207, 142),   # primary emerald
    (36, 180, 126),   # primary deep
    (107, 1, 194),    # accent purple
    (100, 79, 193),   # accent violet
    (255, 219, 19),   # accent yellow
    (220, 38, 38),    # red
    (37, 99, 235),    # blue
    (234, 88, 12),    # orange
]
MASK_ALPHA = 0.40


def draw_detections(
    image: np.ndarray,
    detections: list[dict],
    show_labels: bool = True,
    show_bbox: bool = True,
    show_masks: bool = False,
) -> np.ndarray:
    annotated = image.copy()

    if show_masks:
        _draw_masks(annotated, detections)

    for i, det in enumerate(detections):
        x1, y1, x2, y2 = [int(v) for v in det["box"]]
        label = det["label"]
        conf = det["confidence"]
        color = COLORS[i % len(COLORS)]

        if show_bbox:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        if show_labels:
            text = f"{label} {conf:.0%}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 1
            (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)

            text_y = max(y1 - 6, th + 6)
            cv2.rectangle(
                annotated,
                (x1, text_y - th - 4),
                (x1 + tw + 4, text_y + 4),
                color,
                -1,
            )
            cv2.putText(
                annotated, text, (x1 + 2, text_y), font, font_scale, (255, 255, 255), thickness
            )

    return annotated


def _draw_masks(image: np.ndarray, detections: list[dict]) -> None:
    ordered = sorted(
        enumerate(detections),
        key=lambda item: (item[1]["box"][2] - item[1]["box"][0])
        * (item[1]["box"][3] - item[1]["box"][1]),
        reverse=True,
    )

    for index, det in ordered:
        mask = _detection_mask(det, image.shape[:2])
        if mask is None or not np.any(mask):
            continue

        color = np.array(COLORS[index % len(COLORS)], dtype=np.uint8)
        overlay = image.copy()
        overlay[mask > 0] = color
        cv2.addWeighted(overlay, MASK_ALPHA, image, 1 - MASK_ALPHA, 0, dst=image)


def _detection_mask(det: dict, image_shape: tuple[int, int]) -> np.ndarray | None:
    if det.get("mask_rle"):
        return _mask_from_rle(det["mask_rle"], image_shape, det["box"])
    if det.get("mask"):
        return _mask_from_polygon(det["mask"], image_shape, det["box"])
    return None


def _mask_from_rle(mask_rle: dict, image_shape: tuple[int, int], box: list[float]) -> np.ndarray | None:
    img_h, img_w = image_shape
    width = int(mask_rle.get("width", 0))
    height = int(mask_rle.get("height", 0))
    counts = mask_rle.get("counts", [])
    if width <= 0 or height <= 0 or not counts:
        return None

    flat = np.zeros(width * height, dtype=np.uint8)
    current = 0
    pixel = 0
    for count in counts:
        count = int(count)
        next_pixel = min(flat.size, pixel + max(0, count))
        if current == 1 and next_pixel > pixel:
            flat[pixel:next_pixel] = 1
        pixel = next_pixel
        current = 0 if current == 1 else 1
        if pixel >= flat.size:
            break

    crop = flat.reshape((height, width))
    full = np.zeros((img_h, img_w), dtype=np.uint8)
    x = int(mask_rle.get("x", 0))
    y = int(mask_rle.get("y", 0))
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(img_w, x + width)
    y2 = min(img_h, y + height)
    if x2 <= x1 or y2 <= y1:
        return None

    crop_x1 = x1 - x
    crop_y1 = y1 - y
    full[y1:y2, x1:x2] = crop[crop_y1:crop_y1 + (y2 - y1), crop_x1:crop_x1 + (x2 - x1)]
    return _clip_mask_to_box(full, box)


def _mask_from_polygon(points: list[list[float]], image_shape: tuple[int, int], box: list[float]) -> np.ndarray | None:
    if len(points) < 3:
        return None

    img_h, img_w = image_shape
    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    polygon = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
    cv2.fillPoly(mask, [polygon], 1)
    return _clip_mask_to_box(mask, box)


def _clip_mask_to_box(mask: np.ndarray, box: list[float]) -> np.ndarray:
    h, w = mask.shape[:2]
    x1 = max(0, min(w, int(np.floor(box[0]))))
    y1 = max(0, min(h, int(np.floor(box[1]))))
    x2 = max(0, min(w, int(np.ceil(box[2]))))
    y2 = max(0, min(h, int(np.ceil(box[3]))))

    clipped = np.zeros_like(mask, dtype=np.uint8)
    if x2 <= x1 or y2 <= y1:
        return clipped
    clipped[y1:y2, x1:x2] = mask[y1:y2, x1:x2]
    return clipped
