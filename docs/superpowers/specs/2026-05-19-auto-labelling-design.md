# Auto-Labelling Design Specification

**Date:** 2026-05-19
**Status:** Draft
**Feature:** Auto-Labelling — dataset collection, annotation review, and export for YOLO model fine-tuning

---

## Context

LabelLens currently supports inference-only workflows: detect objects via text/visual/free prompts and display results. There is no mechanism to persist detection results as labeled datasets. Users who want to fine-tune YOLO models need annotated datasets — currently they must use external tools like Roboflow.

This feature turns LabelLens into a lightweight annotation platform by:
1. Saving inference results as labeled dataset entries (quick-save from workspace)
2. Providing batch auto-labeling for multiple images
3. Offering a Dataset Manager for reviewing, accepting/rejecting detections, and exporting in YOLO/COCO formats

The existing Visual Prompt infrastructure (BBoxAnnotation, SAVPE encoder, detection result structures) serves as the foundation — detection results already contain box coordinates, labels, confidence scores, and mask data.

---

## Requirements

### Collected from brainstorming

| Requirement | Decision |
|---|---|
| Export formats | YOLO TXT + COCO JSON (user-selectable) |
| Workflow | Post-inference quick-save AND batch auto-label |
| Dataset management | Multi-project datasets |
| Annotation editing | Review-only (accept/reject per detection, no bbox editing) |
| Storage | Filesystem-based, YOLO-compatible folder structure |
| Frame sampling (video/RTSP) | Configurable per auto-label session only |
| Navigation | New "Datasets" tab on FeatureModes landing page |
| Overlay controls | Global toggle + per-class + per-object show/hide |

---

## Architecture

### Approach: Hybrid (Quick-Save + Dataset Manager Page)

Two entry points for adding images to datasets:
1. **Quick-Save** — button in workspace inference panel, saves current detection results to selected dataset project
2. **Dataset Manager** — dedicated page for batch upload, gallery review, accept/reject, and export

Both share the same backend API and filesystem storage.

---

## Data Model

### Filesystem Structure

```
datasets/
├── {project_name}/
│   ├── meta.json              # project metadata
│   ├── images/
│   │   ├── img_001.jpg        # original image
│   │   └── ...
│   ├── labels/                # generated at export time
│   │   ├── img_001.txt        # YOLO format
│   │   └── ...
│   └── annotations/
│       ├── img_001.json       # full detection data + review state
│       └── ...
```

### meta.json

```json
{
  "name": "product-defects",
  "created": "2026-05-19T10:00:00",
  "classes": ["defect", "scratch", "dent"],
  "class_to_id": {"defect": 0, "scratch": 1, "dent": 2},
  "stats": {
    "total_images": 45,
    "total_annotations": 128,
    "accepted": 115,
    "rejected": 13
  }
}
```

### annotations/{img_id}.json

```json
{
  "image": "img_001.jpg",
  "width": 1920,
  "height": 1080,
  "source": "inference|batch|video|rtsp",
  "created": "2026-05-19T10:05:00",
  "detections": [
    {
      "id": 0,
      "box": [100, 200, 300, 400],
      "label": "defect",
      "confidence": 0.952,
      "cls_id": 0,
      "accepted": true,
      "mask": [[x, y], ...]
    }
  ]
}
```

Classes are auto-discovered from saved detection labels. `class_to_id` mapping is maintained in `meta.json` and updated when new labels appear.

Labels directory (`labels/*.txt`) is generated at export time from accepted detections only. This allows users to change accept/reject state anytime without data loss.

---

## Backend API

