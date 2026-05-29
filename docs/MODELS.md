# Model and GPU Guide

LabelLens uses YOLOE for detection/segmentation inference and Train Tune checkpoint reuse, plus SAM2.1 for optional auto-mask generation from manual bbox prompts.

## Required Model Files

| Path | Purpose | Used by |
|------|---------|---------|
| `models/yoloe-26l-seg.pt` | Prompt-mode YOLOE segmentation model | Text Prompt, Visual Prompt, image/video/RTSP prompt inference |
| `models/yoloe-26l-seg-pf.pt` | Prompt-free YOLOE LRPC model | Free Inference and prompt-free rapid inference |
| `models/sam2.1_l.pt` | SAM2.1 Hiera Large model | Dataset Manager auto-mask from manual bbox |

Additional local YOLO checkpoints can be placed in the repo root or `models/` for Train Tune base checkpoints, as long as the submitted `base_checkpoint` path resolves safely and exists.

## Model Loading

| Endpoint | Behavior |
|----------|----------|
| `POST /api/model/load` with `mode=prompt` | Loads `MODEL_PATH`, default `models/yoloe-26l-seg.pt` |
| `POST /api/model/load` with `mode=free` | Loads prompt-free model, default `models/yoloe-26l-seg-pf.pt` in model service |
| `POST /api/model/load-custom` | Loads a registered Train Tune Model Version artifact |
| `POST /api/sam/load` | Lazy-loads SAM2.1 from `models/<SAM_MODEL>` when present, otherwise from the configured model identifier |

Model loading is deferred. Users land on `/`, then choose a mode that loads the needed model before entering the workspace.

## Inference Modes

| Mode | Backend method | Prompt source |
|------|----------------|---------------|
| Free | `predict_free()` | YOLOE LRPC internal vocabulary |
| Text Prompt | `predict_text()` | Comma-separated or JSON list labels |
| Visual Prompt | `predict_visual()` / visual prompt setup + VPE prediction | Reference image plus bbox labels |
| Custom Model | `load_custom_model()` then normal test inference | Train Tune registered artifact classes |

## GPU Mapping

`backend/config.py` sets:

```text
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=${LABELLENS_CUDA_VISIBLE_DEVICES:-1,2}
```

Default policy:

| Workload | Default setting | Physical GPU intent |
|----------|-----------------|---------------------|
| YOLOE inference | `DEVICE=0` after visible mapping | Physical GPU `1` |
| SAM2.1 | `SAM_DEVICE=1` after visible mapping | Physical GPU `2` |
| Train Tune Standard | `TRAIN_VISIBLE_DEVICES_STANDARD=1`, `TRAIN_DEVICE_STANDARD=1` | Physical GPU `1` |
| Train Tune High-Speed | `TRAIN_VISIBLE_DEVICES_HIGH_SPEED=1,2`, `TRAIN_DEVICE_HIGH_SPEED=1,2` | Physical GPUs `1,2` |
| vLLM reserve | LabelLens avoids physical GPU `0` | Physical GPU `0` remains free |

Train Tune passes physical device IDs to Ultralytics because Ultralytics rewrites `CUDA_VISIBLE_DEVICES` from its `device` argument.

## Train Tune Checkpoints

Training jobs validate:

| Field | Rule |
|-------|------|
| `task_type` | Must be `detect` or `segment`, and match the Dataset Version task |
| `base_checkpoint` | Required, cannot traverse parent directories, absolute paths must exist |
| `epochs` | 1 to 500 |
| `patience` | 0 to 100 |
| `imgsz` | Multiple of 32 from 320 to 2048 |
| `batch` | `-1` for Auto Batch, or 1 to 128 |
| `training_mode` | `standard` or `high_speed` |

Failed/cancelled jobs with `last.pt` can be resumed. Completed jobs register their best artifact as Model Versions.

## SAM2.1 Behavior

SAM is optional at save time:

1. User draws a manual bbox in Dataset Manager review.
2. Frontend requests `/api/datasets/{name}/images/{img_id}/sam-mask`.
3. Backend lazy-loads SAM if needed.
4. Backend returns mask data for the bbox.
5. If SAM fails, bbox annotation can still be saved without a mask.

## Validation Checklist

- Confirm all required model files exist and are readable.
- Load Prompt model and run Text Prompt image inference.
- Load Free model and run Free image inference.
- Run Visual Prompt inference with reference image and bbox.
- Load SAM and generate a mask from a manual bbox.
- Run Train Tune detection job with a detection checkpoint.
- Run Train Tune segmentation job with a segmentation checkpoint and complete masks.
- Load a registered Model Version and test it through `/train-tune/test/:id`.
