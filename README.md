# LabelLens

Web-based object detection application powered by **YOLOE-26s** with support for text prompts and visual prompts (SAVPE).

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Features

- **Text Prompt Detection** — type object labels (e.g. `person, car, dog`) to detect
- **Visual Prompt Detection** — upload a reference image, draw bounding boxes on objects, and detect visually similar objects via SAVPE encoder
- **Image Detection** — upload static images (JPG, PNG)
- **Video Processing** — upload video files (MP4, AVI, MOV) with frame-by-frame detection
- **RTSP Live Streaming** — connect to RTSP camera streams with real-time WebSocket inference
- **Configurable Settings** — confidence threshold, label/bbox visibility toggles
- **Detection Metrics** — object count, FPS, inference time, class breakdown

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 (Composition API) + TypeScript + Tailwind CSS v4 |
| Backend | FastAPI (Python) |
| AI Model | YOLOE-26s via Ultralytics (text + visual SAVPE prompts) |
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
├── PRD.md                   # Product requirements document
├── DESIGN.md                # Supabase-inspired design system tokens
└── AGENTS.md                # Agent guidelines & project overview
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- YOLOE-26s model weight (`yoloe-26s.pt`)

### Backend

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3131 --reload
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
3. **Select media** — switch between Image / Video / RTSP input
4. **Adjust settings** — set confidence threshold, toggle labels/bboxes
5. **Start Inference** — click "Start Inference" to run detection

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `yoloe-26s.pt` | Path to YOLOE model weights |
| `HOST` | `0.0.0.0` | Backend host |
| `PORT` | `3131` | Backend port |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

## License

Internal project — not for public distribution.