### New files
- `backend/routers/dataset.py` — API endpoints
- `backend/services/dataset.py` — filesystem operations, export logic

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/datasets` | List all dataset projects with stats |
| POST | `/api/datasets` | Create new project (name, optional classes) |
| DELETE | `/api/datasets/{name}` | Delete project and all files |
| GET | `/api/datasets/{name}/images` | List images in project (paginated) |
| GET | `/api/datasets/{name}/images/{img_id}` | Get single image + annotations |
| POST | `/api/datasets/{name}/save` | Save inference results to dataset |
| POST | `/api/datasets/{name}/batch` | Batch upload + auto-label (returns job_id) |
| GET | `/api/datasets/{name}/batch/{job_id}` | Batch job status |
| PATCH | `/api/datasets/{name}/images/{img_id}/review` | Accept/reject detections |
| DELETE | `/api/datasets/{name}/images/{img_id}` | Remove image from dataset |
| POST | `/api/datasets/{name}/export` | Export dataset (format: "yolo" or "coco") → download zip |

### Save Endpoint Details

`POST /api/datasets/{name}/save`

Receives the same data as inference results:
- `image`: original image file (multipart)
- `detections`: JSON array of detection objects (box, label, confidence, cls_id, mask)
- `source`: "inference" | "video" | "rtsp"

Generates unique image ID, saves original image, writes annotation JSON. All detections default to `accepted: true`.

### Batch Endpoint Details

`POST /api/datasets/{name}/batch`

Receives:
- `files`: multiple image files (multipart)
- `prompt_type`: "text" | "visual" | "free"
- `labels`, `refer_image`, `bboxes`, `vcls`: prompt parameters (same as detect/image)
- `confidence`: threshold

#### Initialization per Mode

| Mode | Init step | Per-image call | Notes |
|---|---|---|---|
| **Free** | None | `predict_free(img, conf)` | No setup needed |
| **Text** | `set_classes(labels)` (cached) | `predict(img, conf)` | Labels set once, reused for all images |
| **Visual** | `setup_visual_prompt(ref_img, bboxes, cls)` | `predict_with_vpe(img, conf)` | **Single reference image only** (YOLOE limitation) |

#### Visual Prompt Limitation

YOLOE SAVPE supports **one reference image with multiple bbox annotations** per session. Calling `setup_visual_prompt()` again overwrites the previous VPE. For multi-reference scenarios, users must run separate batch sessions.

#### Batch Processing Flow

1. Validate model is loaded for the selected `prompt_type`
2. Initialize once per mode (text: `set_classes`, visual: `setup_visual_prompt`, free: skip)
3. Process each image through the appropriate predict method
4. Save results with all detections as `accepted: true`
5. Return job status for progress tracking

#### Dual Init Path (Workspace + Dialog)

The batch dialog supports two initialization paths:
- **From workspace**: If visual prompt is already configured in the workspace, batch reuses the pre-set VPE. Dialog auto-detects and shows "Using workspace prompt" indicator.
- **From dialog**: If no prompt is configured, dialog shows inline setup (ref image upload + bbox annotation for visual mode, labels input for text mode). Backend receives prompt params and initializes during batch processing.

### Video/RTSP Auto-Label

For saving frames from video or RTSP to dataset:
- `sample_rate`: configurable (e.g., "1fps" = 1 frame per second from video, or "every N frames" from RTSP)
- Only applies to the auto-label save operation, not the display inference

Implementation: add optional `sample_rate` parameter to the save endpoint when source is "video" or "rtsp". The backend processes the media with the specified sampling rate, runs inference on sampled frames, and saves results.

### Review Endpoint Details

`PATCH /api/datasets/{name}/images/{img_id}/review`

```json
{
  "detections": [
    {"id": 0, "accepted": true},
    {"id": 1, "accepted": false}
  ]
}
```

Updates accept/reject state per detection in the annotation JSON.

### Export Endpoint Details

`POST /api/datasets/{name}/export`

Receives: `format: "yolo" | "coco"`, `split: float` (train ratio, default 0.8)

**YOLO export** generates:
- `images/train/` — accepted images
- `labels/train/` — YOLO TXT files (only accepted detections)
- `dataset.yaml` — YOLO training config

**COCO export** generates:
- Single `coco.json` with images, annotations, categories
- `images/` folder with accepted images

Both return a downloadable zip file.

---

## Frontend

### Navigation

Add "Datasets" tab to the FeatureModes landing page. Two tabs:
- **Inference** — current workspace (Free Mode / Prompt Mode)
- **Datasets** — Dataset Manager

### Dataset Manager Page

**Route:** `/datasets` (or as tab content on landing page)

**Project List View:**
- Cards showing project name, image count, annotation count, last modified
- "New Dataset" button (creates project with name + optional class list)
- Click card → Dataset Detail

**Dataset Detail View:**
- **Header**: project name, stats badge, Batch Upload button, Export button
- **Image Gallery** (left): grid of image thumbnails with status badges (✓ all accepted, ⚠ has unreviewed/rejected, empty new)
- **Review Panel** (right sidebar):
  - **Global overlay controls**: BBox / Labels / Mask toggles (top of image viewer)
  - **Per-class filters**: list of classes with eye icon to show/hide all objects of that class
  - **Detection list**: each detection row shows color dot, label, confidence, coordinates, eye icon (per-object overlay), accept/reject buttons
  - Rejected detections shown with reduced opacity and strikethrough label
  - **Summary bar**: accepted/rejected counts, Next/Prev navigation

**Export Dialog:**
- Format selector: YOLO / COCO
- Train/val split slider (optional, default 80/20)
- Download button

### Auto-Labelling Trigger (Workspace)

Before running inference, user activates Auto-Labelling mode:

1. **Trigger**: Toggle/button "Auto-Label" in workspace controls
2. **Modal opens** with configuration:
   - **Dataset project**: dropdown (select existing or create new)
   - **Frame rate** (video/RTSP only): input field, default 1 fps — controls how many frames are captured and saved
   - **Active indicator**: persistent badge in UI showing auto-labelling is ON + target dataset name
3. **Behavior when active**:
   - Image inference: detection results auto-save to selected dataset after each run
   - Video/RTSP inference: frames sampled at configured fps, each auto-saved with detections
   - All detections saved as `accepted: true` — user reviews later in Dataset Manager
   - Toast notification on each save (image name + detection count)
4. **Deactivate**: toggle off → modal closes → inference runs normally without saving

This is modeled after Roboflow's auto-labelling input flow.

### Quick-Save (Manual)

When auto-labelling is NOT active, user can still manually save:
- Dropdown to select target dataset project in inference results panel
- "Save" button
- Saves current image + all detections to selected dataset
- Toast notification on success

### Batch Upload

Modal/dialog in Dataset Manager:
- File drop zone for multiple images
- Inference configuration:
  - Prompt mode indicator (uses current workspace model state)
  - **Frame rate** input: for video files uploaded in batch, controls sampling fps (default 1 fps)
- Uses current inference mode (free/text/visual with current prompts)
- Progress bar during processing
- Results appear in gallery for review

---

## Export Formats

### YOLO TXT

One `.txt` file per image, one line per accepted detection:
```
class_id x_center y_center width height
```
All values normalized to [0, 1]. Plus `dataset.yaml`:
```yaml
path: ./datasets/product-defects
train: images/train
val: images/val
names:
  0: defect
  1: scratch
  2: dent
