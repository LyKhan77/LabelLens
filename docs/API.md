# LabelLens API Reference

Backend base URL defaults to `http://localhost:3131`. REST endpoints are mounted under `/api`. RTSP streaming is mounted at `/ws/stream`, while training job events are mounted at `/api/ws/training/{job_id}`.

This is an operator-facing endpoint catalog, not a strict OpenAPI schema.

## Health and Model

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Backend health and model-loaded status |
| GET | `/api/model/status` | Current YOLOE/custom model status |
| POST | `/api/model/load` | Load Free or Prompt YOLOE model with body `{ "mode": "free" }` or `{ "mode": "prompt" }` |
| POST | `/api/model/load-custom` | Load registered Train Tune model by `{ "model_id": "..." }` |

## Detection

| Method | Path | Input | Purpose |
|--------|------|-------|---------|
| POST | `/api/detect/image` | multipart form image, prompt fields, confidence, overlay flags | Run image inference and return annotated image, detections, stats |
| POST | `/api/detect/video` | multipart form video, prompt fields, confidence, overlay flags, `sample_fps` | Run sampled video inference and return processed result |

Prompt fields:

| Field | Mode | Notes |
|-------|------|-------|
| `prompt_type` | all | `free`, `text`, or `visual` |
| `labels` | text | Comma-separated for detection API, JSON list for dataset API |
| `refer_image` | visual | Reference image file |
| `bboxes` | visual | JSON list of prompt boxes |
| `vcls` | visual | JSON list of prompt labels/classes |
| `confidence` | all | Float confidence threshold |
| `show_labels` | all | Render labels in backend overlay |
| `show_bbox` | all | Render boxes in backend overlay |
| `show_masks` | all | Render clipped masks in backend overlay |

## RTSP WebSocket

| Method | Path | Purpose |
|--------|------|---------|
| WS | `/ws/stream` | Live RTSP inference stream |

The first client message is JSON config:

```json
{
  "rtsp_url": "rtsp://camera/stream",
  "prompt_type": "text",
  "labels": ["person", "car"],
  "confidence": 0.5,
  "show_labels": true,
  "show_bbox": true,
  "show_masks": false,
  "bboxes": [],
  "vcls": [],
  "refer_image_b64": null
}
```

Backend sends JSON frame payloads or `{ "error": "..." }`.

## Datasets

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/datasets` | List dataset projects |
| POST | `/api/datasets` | Create dataset project from form `name`, `task_type`, optional `task_config` JSON object |
| DELETE | `/api/datasets/{name}` | Delete dataset project |
| PATCH | `/api/datasets/{name}/class-colors` | Persist class color override |
| GET | `/api/datasets/{name}/images` | Paginated image list; query `page`, `limit` |
| GET | `/api/datasets/{name}/images/{img_id}` | Image metadata and annotations |
| GET | `/api/datasets/{name}/images/{img_id}/file` | Raw image file |
| POST | `/api/datasets/{name}/save` | Save one inference image and detections |
| POST | `/api/datasets/{name}/upload` | Upload raw images without inference |
| POST | `/api/datasets/{name}/upload-stream` | Sample frames from uploaded video or RTSP stream |
| POST | `/api/datasets/{name}/label` | Synchronous label pass over unlabeled images |
| POST | `/api/datasets/{name}/label-jobs` | Background rapid inference labeling job |
| GET | `/api/datasets/{name}/label-jobs/{job_id}` | Poll rapid inference job state |
| POST | `/api/datasets/{name}/batch` | Batch upload and infer images |
| POST | `/api/datasets/{name}/save-stream` | Sample video/RTSP frames, infer, and save detections |
| POST | `/api/datasets/{name}/export` | Export accepted labels as `yolo` or `coco` zip, or `raw` for original images only (no labels/split/yaml). `yolo` dispatches to native task export for detection, classification, and pose. |

## Dataset Review and Annotation

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/datasets/{name}/images/{source_img_id}/infer-next` | Run visual-prompt candidates from source image to target image |
| POST | `/api/datasets/{name}/images/{img_id}/sam-mask` | Generate SAM2.1 mask from bbox prompt |
| POST | `/api/datasets/{name}/images/{img_id}/detections` | Add manual detection |
| POST | `/api/datasets/{name}/images/{img_id}/labels` | Set image-level labels for single-label or multi-label classification datasets |
| POST | `/api/datasets/{name}/images/{img_id}/poses` | Add bbox-first pose instance with fixed-template keypoints |
| PATCH | `/api/datasets/{name}/images/{img_id}/detections/{det_id}` | Update detection fields |
| DELETE | `/api/datasets/{name}/images/{img_id}/detections/{det_id}` | Delete detection |
| PATCH | `/api/datasets/{name}/images/{img_id}/review` | Save accept/reject review state |
| DELETE | `/api/datasets/{name}/images/{img_id}` | Delete image and annotations |

