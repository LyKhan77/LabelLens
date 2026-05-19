import asyncio
import base64
import json
import logging

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.rtsp import RTSPStream
from backend.utils.encoding import decode_image

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/stream")
async def stream_endpoint(ws: WebSocket):
    await ws.accept()

    rtsp = RTSPStream()

    try:
        # Receive config
        logger.info("WebSocket stream accepted, waiting for config")
        config_raw = await asyncio.wait_for(ws.receive_text(), timeout=5.0)
        config = json.loads(config_raw)

        rtsp_url = config["rtsp_url"]
        prompt_type = config.get("prompt_type", "text")
        labels = config.get("labels", [])
        confidence = config.get("confidence", 0.5)
        show_labels = config.get("show_labels", True)
        show_bbox = config.get("show_bbox", True)
        show_masks = config.get("show_masks", False)
        bboxes = config.get("bboxes", [])
        vcls = config.get("vcls", [])

        logger.info(
            "RTSP stream config received: prompt_type=%s labels=%d visual_boxes=%d",
            prompt_type,
            len(labels),
            len(bboxes),
        )

        refer_image = None
        refer_b64 = config.get("refer_image_b64")
        if refer_b64 and prompt_type == "visual":
            refer_bytes = base64.b64decode(refer_b64)
            refer_image = decode_image(refer_bytes)

        async for frame_data in rtsp.start(
            rtsp_url=rtsp_url,
            prompt_type=prompt_type,
            labels=labels if prompt_type == "text" else None,
            refer_image=refer_image if prompt_type == "visual" else None,
            bboxes=bboxes if prompt_type == "visual" else None,
            cls=vcls if prompt_type == "visual" else None,
            conf=confidence,
            show_labels=show_labels,
            show_bbox=show_bbox,
            show_masks=show_masks,
        ):
            await ws.send_json(frame_data)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except asyncio.TimeoutError:
        logger.warning("WebSocket stream config timed out")
        try:
            await ws.send_json({"error": "Stream configuration timed out. Please retry RTSP connection."})
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Stream error: {e}")
        try:
            await ws.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        rtsp.stop()
