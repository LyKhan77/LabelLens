# LabelLens

Web-based object detection application powered by **YOLOE-26L** with support for text prompts and visual prompts (SAVPE).

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Features

- **Feature Modes Page** — root path `/` always opens mode selection; choose Free Inference (no prompts, 1200+ LVIS categories via LRPC), Prompt Inference (text/visual prompts), or Train Tune, then enter the matching workspace
- **Train Tune Workspace** — dedicated `/train-tune` YOLO detection/segmentation builder with task-selectable immutable Dataset Version snapshots, bbox or polygon-mask label export, missing-mask validation with Dataset Workspace handoff, preprocessing policy with Keep/Letterbox/Stretch resize strategies, Basic online augmentation or Advanced Add Augmentation Step workflow with optional 1x-5x train-only materialized images, smart recommended training settings by dataset size, Auto Batch (`batch=-1`), early-stopping Patience, real policy preview samples with bbox/mask overlays, locked version configuration preview, backend training config validation/preflight, compact model/job badges, JSON-safe metric history, compact metric trends plus dataset/run/compute details, `/train-tune/test/:id` custom model testing, Standard vs High-Speed RTX 5080 GPU modes, full-process cancellation, failed-job re-compute/delete, last-checkpoint resume, train logs/results CSV artifacts under `traintune-workspace/`, and model version registry
- **Dataset Manager Page** — standalone `/datasets` workspace for multi-project dataset management with Inference-style header navigation, project/image delete controls, Select All Files gallery selection, real overlay thumbnail gallery review, cross-page modal inspector navigation, compact class/status review controls, zoomable/pannable review canvas, viewport-clamped Edit BBox popover, persisted per-dataset class colors with manual swatches, manual bbox add/edit/delete annotation editor, multi-prompt Infer Next visual-prompt candidate propagation with per-candidate Accept/Reject plus Accept All & Continue, direct annotation delete, Rapid Inference jobs, and YOLO/COCO export that preserves original input filenames in exported artifacts
- **Free Inference Mode** — detect all visible objects without any prompt using YOLOE's internal vocabulary
- **Text Prompt Detection** — type object labels (e.g. `person, car, dog`) to detect
- **Visual Prompt Detection** — upload a reference image, draw guided bounding boxes with hover X/Y alignment lines, and detect visually similar objects via SAVPE encoder
- **Image Detection** — upload static images (JPG, PNG)
- **Video Processing** — upload video files (MP4, AVI, MOV) with frame-by-frame detection
- **RTSP Live Streaming** — connect to RTSP camera streams with real-time WebSocket inference and visible connection errors
- **Configurable Settings** — confidence threshold plus backend-rendered label, bbox, and clipped mask overlay toggles
- **Floating Inference Panel** — compact right-side stats and scrollable detection log for active results
- **Clear Media Workflow** — stop inference, clear current media, then switch Image/Video/RTSP modes without losing prompt state
- **Workspace Auto-Label Modal** — trigger auto-save only from Auto-Label modal; RTSP saves continuous viewer frames while active, optional `MM:SS` timer stops auto-label only, and Stop Inference also stops auto-label
- **Rapid Inference Workflow** — upload images or sample video frames into a dataset, configure Free/Text/Visual YOLOE grounding in Dataset Manager, load the required model, run batch inference with frame-by-frame progress, `Frame x/y` highlighting, and overlay preview, then inspect detections in a modal reviewer with accept/reject, manual bbox correction, direct label deletion, and multi-prompt Infer Next visual-prompt candidates for missing objects

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 (Composition API) + TypeScript + Tailwind CSS v4 |
| Backend | FastAPI (Python) |
| AI Model | YOLOE-26L via Ultralytics (text + visual SAVPE prompts, segmentation masks) |
| Communication | REST API (image/video) + WebSocket (RTSP) |
| Media Processing | OpenCV, FFmpeg |

## Project Structure

