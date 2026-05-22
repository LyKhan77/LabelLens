import json
import os
import tempfile
import threading
import time
import uuid

import cv2
from fastapi import APIRouter, BackgroundTasks, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.services.dataset import dataset_service
from backend.services.model import model_service
from backend.services.sam import sam_service
from backend.utils.encoding import decode_image

router = APIRouter(tags=["datasets"])

label_jobs: dict[str, dict] = {}
label_job_lock = threading.Lock()


def _new_job(name: str) -> dict:
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "dataset": name,
        "state": "queued",
        "processed": 0,
        "total": 0,
        "current_image_url": None,
        "current_filename": None,
        "detections_count": 0,
        "error": None,
        "results": [],
        "items": [],
        "created": time.time(),
    }
    label_jobs[job_id] = job
    return job


def _parse_json_list(raw: str, field: str) -> list:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, f"Invalid {field} JSON")
    if not isinstance(value, list):
        raise HTTPException(400, f"{field} must be a JSON list")
    return value


def _run_inference(frame, prompt_type: str, labels: list[str], confidence: float) -> dict:
    if prompt_type == "free":
        return model_service.predict_free(frame, confidence)
    if prompt_type == "text":
        return model_service.predict_text(frame, labels, confidence)
    if prompt_type == "visual":
        return model_service.predict_with_vpe(frame, confidence)
    raise ValueError(f"Unknown prompt_type: {prompt_type}")


def _prepare_visual_prompt(refer_image_bytes: bytes | None, bboxes: list, vcls: list):
    if refer_image_bytes is None:
        raise ValueError("refer_image required for visual prompt")
    refer_image = decode_image(refer_image_bytes)
    if refer_image is None:
        raise ValueError("Invalid refer_image")
    model_service.setup_visual_prompt(refer_image, bboxes, vcls)


def _run_label_job(
    job_id: str,
    name: str,
    prompt_type: str,
    labels: list[str],
    confidence: float,
    refer_image_bytes: bytes | None,
    bboxes: list,
    vcls: list,
):
    job = label_jobs[job_id]
    if not label_job_lock.acquire(blocking=False):
        job["state"] = "failed"
        job["error"] = "Another labeling job is already running"
        return

    try:
        if model_service.model is None:
            raise ValueError("No model loaded. Load a model first.")
        if prompt_type == "text" and not labels:
            raise ValueError("At least one label required for text prompt")
        if prompt_type == "visual":
            _prepare_visual_prompt(refer_image_bytes, bboxes, vcls)

        unlabeled = dataset_service.get_unlabeled_images(name)
        job["state"] = "running"
        job["total"] = len(unlabeled)

        for img_id in unlabeled:
            image_data = dataset_service.get_image(name, img_id)
            image_url = f"/api/datasets/{name}/images/{img_id}/file"
            annotations = image_data.get("annotations") if image_data else None
            item = {
                "img_id": img_id,
                "filename": image_data["filename"] if image_data else img_id,
                "image_url": image_url,
                "width": annotations.get("width") if annotations else None,
                "height": annotations.get("height") if annotations else None,
                "state": "running",
                "detections_count": 0,
                "detections": [],
                "error": None,
            }
            job["items"].append(item)
            job["current_filename"] = item["filename"]
            job["current_image_url"] = image_url

            if image_data is None or image_data["image_path"] is None:
                item["state"] = "failed"
                item["error"] = "Image not found"
                job["processed"] += 1
                continue

            image = cv2.imread(image_data["image_path"])
            if image is None:
                item["state"] = "failed"
                item["error"] = "Image could not be read"
                job["processed"] += 1
                continue

            try:
                det_result = _run_inference(image, prompt_type, labels, confidence)
                detections = det_result.get("detections", [])
                labeled = dataset_service.label_image(name, img_id, detections)
                if labeled:
                    item["detections_count"] = labeled["detections_count"]
                    item["detections"] = detections
                    item["state"] = "done"
                    job["detections_count"] += labeled["detections_count"]
                    job["results"].append(labeled)
                else:
                    item["state"] = "failed"
                    item["error"] = "Image annotation not found"
            except Exception as exc:
                item["state"] = "failed"
                item["error"] = str(exc)
            job["processed"] += 1

        job["state"] = "done"
    except Exception as exc:
        job["state"] = "failed"
        job["error"] = str(exc)
    finally:
        label_job_lock.release()


@router.get("/datasets")
async def list_datasets():
    return dataset_service.list_projects()


@router.post("/datasets")
async def create_dataset(
    name: str = Form(...),
    classes: str = Form("[]"),
):
    class_list = _parse_json_list(classes, "classes")
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


def _read_dataset_image(name: str, img_id: str, role: str):
    image_data = dataset_service.get_image(name, img_id)
    if image_data is None or image_data.get("image_path") is None:
        raise HTTPException(404, f"{role} image not found")
    image = cv2.imread(image_data["image_path"])
    if image is None:
        raise HTTPException(400, f"{role} image could not be read")
    return image