```

### COCO JSON

Single JSON file:
```json
{
  "images": [{"id": 1, "file_name": "img_001.jpg", "width": 1920, "height": 1080}],
  "annotations": [{"id": 1, "image_id": 1, "category_id": 0, "bbox": [x, y, w, h], "area": ..., "segmentation": [...]}],
  "categories": [{"id": 0, "name": "defect"}, ...]
}
```

---

## Implementation Scope

### New files
- `backend/routers/dataset.py` — dataset API endpoints
- `backend/services/dataset.py` — filesystem CRUD, export logic
- `frontend/src/pages/datasets/` — Dataset Manager page components
  - `DatasetList.vue` — project cards
  - `DatasetDetail.vue` — gallery + review layout
  - `DatasetReviewPanel.vue` — per-image review sidebar
  - `DatasetExportDialog.vue` — format selection + download
  - `BatchUploadDialog.vue` — multi-image upload
- `frontend/src/shared/api/dataset.ts` — API client for dataset endpoints
- `frontend/src/shared/stores/dataset.ts` — Pinia store for dataset state

### Modified files
- `frontend/src/pages/landing/FeatureModes.vue` — add Datasets tab
- `frontend/src/pages/workspace/components/` — add Quick-Save UI to inference panel
- `backend/main.py` — register dataset router
- `CLAUDE.md` — update feature list and project structure

---

## Verification

1. **Quick-save**: Run inference on image → click Save → verify image + annotations appear in dataset folder
2. **Batch upload**: Upload 10 images → verify auto-labeling runs → verify results in gallery
3. **Review**: Open dataset detail → accept/reject detections → verify state persists → verify overlay controls work (global, per-class, per-object)
4. **Export YOLO**: Export dataset → verify labels/*.txt contain only accepted detections → verify dataset.yaml is correct
5. **Export COCO**: Export dataset → verify coco.json structure matches COCO format spec
6. **Multi-project**: Create 2+ datasets → verify isolation between projects
7. **Frame sampling (video)**: Save from video with custom sample rate → verify correct number of frames saved
