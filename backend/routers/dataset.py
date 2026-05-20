import json
import uuid

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.services.dataset import dataset_service
from backend.services.model import model_service
from backend.utils.encoding import decode_image

router = APIRouter(tags=["datasets"])


@router.get("/datasets")
async def list_datasets():
    return dataset_service.list_projects()


@router.post("/datasets")
async def create_dataset(
    name: str = Form(...),
    classes: str = Form("[]"),
):
    try:
        class_list = json.loads(classes)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid classes JSON")
    try:
        meta = dataset_service.create_project(name, class_list)
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    return meta


@router.delete("/datasets/{name}")
async def delete_dataset(name: str):
    try:
        dataset_service.delete_project(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"deleted": name}


@router.get("/datasets/{name}/images")
async def list_images(name: str, page: int = 1, limit: int = 20):
    try:
        return dataset_service.list_images(name, page, limit)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/datasets/{name}/images/{img_id}")
async def get_image(name: str, img_id: str):
    result = dataset_service.get_image(name, img_id)
    if result is None:
        raise HTTPException(404, "Image not found")
    return {
        "img_id": result["img_id"],
        "filename": result["filename"],
        "annotations": result["annotations"],
    }


@router.get("/datasets/{name}/images/{img_id}/file")
async def get_image_file(name: str, img_id: str):
    result = dataset_service.get_image(name, img_id)
    if result is None:
        raise HTTPException(404, "Image not found")
    return FileResponse(result["image_path"])


@router.post("/datasets/{name}/save")
async def save_to_dataset(
    name: str,
    file: UploadFile = File(...),
    detections: str = Form("[]"),
    source: str = Form("inference"),
):
    try:
        det_list = json.loads(detections)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid detections JSON")

    image_bytes = await file.read()
    try:
        result = dataset_service.save_image(name, image_bytes, det_list, source)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


@router.post("/datasets/{name}/upload")
async def upload_raw_images(
    name: str,
    files: list[UploadFile] = File(...),
):
    """Upload images without inference. Stored as unlabeled for later batch labeling."""
    results = []
    for f in files:
        image_bytes = await f.read()
        try:
            result = dataset_service.upload_raw(name, image_bytes, "upload")
            results.append(result)
        except (FileNotFoundError, ValueError):
            continue
    return {"uploaded": len(results), "results": results}


@router.post("/datasets/{name}/upload-stream")
async def upload_stream(
    name: str,
    file: UploadFile = File(None),
    rtsp_url: str = Form(None),
    sample_fps: float = Form(1.0),
):
    """Upload frames from video or RTSP as raw images (no inference)."""
    import tempfile
    import cv2

    results = []

    if file is not None:
        video_bytes = await file.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(video_bytes)
        tmp.close()

        cap = cv2.VideoCapture(tmp.name)
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(src_fps / sample_fps)) if sample_fps > 0 else 1
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                _, buf = cv2.imencode(".jpg", frame)
                try:
                    result = dataset_service.upload_raw(name, buf.tobytes(), "video")
                    results.append(result)
                except (FileNotFoundError, ValueError):
                    pass
            frame_idx += 1

        cap.release()
        import os
        os.unlink(tmp.name)

    elif rtsp_url:
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            raise HTTPException(400, f"Cannot open RTSP stream: {rtsp_url}")

        frame_interval = max(1, int(30 / sample_fps)) if sample_fps > 0 else 30
        frame_idx = 0
        max_frames = 300

        while frame_idx < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                _, buf = cv2.imencode(".jpg", frame)
                try:
                    result = dataset_service.upload_raw(name, buf.tobytes(), "rtsp")
                    results.append(result)
                except (FileNotFoundError, ValueError):
                    pass
            frame_idx += 1

        cap.release()
    else:
        raise HTTPException(400, "Provide either file (video) or rtsp_url")

    return {"uploaded": len(results), "results": results}


@router.post("/datasets/{name}/label")
async def label_images(
    name: str,
    prompt_type: str = Form("free"),
    labels: str = Form("[]"),
    confidence: float = Form(0.5),
):
    """Run inference on all unlabeled images in dataset. Requires loaded model."""
    if model_service.model is None:
        raise HTTPException(400, "No model loaded. Load a model first.")

    try:
        label_list = json.loads(labels)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid labels JSON")

    # Setup text prompt once if needed
    if prompt_type == "text" and label_list:
        model_service.predict_text.__wrapped__(model_service, np.zeros((1, 1, 3), np.uint8), label_list, 0.01) if hasattr(model_service.predict_text, '__wrapped__') else None

    unlabeled = dataset_service.get_unlabeled_images(name)
    results = []

    for img_id in unlabeled:
        image_data = dataset_service.get_image(name, img_id)
        if image_data is None or image_data["image_path"] is None:
            continue

        image = cv2.imread(image_data["image_path"])
        if image is None:
            continue

        if prompt_type == "free":
            det_result = model_service.predict_free(image, confidence)
        elif prompt_type == "text":
            det_result = model_service.predict_text(image, label_list, confidence)
        elif prompt_type == "visual":
            det_result = model_service.predict_with_vpe(image, confidence)
        else:
            continue

        labeled = dataset_service.label_image(name, img_id, det_result["detections"])
        if labeled:
            results.append(labeled)

    return {"labeled": len(results), "total_unlabeled": len(unlabeled), "results": results}