def _parse_visual_prompt_payload(payload: dict) -> tuple[str, list, list[str], float]:
    target_img_id = payload.get("target_img_id")
    if not isinstance(target_img_id, str) or not target_img_id.strip():
        raise HTTPException(400, "target_img_id is required")

    prompts = payload.get("prompts")
    if not isinstance(prompts, list) or len(prompts) == 0:
        raise HTTPException(400, "At least one prompt is required")

    bboxes = []
    labels = []
    for prompt in prompts:
        if not isinstance(prompt, dict):
            raise HTTPException(400, "prompts must contain objects")
        box = prompt.get("box")
        label = prompt.get("label")
        if not isinstance(box, list) or len(box) != 4:
            raise HTTPException(400, "prompt box must be a list of four numbers")
        if not isinstance(label, str) or not label.strip():
            raise HTTPException(400, "prompt label is required")
        bboxes.append(box)
        labels.append(label.strip())

    try:
        confidence = float(payload.get("confidence", 0.5))
    except (TypeError, ValueError):
        raise HTTPException(400, "confidence must be a number")
    confidence = max(0.01, min(confidence, 0.99))
    return target_img_id.strip(), bboxes, labels, confidence


@router.post("/datasets/{name}/images/{source_img_id}/infer-next")
async def infer_next_visual_prompt(name: str, source_img_id: str, payload: dict = Body(...)):
    if model_service.model is None:
        raise HTTPException(400, "No model loaded. Load the prompt model first.")

    target_img_id, bboxes, labels, confidence = _parse_visual_prompt_payload(payload)
    source_image = _read_dataset_image(name, source_img_id, "Source")
    target_image = _read_dataset_image(name, target_img_id, "Target")

    try:
        model_service.setup_visual_prompt(source_image, bboxes, labels)
        det_result = model_service.predict_with_vpe(target_image, confidence)
    except Exception as exc:
        raise HTTPException(400, str(exc))

    candidates = []
    for idx, det in enumerate(det_result.get("detections", [])):
        candidate = {
            "id": idx,
            "box": det.get("box", []),
            "label": det.get("label", ""),
            "confidence": det.get("confidence", 0),
            "cls_id": det.get("cls_id", -1),
            "accepted": False,
            "assisted": True,
            "source": "visual_prompt",
        }
        if "mask" in det:
            candidate["mask"] = det["mask"]
        if "mask_rle" in det:
            candidate["mask_rle"] = det["mask_rle"]
        candidates.append(candidate)

    return {
        "source_img_id": source_img_id,
        "target_img_id": target_img_id,
        "candidates": candidates,
    }


@router.post("/datasets/{name}/save")
async def save_to_dataset(
    name: str,
    file: UploadFile = File(...),
    detections: str = Form("[]"),
    source: str = Form("inference"),
):
    det_list = _parse_json_list(detections, "detections")
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
    file: UploadFile | None = File(None),
    rtsp_url: str | None = Form(None),
    sample_fps: float = Form(1.0),
):
    results = []

    if file is not None:
        video_bytes = await file.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        try:
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
        finally:
            try:
                tmp.close()
                os.unlink(tmp.name)
            except OSError:
                pass

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
    refer_image: UploadFile | None = File(None),
    bboxes: str = Form("[]"),
    vcls: str = Form("[]"),
):
    if model_service.model is None:
        raise HTTPException(400, "No model loaded. Load a model first.")

    label_list = _parse_json_list(labels, "labels")
    bbox_list = _parse_json_list(bboxes, "bboxes")
    vcls_list = _parse_json_list(vcls, "vcls")

    if prompt_type == "visual":
        refer_bytes = await refer_image.read() if refer_image else None
        try:
            _prepare_visual_prompt(refer_bytes, bbox_list, vcls_list)
        except ValueError as e:
            raise HTTPException(400, str(e))

    unlabeled = dataset_service.get_unlabeled_images(name)
    results = []

    for img_id in unlabeled:
        image_data = dataset_service.get_image(name, img_id)
        if image_data is None or image_data["image_path"] is None:
            continue
        image = cv2.imread(image_data["image_path"])
        if image is None:
            continue
        det_result = _run_inference(image, prompt_type, label_list, confidence)
        labeled = dataset_service.label_image(name, img_id, det_result["detections"])
        if labeled:
            results.append(labeled)

    return {"labeled": len(results), "total_unlabeled": len(unlabeled), "results": results}


