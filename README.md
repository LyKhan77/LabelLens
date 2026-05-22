# LabelLens

Web-based object detection application powered by **YOLOE-26L** with support for text prompts and visual prompts (SAVPE).

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Features

- **Feature Modes Page** — root path `/` always opens mode selection; choose Free Inference (no prompts, 1200+ LVIS categories via LRPC), Prompt Inference (text/visual prompts), or Train Tune, then enter the matching workspace
- **Train Tune Workspace** — dedicated `/train-tune` bbox detection builder with stepper-based immutable Dataset Version snapshots, locked version configuration preview, safe deletion for unused dataset versions, detection-checkpoint validation, compact metric trends on live progress and result views, Standard vs High-Speed GPU modes, real-time epoch history, failed-job re-compute/delete actions, output artifacts under `traintune-workspace/`, and model version registry
- **Dataset Manager Page** — standalone `/datasets` workspace for multi-project dataset management with Inference-style header navigation, project/image delete controls, Select All Files gallery selection, real overlay thumbnail gallery review, cross-page modal inspector navigation, compact class/status review controls, manual bbox add/edit/delete annotation editor, multi-prompt Infer Next visual-prompt candidate propagation with per-candidate Accept/Reject plus Accept All & Continue, direct annotation delete, Rapid Inference jobs, and YOLO/COCO export that preserves original input filenames in exported artifacts
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
│       │   ├── train-tune/  # Training builder, dedicated live progress pages, dedicated result pages
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
2. Follow the builder stepper: choose a **Live Dataset** or **Export ZIP**, configure YOLO architecture and training settings, then define split, preprocessing, and augmentation policy.
3. Review the Snapshot Preview and create the immutable **Dataset Version**.
4. Select a Dataset Version from the sidebar to inspect its locked split, preprocessing, augmentation, source, and training estimate in **Training Preview**.
5. Click **Start Training Job** from Training Preview to jump into the dedicated live monitor page at `/train-tune/jobs/:id`.
6. Watch compact metric trends, scrollable epoch history, ETA, checkpoints, and job events on that live progress page.
7. Open the result page to inspect best metrics, full metric trends, and the Dataset Version configuration used by the model.
8. Delete unused Dataset Versions from the builder sidebar when a snapshot should be removed; versions referenced by jobs or models stay protected.
9. If a job fails, use **Re-compute** or **Delete** from the failed job state.
10. Review the dedicated result page at `/train-tune/results/:id` once a job completes.

Train Tune run artifacts are written to `traintune-workspace/<job-name>-<job-id>/`.

### Dataset Manager

1. Open `/datasets` from the Feature Modes page or directly in the browser.
2. Create, open, or delete a dataset project from the Dataset Manager overview.
3. Click **Rapid Inference** and upload either multiple images or one video. Video frames are sampled once based on the selected FPS until the video ends.
4. Choose Free, Text, or Visual prompt mode. Visual prompt uses an inline reference image + bbox annotation editor.
5. Load the required YOLOE model, start inference, and watch frame-by-frame progress with `Frame x/y` highlighting and overlay preview.
6. Inspect the paginated thumbnail gallery (25 images per page) with real bbox/mask overlays. Use Select All Files for the visible page/filter, delete selected images, delete a single card, or click any image to open the centered review modal with bbox/label/mask overlays, cross-page Prev/Next navigation, compact class filters, per-object visibility, accept/reject controls, manual bbox add/edit/delete, direct saved-label delete, simplified multi-prompt Infer Next visual-prompt candidate review, and image delete.
7. For missing objects in sequential images, check one or more saved annotations as prompts, load the prompt model if needed, run **Infer Next**, then use **Accept** or **Reject** on individual candidates, or **Accept All & Continue** to save all visible candidates and propagate forward.
8. Delete any saved Rapid/Batch, Manual, or Visual Assist annotation directly from its detection row when it should not be exported.
9. Export accepted detections as YOLO TXT or COCO JSON with train/val split.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/yoloe-26l-seg.pt` | Path to YOLOE model weights; set `models/yoloe-26s-seg.pt` to roll back |
| `DEVICE` | `0` | CUDA device for inference; with `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `0` selects the first RTX 5080 |
| `CUDA_DEVICE_ORDER` | `PCI_BUS_ID` | Keeps PyTorch CUDA indexes aligned with `nvidia-smi` PCI order |
| `HOST` | `0.0.0.0` | Backend host |
| `PORT` | `3131` | Backend port |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `TRAIN_DEVICE_STANDARD` | `1` | CUDA device used by Standard Mode Train Tune jobs |
| `TRAIN_DEVICE_HIGH_SPEED` | `0,1` | CUDA devices used by High-Speed Train Tune jobs |
| `LABELLENS_TRAIN_TUNE_FAKE` | `0` | Set to `1` to run mock training jobs that stream progress without real weights |

## License

Internal project — not for public distribution.
