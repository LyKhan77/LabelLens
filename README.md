# LabelLens

Web-based object detection application powered by **YOLOE-26L** with support for text prompts and visual prompts (SAVPE).

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Features

- **Feature Modes Page** — select Free Inference (no prompts, 1200+ LVIS categories via LRPC) or Prompt Inference (text/visual prompts) before entering the dashboard
- **Free Inference Mode** — detect all visible objects without any prompt using YOLOE's internal vocabulary
- **Text Prompt Detection** — type object labels (e.g. `person, car, dog`) to detect
- **Visual Prompt Detection** — upload a reference image, draw guided bounding boxes with hover X/Y alignment lines, and detect visually similar objects via SAVPE encoder
- **Image Detection** — upload static images (JPG, PNG)
- **Video Processing** — upload video files (MP4, AVI, MOV) with frame-by-frame detection
- **RTSP Live Streaming** — connect to RTSP camera streams with real-time WebSocket inference and visible connection errors
- **Configurable Settings** — confidence threshold plus backend-rendered label, bbox, and clipped mask overlay toggles
- **Floating Inference Panel** — compact right-side stats and scrollable detection log for active results
- **Clear Media Workflow** — stop inference, clear current media, then switch Image/Video/RTSP modes without losing prompt state

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
│       ├── pages/           # Logical pages (mode-select, workspace)
│       │   └── workspace/
│       │       ├── components/   # Workspace layout/display blocks
│       │       └── sections/     # Grounding, media, settings sections
│       ├── shared/          # Shared api, composables, store, types
│       └── assets/          # Static assets
├── backend/                 # FastAPI server
│   ├── routers/             # API endpoints (health, detection, stream)
│   ├── services/            # Model, video, RTSP services
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

1. **Select Mode** — choose Free Inference (no prompts needed) or Prompt Inference on the landing page
2. **Text Prompt** — type comma-separated labels in the grounding prompt field (Prompt mode only)
3. **Visual Prompt** — switch to "Visual Prompt" tab, upload a reference image, draw bounding boxes on target objects, assign labels (Prompt mode only)
4. **Select media** — choose Image / Video / RTSP before adding media input
5. **Adjust settings** — set confidence threshold and choose label/bbox/mask overlays before starting inference; image/video changes require rerun, RTSP changes require restarting the stream
6. **Run or switch media** — Start/Stop can reuse the current media; use Clear Media after stopping inference to switch modes
7. **Start Inference** — click "Start Inference" to run detection; RTSP connection/config errors appear in the viewer and stats/logs float on the right side
8. **Switch Mode** — click "Switch Mode" in the header to return to mode selection

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/yoloe-26l-seg.pt` | Path to YOLOE model weights; set `models/yoloe-26s-seg.pt` to roll back |
| `DEVICE` | `0` | CUDA device for inference; with `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `0` selects the first RTX 5080 |
| `CUDA_DEVICE_ORDER` | `PCI_BUS_ID` | Keeps PyTorch CUDA indexes aligned with `nvidia-smi` PCI order |
| `HOST` | `0.0.0.0` | Backend host |
| `PORT` | `3131` | Backend port |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

## License

Internal project — not for public distribution.