@router.post("/datasets/{name}/label-jobs")
async def create_label_job(
    name: str,
    background_tasks: BackgroundTasks,
    prompt_type: str = Form("free"),
    labels: str = Form("[]"),
    confidence: float = Form(0.5),
    refer_image: UploadFile | None = File(None),
    bboxes: str = Form("[]"),
    vcls: str = Form("[]"),
):
    if model_service.model is None:
        raise HTTPException(400, "No model loaded. Load a model first.")

    try:
        dataset_service._read_meta(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    label_list = _parse_json_list(labels, "labels")
    bbox_list = _parse_json_list(bboxes, "bboxes")
    vcls_list = _parse_json_list(vcls, "vcls")
    refer_bytes = await refer_image.read() if refer_image else None

    job = _new_job(name)
    background_tasks.add_task(
        _run_label_job,
        job["job_id"],
        name,
        prompt_type,
        label_list,
        confidence,
        refer_bytes,
        bbox_list,
        vcls_list,
    )
    return job


@router.get("/datasets/{name}/label-jobs/{job_id}")
async def get_label_job(name: str, job_id: str):
    job = label_jobs.get(job_id)
    if job is None or job.get("dataset") != name:
        raise HTTPException(404, "Label job not found")
    return job


@router.post("/datasets/{name}/batch")
async def batch_upload(
    name: str,
    files: list[UploadFile] = File(...),
    prompt_type: str = Form("free"),
    labels: str = Form("[]"),
    confidence: float = Form(0.5),
    refer_image: UploadFile | None = File(None),
    bboxes: str = Form("[]"),
    vcls: str = Form("[]"),
):
    if model_service.model is None:
        raise HTTPException(400, "No model loaded. Load a model first.")

    label_list = _parse_json_list(labels, "labels")
    bbox_list = _parse_json_list(bboxes, "bboxes")
    vcls_list = _parse_json_list(vcls, "vcls")

    if prompt_type == "visual":
        refer_bytes = await refer_image.read() if refer_image else None
        try:
            _prepare_visual_prompt(refer_bytes, bbox_list, vcls_list)
        except ValueError as e:
            raise HTTPException(400, str(e))

    results = []
    for f in files:
        image_bytes = await f.read()
        image = decode_image(image_bytes)
        if image is None:
            continue
        det_result = _run_inference(image, prompt_type, label_list, confidence)
        try:
            save_result = dataset_service.save_image(
                name, image_bytes, det_result["detections"], "batch"
            )
            results.append(save_result)
        except (FileNotFoundError, ValueError):
            continue

    return {"processed": len(results), "results": results}



@router.post("/datasets/{name}/images/{img_id}/sam-mask")
async def generate_sam_mask(name: str, img_id: str, payload: dict = Body(...)):
    if not sam_service.get_status()["enabled"]:
        raise HTTPException(400, "SAM is disabled")
    box = payload.get("box")
    if not isinstance(box, list) or len(box) != 4:
        raise HTTPException(400, "box must be [x1, y1, x2, y2]")

    image = _read_dataset_image(name, img_id, "Source")
    try:
        sam_service._ensure_loaded()
        result = sam_service.predict_mask_from_bbox(image, box)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"SAM prediction failed: {e}")

    return result


@router.post("/datasets/{name}/images/{img_id}/detections")
async def add_detection(name: str, img_id: str, payload: dict = Body(...)):
    try:
        result = dataset_service.add_detection(name, img_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if result is None:
        raise HTTPException(404, "Image not found")
    return result


@router.patch("/datasets/{name}/images/{img_id}/detections/{det_id}")
async def update_detection(name: str, img_id: str, det_id: int, payload: dict = Body(...)):
    try:
        result = dataset_service.update_detection(name, img_id, det_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if result is None:
        raise HTTPException(404, "Detection not found")
    return result


@router.delete("/datasets/{name}/images/{img_id}/detections/{det_id}")
async def delete_detection(name: str, img_id: str, det_id: int):
    result = dataset_service.delete_detection(name, img_id, det_id)
    if result is None:
        raise HTTPException(404, "Detection not found")
    return result


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
    file: UploadFile | None = File(None),
    rtsp_url: str | None = Form(None),
    prompt_type: str = Form("free"),
    labels: str = Form("[]"),
    confidence: float = Form(0.5),
    sample_fps: float = Form(1.0),
    refer_image: UploadFile | None = File(None),
    bboxes: str = Form("[]"),
    vcls: str = Form("[]"),
):
    if model_service.model is None:
        raise HTTPException(400, "No model loaded.")

    label_list = _parse_json_list(labels, "labels")
    bbox_list = _parse_json_list(bboxes, "bboxes")
    vcls_list = _parse_json_list(vcls, "vcls")

    if prompt_type == "visual":
        refer_bytes = await refer_image.read() if refer_image else None
        try:
            _prepare_visual_prompt(refer_bytes, bbox_list, vcls_list)
        except ValueError as e:
            raise HTTPException(400, str(e))

    results = []

    if file is not None:
        video_bytes = await file.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        try:
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
                    try:
                        save_result = dataset_service.save_image(
                            name, buf.tobytes(), det_result["detections"], "video"
                        )
                        results.append(save_result)
                    except (FileNotFoundError, ValueError):
                        pass
                frame_idx += 1
            cap.release()
        finally:
            try:
                tmp.close()
                os.unlink(tmp.name)
            except OSError:
                pass

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
                det_result = _run_inference(frame, prompt_type, label_list, confidence)
                _, buf = cv2.imencode(".jpg", frame)
                try:
                    save_result = dataset_service.save_image(
                        name, buf.tobytes(), det_result["detections"], "rtsp"
                    )
                    results.append(save_result)
                except (FileNotFoundError, ValueError):
                    pass
            frame_idx += 1
        cap.release()
    else:
        raise HTTPException(400, "Provide either file (video) or rtsp_url")

    return {"processed": len(results), "results": results}