```
LabelLens/
├── frontend/                # Vue 3 SPA
│   └── src/
│       ├── app/             # App shell, entrypoint, global style
│       ├── pages/           # Logical pages (mode-select, datasets, train-tune, workspace)
│       │   ├── datasets/    # Dataset Manager gallery, review modal, manual bbox editor, auto-label wizard
│       │   ├── train-tune/  # Training builder, live progress, result pages, custom model testing
│       │   └── workspace/
│       │       ├── components/   # Workspace layout/display blocks
│       │       └── sections/     # Grounding, media, settings sections
│       ├── shared/          # Shared api, composables, stores, types
│       └── assets/          # Static assets
├── backend/                 # FastAPI server
│   ├── routers/             # API endpoints (health, detection, stream, dataset, training)
│   ├── services/            # Model, video, RTSP, activity, training, runtime services
│   ├── train_worker.py      # Background training worker process for Train Tune jobs
│   └── utils/               # Drawing, encoding helpers
├── docs/plans/              # Saved implementation plans
├── PRD.md                   # Product requirements document
├── DESIGN.md                # Supabase-inspired design system tokens
└── AGENTS.md                # Agent guidelines & project overview
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- YOLOE-26L segmentation model weight (`models/yoloe-26l-seg.pt` for prompt mode, `models/yoloe-26l-seg-pf.pt` for free mode)

### Run Frontend + Backend (Recommended)

```bash
./run-dev.sh
```

Default URL:
- Frontend: `http://localhost:8282`
- Backend API: `http://localhost:3131`

### Backend

```bash
pip install -r backend/requirements.txt
CUDA_DEVICE_ORDER=PCI_BUS_ID DEVICE=0 python -m uvicorn backend.main:app --host 0.0.0.0 --port 3131 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs at `http://<your-ip>:8282`. Backend API runs at `http://<your-ip>:3131`.

## Usage

1. **Select Mode** — open `/`, choose Free Inference, Prompt Inference, or Train Tune on the landing page
2. **Text Prompt** — type comma-separated labels in the grounding prompt field (Prompt mode only)
3. **Visual Prompt** — switch to "Visual Prompt" tab, upload a reference image, draw bounding boxes on target objects, assign labels (Prompt mode only)
4. **Select media** — choose Image / Video / RTSP before adding media input
5. **Adjust settings** — set confidence threshold and choose label/bbox/mask overlays before starting inference; image/video changes require rerun, RTSP changes require restarting the stream
6. **Run or switch media** — Start/Stop can reuse the current media; use Clear Media after stopping inference to switch modes
7. **Start Inference** — click "Start Inference" to run detection; RTSP connection/config errors appear in the viewer and stats/logs float on the right side
8. **Auto-Label (optional)** — open Dataset section in sidebar, start Auto-Label via modal, and stop from modal or Stop Inference. For RTSP, optional `MM:SS` timer stops auto-label while stream keeps running.
9. **Switch Mode** — click "Switch Mode" in the header to return to mode selection

### Train Tune

1. Open `/train-tune` from the Feature Modes page.
2. Follow the builder stepper: choose a **Live Dataset** or **Export ZIP**, select **Detection** or **Segmentation**, configure YOLO11/YOLO26 architecture and training settings, then define split and the Roboflow-like Policy sections.
3. In **Policy**, choose resize strategy (**Keep original**, **Letterbox to image size**, or **Stretch to image size**) and select **Basic** augmentation for a safe online-only YOLO preset or **Advanced** to configure Add Augmentation Step controls. In Advanced mode, choose **Maximum Version Size** from 1x-5x only when materialized augmentation steps exist, and generate preview samples to inspect original/preprocessed/augmented images with bbox/mask overlays. Offline generated images are materialized only into the train split; val/test stay original.
4. Review the Snapshot Preview and create the immutable **Dataset Version**. Segmentation versions require every accepted object to already have a mask; missing masks are listed so they can be fixed in Dataset Workspace.
5. Select a Dataset Version from the sidebar to inspect its locked split, preprocessing, augmentation, source, **Recommended Settings** result, and **Refresh Estimate** result in **Training Preview**. Recommendations choose epochs, Patience, Auto Batch, image size, and Basic augmentation from the dataset image count; users can apply or override them.
6. Click **Start Training Job** from Training Preview to jump into the dedicated live monitor page at `/train-tune/jobs/:id`.
7. Watch compact metric trends, scrollable epoch history, dataset/run/compute configuration, ETA, checkpoints, train log/results CSV paths, and job events on that live progress page. Temporary `NaN` metrics from Ultralytics are sanitized so training job navigation remains available while runs continue.
8. Open the result page to inspect best metrics, full metric trends, Dataset Version configuration, and Training Configuration used by the model; use **Test Model** to run the registered artifact with bbox/mask overlays.
9. Delete unused Dataset Versions from the builder sidebar when a snapshot should be removed; versions referenced by jobs or models stay protected.
10. Delete a Model Version from its modal when its registered model, linked Training Job, metrics, and output folder should be removed; failed jobs still have their own **Re-compute** or **Delete** actions, and failed/cancelled jobs with `last.pt` can be resumed.
11. Review the dedicated result page at `/train-tune/results/:id` once a job completes, or test the artifact at `/train-tune/test/:id`.

