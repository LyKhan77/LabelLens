import json

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from backend.services.model import model_service
from backend.services.video import process_video
from backend.utils.drawing import draw_detections
from backend.utils.encoding import decode_image, frame_to_base64

router = APIRouter()


@router.post("/detect/image")
async def detect_image(
    file: UploadFile = File(...),
    prompt_type: str = Form("text"),
    labels: str = Form(""),
    refer_image: UploadFile | None = File(None),
    bboxes: str = Form("[]"),
    vcls: str = Form("[]"),
    confidence: float = Form(0.5),
    show_labels: bool = Form(True),
    show_bbox: bool = Form(True),
):
    target_bytes = await file.read()
    target_img = decode_image(target_bytes)

    if prompt_type == "visual":
        if refer_image is None:
            return JSONResponse(
                status_code=400,
                content={"error": "refer_image required for visual prompt"},
            )
        refer_bytes = await refer_image.read()
        refer_img = decode_image(refer_bytes)
        bbox_list = json.loads(bboxes)
        cls_list = json.loads(vcls)

        result = model_service.predict_visual(
            image=target_img,
            refer_image=refer_img,
            bboxes=bbox_list,
            cls=cls_list,
            conf=confidence,
        )
    else:
        label_list = [l.strip() for l in labels.split(",") if l.strip()]
        if not label_list:
            return JSONResponse(
                status_code=400,
                content={"error": "At least one label required for text prompt"},
            )
        result = model_service.predict_text(
            image=target_img,
            labels=label_list,
            conf=confidence,
        )

    annotated = draw_detections(
        target_img,
        result["detections"],
        show_labels=show_labels,
        show_bbox=show_bbox,
    )

    return {
        "image": frame_to_base64(annotated),
        "detections": result["detections"],
        "stats": result["stats"],
    }


@router.post("/detect/video")
async def detect_video(
    file: UploadFile = File(...),
    prompt_type: str = Form("text"),
    labels: str = Form(""),
    refer_image: UploadFile | None = File(None),
    bboxes: str = Form("[]"),
    vcls: str = Form("[]"),
    confidence: float = Form(0.5),
    show_labels: bool = Form(True),
    show_bbox: bool = Form(True),
    sample_fps: int = Form(5),
):
    file_bytes = await file.read()

    refer_img = None
    bbox_list = json.loads(bboxes)
    cls_list = json.loads(vcls)

    if prompt_type == "visual":
        if refer_image is None:
            return JSONResponse(
                status_code=400,
                content={"error": "refer_image required for visual prompt"},
            )
        refer_bytes = await refer_image.read()
        refer_img = decode_image(refer_bytes)

    label_list = [l.strip() for l in labels.split(",") if l.strip()] if prompt_type == "text" else None

    result = process_video(
        file_bytes=file_bytes,
        prompt_type=prompt_type,
        labels=label_list,
        refer_image=refer_img,
        bboxes=bbox_list,
        cls=cls_list,
        conf=confidence,
        show_labels=show_labels,
        show_bbox=show_bbox,
        sample_fps=sample_fps,
    )

    return result
