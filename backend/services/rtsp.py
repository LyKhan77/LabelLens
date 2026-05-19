import asyncio
import logging
from typing import AsyncGenerator

import cv2
import numpy as np

from backend.services.model import model_service
from backend.utils.drawing import draw_detections
from backend.utils.encoding import frame_to_base64

logger = logging.getLogger(__name__)

# Skip frames between inference — stream reads every frame but only
# runs inference every N frames. Intermediate frames get the last
# known detections drawn on them for smooth display.
INFERENCE_INTERVAL = 5


class RTSPStream:
    def __init__(self):
        self._running = False
        self._cap: cv2.VideoCapture | None = None

    async def start(
        self,
        rtsp_url: str,
        prompt_type: str,
        labels: list[str] | None = None,
        refer_image: np.ndarray | None = None,
        bboxes: list[list[float]] | None = None,
        cls: list[str] | None = None,
        conf: float = 0.5,
        show_labels: bool = True,
        show_bbox: bool = True,
    ) -> AsyncGenerator[dict, None]:
        self._running = True
        loop = asyncio.get_event_loop()

        try:
            # Setup visual prompt once before streaming
            if prompt_type == "visual" and refer_image is not None:
                await loop.run_in_executor(
                    None,
                    lambda: model_service.setup_visual_prompt(
                        refer_image=refer_image,
                        bboxes=bboxes or [],
                        cls=cls or [],
                    ),
                )

            self._cap = await loop.run_in_executor(None, lambda: cv2.VideoCapture(rtsp_url))
            if not self._cap.isOpened():
                raise ValueError(f"Cannot open RTSP stream: {rtsp_url}")

            last_detections: list[dict] = []
            last_inference_ms = 0.0
            frame_idx = 0

            while self._running:
                ret, frame = await loop.run_in_executor(None, self._cap.read)
                if not ret or frame is None:
                    logger.warning("RTSP frame read failed, stopping")
                    break

                # Run inference only every N frames
                if frame_idx % INFERENCE_INTERVAL == 0:
                    if prompt_type == "visual" and refer_image is not None:
                        result = model_service.predict_with_vpe(frame, conf)
                    else:
                        result = model_service.predict_text(
                            image=frame,
                            labels=labels or [],
                            conf=conf,
                        )
                    last_detections = result["detections"]
                    last_inference_ms = result["stats"]["inference_ms"]

                annotated = draw_detections(
                    frame,
                    last_detections,
                    show_labels=show_labels,
                    show_bbox=show_bbox,
                )

                yield {
                    "frame": frame_to_base64(annotated, quality=60),
                    "detections": last_detections,
                    "inference_ms": last_inference_ms,
                }

                frame_idx += 1

        except Exception as e:
            logger.error(f"RTSP stream error: {e}")
            raise
        finally:
            self.stop()

    def stop(self):
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