Train Tune run artifacts are written to `traintune-workspace/<job-name>-<job-id>/`.

### Dataset Manager

1. Open `/datasets` from the Feature Modes page or directly in the browser.
2. Create, open, or delete a dataset project from the Dataset Manager overview.
3. Click **Rapid Inference** and upload either multiple images or one video. Video frames are sampled once based on the selected FPS until the video ends.
4. Choose Free, Text, or Visual prompt mode. Visual prompt uses an inline reference image + bbox annotation editor.
5. Load the required YOLOE model, start inference, and watch frame-by-frame progress with `Frame x/y` highlighting and overlay preview.
6. Inspect the paginated thumbnail gallery (25 images per page) with real bbox/mask overlays. Use Select All Files for the visible page/filter, delete selected images, delete a single card, or click any image to open the centered review modal with bbox/label/mask overlays, cross-page Prev/Next navigation, zoom/pan canvas controls, compact class filters with editable color swatches, per-object visibility, accept/reject controls, manual bbox add/edit/delete, direct saved-label delete, simplified multi-prompt Infer Next visual-prompt candidate review, and image delete.
7. For missing objects in sequential images, check one or more saved annotations as prompts, load the prompt model if needed, run **Infer Next**, then use **Accept** or **Reject** on individual candidates, or **Accept All & Continue** to save all visible candidates and propagate forward.
8. Delete any saved Rapid/Batch, Manual, or Visual Assist annotation directly from its detection row when it should not be exported.
9. Export accepted detections as YOLO TXT or COCO JSON with train/val split.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/yoloe-26l-seg.pt` | Path to YOLOE model weights; set `models/yoloe-26s-seg.pt` to roll back |
| `LABELLENS_CUDA_VISIBLE_DEVICES` | `1,2` | Physical CUDA devices visible to LabelLens; keeps the RTX 4090 at physical index `0` reserved for vLLM |
| `DEVICE` | `0` | Local CUDA device for YOLOE inference; with the default visible set, this maps to physical RTX 5080 index `1` |
| `SAM_DEVICE` | `1` | Local CUDA device for SAM2.1; with the default visible set, this maps to physical RTX 5080 index `2` |
| `CUDA_DEVICE_ORDER` | `PCI_BUS_ID` | Keeps PyTorch CUDA indexes aligned with `nvidia-smi` PCI order |
| `HOST` | `0.0.0.0` | Backend host |
| `PORT` | `3131` | Backend port |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `TRAIN_VISIBLE_DEVICES_STANDARD` | `1` | Physical CUDA devices exposed to Standard Mode Train Tune jobs; default maps to the first RTX 5080 |
| `TRAIN_VISIBLE_DEVICES_HIGH_SPEED` | `1,2` | Physical CUDA devices exposed to High-Speed Train Tune jobs; default maps to both RTX 5080 cards |
| `TRAIN_DEVICE_STANDARD` | `1` | Physical CUDA device string passed to Ultralytics for Standard Mode |
| `TRAIN_DEVICE_HIGH_SPEED` | `1,2` | Physical CUDA device string passed to Ultralytics for High-Speed Mode |
| `TRAIN_AMP_STANDARD` | `true` | Enables AMP for Standard Mode |
| `TRAIN_AMP_HIGH_SPEED` | `false` | Disables AMP for High-Speed DDP on RTX 5080 to avoid CUDA illegal-instruction failures |
| `LABELLENS_TRAIN_DDP_FIND_UNUSED` | `0` | Set to `1` to opt into the Ultralytics DDP `find_unused_parameters=True` patch for runs that need it |
| `LABELLENS_TRAIN_TUNE_FAKE` | `0` | Set to `1` to run mock training jobs that stream progress without real weights |

LabelLens defaults to `CUDA_VISIBLE_DEVICES=1,2` so the RTX 4090 at physical GPU `0` remains reserved for vLLM. Train Tune passes physical device IDs to Ultralytics because Ultralytics rewrites `CUDA_VISIBLE_DEVICES` from its `device` argument; Standard Mode uses physical GPU `1`, and High-Speed Mode uses physical GPUs `1,2` with AMP off for DDP stability.

## License

Internal project — not for public distribution.