async def batch_upload(
    name: str,
    files: list[UploadFile] = File(...),
    prompt_type: str = Form("free"),
    labels: str = Form("[]"),
    confidence: float = Form(0.5),
):
    if model_service.model is None:
        raise HTTPException(400, "No model loaded. Load a model first.")

    try:
        label_list = json.loads(labels)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid labels JSON")

    results = []
    for f in files:
        image_bytes = await f.read()
        image = decode_image(image_bytes)
        if image is None:
            continue

        if prompt_type == "free":
            det_result = model_service.predict_free(image, confidence)
        elif prompt_type == "text":
            det_result = model_service.predict_text(image, label_list, confidence)
        elif prompt_type == "visual":
            det_result = model_service.predict_with_vpe(image, confidence)
        else:
            raise HTTPException(400, f"Unknown prompt_type: {prompt_type}")

        try:
            save_result = dataset_service.save_image(
                name, image_bytes, det_result["detections"], "batch"
            )
            results.append(save_result)
        except (FileNotFoundError, ValueError):
            continue

    return {"processed": len(results), "results": results}


@router.patch("/datasets/{name}/images/{img_id}/review")
async def review_image(name: str, img_id: str, reviews: list[dict] = Body(...)):
    result = dataset_service.review_image(name, img_id, reviews)
    if result is None:
        raise HTTPException(404, "Image not found")
    return result


@router.delete("/datasets/{name}/images/{img_id}")
async def delete_image(name: str, img_id: str):
    deleted = dataset_service.delete_image(name, img_id)
    if not deleted:
        raise HTTPException(404, "Image not found")
    return {"deleted": img_id}


@router.post("/datasets/{name}/export")
async def export_dataset(name: str, format: str = Form("yolo"), split: float = Form(0.8)):
    try:
        if format == "yolo":
            zip_bytes = dataset_service.export_yolo(name, split)
            filename = f"{name}_yolo.zip"
        elif format == "coco":
            zip_bytes = dataset_service.export_coco(name, split)
            filename = f"{name}_coco.zip"
        else:
            raise HTTPException(400, f"Unknown format: {format}. Use 'yolo' or 'coco'.")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/datasets/{name}/save-stream")
async def save_stream(
    name: str,
    file: UploadFile = File(None),
    rtsp_url: str = Form(None),
    prompt_type: str = Form("free"),
    labels: str = Form("[]"),
    confidence: float = Form(0.5),
    sample_fps: float = Form(1.0),
):
    """Save frames from video or RTSP stream to dataset at configured sample rate."""
    if model_service.model is None:
        raise HTTPException(400, "No model loaded.")

    import cv2
    import tempfile

    try:
        label_list = json.loads(labels)
    except json.JSONDecodeError:
        label_list = []

    results = []

    if file is not None:
        # Video file processing
        video_bytes = await file.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(video_bytes)
        tmp.close()

        cap = cv2.VideoCapture(tmp.name)
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(src_fps / sample_fps)) if sample_fps > 0 else 1
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                det_result = _run_inference(frame, prompt_type, label_list, confidence)
                _, buf = cv2.imencode(".jpg", frame)
                img_bytes = buf.tobytes()
                try:
                    save_result = dataset_service.save_image(
                        name, img_bytes, det_result["detections"], "video"
                    )
                    results.append(save_result)
                except (FileNotFoundError, ValueError):
                    pass
            frame_idx += 1

        cap.release()
        import os
        os.unlink(tmp.name)

    elif rtsp_url:
        # RTSP stream processing — limited frame capture
        import asyncio

        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            raise HTTPException(400, f"Cannot open RTSP stream: {rtsp_url}")

        frame_interval = max(1, int(30 / sample_fps)) if sample_fps > 0 else 30
        frame_idx = 0
        max_frames = 300  # Safety limit for RTSP

        while frame_idx < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                det_result = _run_inference(frame, prompt_type, label_list, confidence)
                _, buf = cv2.imencode(".jpg", frame)
                img_bytes = buf.tobytes()
                try:
                    save_result = dataset_service.save_image(
                        name, img_bytes, det_result["detections"], "rtsp"
                    )
                    results.append(save_result)
                except (FileNotFoundError, ValueError):
                    pass
            frame_idx += 1

        cap.release()
    else:
        raise HTTPException(400, "Provide either file (video) or rtsp_url")

    return {"processed": len(results), "results": results}


def _run_inference(frame, prompt_type: str, labels: list[str], confidence: float) -> dict:
    if prompt_type == "free":
        return model_service.predict_free(frame, confidence)
    elif prompt_type == "text":
        return model_service.predict_text(frame, labels, confidence)
    elif prompt_type == "visual":
        return model_service.predict_with_vpe(frame, confidence)
    return {"detections": []}
