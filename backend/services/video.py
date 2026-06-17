import tempfile

import cv2
import numpy as np

from backend.services.model import model_service
from backend.utils.drawing import draw_detections
from backend.utils.encoding import decode_image, frame_to_base64


def process_video(
    file_bytes: bytes,
    prompt_type: str,
    labels: list[str] | None = None,
    refer_image: np.ndarray | None = None,
    bboxes: list[list[float]] | None = None,
    cls: list[str] | None = None,
    conf: float = 0.5,
    show_labels: bool = True,
    show_bbox: bool = True,
    show_masks: bool = False,
    sample_fps: int = 5,
) -> dict:
    # Setup visual prompt once (VPE extraction) if using visual mode
    if prompt_type == "visual" and refer_image is not None:
        model_service.setup_visual_prompt(
            refer_image=refer_image,
            bboxes=bboxes or [],
            cls=cls or [],
        )

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
        tmp.write(file_bytes)
        tmp.flush()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise ValueError("Failed to open video")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(src_fps / sample_fps))

        frames = []
        all_detections = []
        total_inference_ms = 0.0
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                if prompt_type == "visual" and refer_image is not None:
                    result = model_service.predict_with_vpe(frame, conf)
                elif prompt_type == "free":
                    result = model_service.predict_free(frame, conf)
                else:
                    result = model_service.predict_text(
                        image=frame,
                        labels=labels or [],
                        conf=conf,
                    )

                annotated = draw_detections(
                    frame,
                    result["detections"],
                    show_labels=show_labels,
                    show_bbox=show_bbox,
                    show_masks=show_masks,
                    classification=result.get("classification"),
                )
                frames.append(frame_to_base64(annotated, quality=70))
                all_detections.append(result["detections"])
                total_inference_ms += result["stats"]["inference_ms"]

            frame_idx += 1

        cap.release()

    n = len(frames)
    return {
        "frames": frames,
        "detections": all_detections,
        "stats": {
            "total_objects": sum(len(d) for d in all_detections),
            "classes_count": _count_classes(all_detections),
            "inference_ms": round(total_inference_ms / n, 1) if n else 0,
            "total_frames": frame_idx,
            "processed_frames": n,
        },
    }


def _count_classes(all_detections: list[list[dict]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dets in all_detections:
        for det in dets:
            counts[det["label"]] = counts.get(det["label"], 0) + 1
    return counts
