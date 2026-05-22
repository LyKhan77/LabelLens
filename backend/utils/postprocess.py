from __future__ import annotations


def _iou(box_a: list[float], box_b: list[float]) -> float:
    """Compute IoU between two [x1, y1, x2, y2] boxes."""
    xi1 = max(box_a[0], box_b[0])
    yi1 = max(box_a[1], box_b[1])
    xi2 = min(box_a[2], box_b[2])
    yi2 = min(box_a[3], box_b[3])

    inter = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
    if inter == 0:
        return 0.0

    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return inter / (area_a + area_b - inter)


def nms_dedup(
    detections: list[dict],
    iou_threshold: float = 0.5,
) -> list[dict]:
    """Remove duplicate detections using per-class NMS.

    Keeps the highest-confidence detection when multiple detections
    of the same class overlap beyond *iou_threshold*.
    """
    if len(detections) <= 1:
        return detections

    # Group by class
    by_class: dict[str, list[dict]] = {}
    for det in detections:
        key = det.get("label", "")
        by_class.setdefault(key, []).append(det)

    kept: list[dict] = []
    for group in by_class.values():
        # Sort descending by confidence
        group.sort(key=lambda d: d.get("confidence", 0), reverse=True)

        for det in group:
            box = det.get("box")
            if box is None:
                kept.append(det)
                continue

            suppressed = False
            for winner in kept:
                if winner.get("label") != det.get("label"):
                    continue
                if _iou(box, winner.get("box", [])) > iou_threshold:
                    suppressed = True
                    break

            if not suppressed:
                kept.append(det)

    return kept
