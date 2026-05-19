# LabelLens

Web-based object detection application powered by **YOLOE-26L** with support for text prompts and visual prompts (SAVPE).

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Features

- **Text Prompt Detection** — type object labels (e.g. `person, car, dog`) to detect
- **Visual Prompt Detection** — upload a reference image, draw guided bounding boxes with hover X/Y alignment lines, and detect visually similar objects via SAVPE encoder
- **Image Detection** — upload static images (JPG, PNG)
- **Video Processing** — upload video files (MP4, AVI, MOV) with frame-by-frame detection
- **RTSP Live Streaming** — connect to RTSP camera streams with real-time WebSocket inference and visible connection errors
- **Configurable Settings** — confidence threshold plus label, bbox, and smoothed live mask overlay toggles
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
│       ├── api/             # REST & WebSocket clients
│       ├── composables/     # Backend status, WebSocket hooks
│       ├── components/      # UI components (BBoxAnnotation, Viewer, etc.)
│       ├── stores/          # Pinia state management
│       └── types/           # TypeScript interfaces
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
- YOLOE-26L segmentation model weight (`models/yoloe-26l-seg.pt`)

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

App runs at `http://<your-ip>:3131`. Accessible from any device on the network.

## Usage

1. **Text Prompt** — type comma-separated labels in the grounding prompt field
2. **Visual Prompt** — switch to "Visual Prompt" tab, upload a reference image, draw bounding boxes on target objects, assign labels
3. **Select media** — choose Image / Video / RTSP before adding media input
4. **Adjust settings** — set confidence threshold, toggle labels/bboxes, and turn `Show Masks` on/off live after inference
5. **Run or switch media** — Start/Stop can reuse the current media; use Clear Media after stopping inference to switch modes
6. **Start Inference** — click "Start Inference" to run detection; RTSP connection/config errors appear in the viewer and stats/logs float on the right side

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
