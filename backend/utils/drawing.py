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


def draw_detections(
    image: np.ndarray,
    detections: list[dict],
    show_labels: bool = True,
    show_bbox: bool = True,
) -> np.ndarray:
    annotated = image.copy()

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