## System / GPU

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/system/gpus` | List auto-detected CUDA GPUs with VRAM info, UUID, and current inference config |
| PUT | `/api/system/gpu-config` | Update YOLOE/SAM device assignment with hot-swap reload; body `{ "yoloe_device": int, "sam_device": int }` |
| GET | `/api/system/gpus/training` | List auto-detected CUDA GPUs with current training GPU config |
| PUT | `/api/training/gpu-config` | Update training GPU mode and device selection; body `{ "training_mode": "standard"|"high_speed", "training_device": str, "visible_devices": str, "amp": bool }` |

## SAM2.1

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/sam/status` | Return enabled/loading/loaded/device/model status |
| POST | `/api/sam/load` | Lazy-load SAM2.1 model |
| POST | `/api/sam/unload` | Release SAM2.1 model |

## Train Tune

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/training/dataset-versions` | List immutable Dataset Versions |
| GET | `/api/training/dataset-versions/{version_id}` | Fetch Dataset Version detail |
| DELETE | `/api/training/dataset-versions/{version_id}` | Delete unused Dataset Version |
| POST | `/api/training/dataset-versions/preview` | Preview preprocessing/augmentation policy samples |
| POST | `/api/training/dataset-versions/live` | Create Dataset Version from live dataset |
| POST | `/api/training/dataset-versions/import` | Create Dataset Version from exported ZIP |
| POST | `/api/training/estimate` | Estimate training time/resources |
| POST | `/api/training/recommend` | Recommend epochs, patience, batch, image size |
| GET | `/api/training/jobs` | List training jobs |
| GET | `/api/training/jobs/{job_id}` | Get training job detail |
| POST | `/api/training/jobs` | Create training job |
| POST | `/api/training/jobs/{job_id}/cancel` | Cancel running/queued job |
| POST | `/api/training/jobs/{job_id}/recompute` | Recompute failed job |
| POST | `/api/training/jobs/{job_id}/resume` | Resume from `last.pt` checkpoint |
| DELETE | `/api/training/jobs/{job_id}` | Delete failed/cancelled job when allowed |
| GET | `/api/training/jobs/{job_id}/metrics` | Read metric history |
| GET | `/api/training/models` | List registered Model Versions |
| GET | `/api/training/models/{model_id}` | Fetch Model Version detail |
| DELETE | `/api/training/models/{model_id}` | Delete Model Version and linked artifacts |
| WS | `/api/ws/training/{job_id}` | Subscribe to job events and historical event replay |

## Common Error Codes

| Code | Meaning |
|------|---------|
| 400 | Invalid input, missing prompt fields, missing masks, incompatible task/config |
| 404 | Dataset, image, job, Dataset Version, or Model Version not found |
| 409 | Conflicting activity or protected delete |
| 422 | Model load failed because request/path is invalid |
| 500 | Unhandled model/SAM/runtime error |
| 503 | SAM unavailable or currently loading |
