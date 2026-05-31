# Installation Guide

LabelLens is a web-based object detection and dataset iteration application. Backend (FastAPI + PyTorch) handles CV workloads, frontend (Vue 3 SPA) provides the UI. They communicate via REST API and WebSockets.

## Prerequisites

### Hardware

- **NVIDIA GPU** with CUDA support (required for inference, training, and SAM2.1)
- Minimum 8 GB VRAM; 16+ GB recommended for Train Tune workloads
- Disk space: ~5 GB for model weights + runtime data

### Software

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| npm | 9+ | Package manager |
| CUDA Toolkit | 11.8+ | GPU acceleration |
| Git | 2.30+ | Repository clone |

### GPU Layout (Default)

LabelLens defaults to physical GPUs `1,2`, reserving physical GPU `0` for other workloads (e.g., vLLM).

| Workload | Physical GPU | Config Key |
|---|---|---|
| YOLOE Inference | GPU 1 | `DEVICE=0` (after CUDA_VISIBLE_DEVICES) |
| SAM2.1 Auto-mask | GPU 2 | `SAM_DEVICE=1` (after CUDA_VISIBLE_DEVICES) |
| Train Tune Standard | GPU 1 | `TRAIN_VISIBLE_DEVICES_STANDARD=1` |
| Train Tune High-Speed | GPU 1,2 | `TRAIN_VISIBLE_DEVICES_HIGH_SPEED=1,2` |

Adjust via environment variables if your GPU topology differs.

---

## 1. Clone Repository

```bash
git clone <repo-url> LabelLens
cd LabelLens
```

---

## 2. Backend Setup

### Linux

```bash
python3 -m venv env
source env/bin/activate
pip install -r backend/requirements.txt
```

### Windows

```powershell
python -m venv env
env\Scripts\activate
pip install -r backend\requirements.txt
```

> **Note:** The `env/` directory is gitignored. The project convention is `@env/` in docs but `env/` on disk.

### Key Backend Dependencies

- FastAPI + Uvicorn — REST API server
- Ultralytics — YOLO model framework
- OpenCV (headless) — image/video processing
- Albumentations — augmentation pipeline
- WebSockets — real-time streaming
- CLIP (from Ultralytics GitHub) — text/visual prompt encoding

---

## 3. Frontend Setup

```bash
cd frontend
npm install
cd ..
```

No OS-specific differences.

---

## 4. Model Weights

Download the following model files and place them in the `models/` directory at the project root:

| File | Size (approx.) | Purpose |
|---|---|---|
| `yoloe-26l-seg.pt` | ~500 MB | YOLOE prompt-based inference (text + visual prompts) |
| `yoloe-26l-seg-pf.pt` | ~500 MB | YOLOE prompt-free inference (LRPC, Free Inference mode) |
| `sam2.1_l.pt` | ~1.2 GB | SAM2.1 Hiera Large for auto-mask generation |

### Sources

- YOLOE weights: [THU-MIG/yoloe](https://github.com/THU-MIG/yoloe) releases or [HuggingFace](https://huggingface.co/spaces/jameslahm/yoloe)
- SAM2.1 weights: [Meta SAM2](https://github.com/facebookresearch/sam2) releases

```bash
mkdir -p models
# Place downloaded .pt files into models/
```

---

## 5. Environment Configuration

All configuration is via environment variables. Defaults work out of the box for the standard GPU layout.

### Core Variables

| Variable | Default | Description |
|---|---|---|
| `CUDA_DEVICE_ORDER` | `PCI_BUS_ID` | Keeps CUDA device IDs aligned with `nvidia-smi` |
| `LABELLENS_CUDA_VISIBLE_DEVICES` | `1,2` | Physical GPUs visible to LabelLens |
| `DEVICE` | `0` | Local CUDA device for YOLOE (after visible mapping) |
| `SAM_ENABLED` | `true` | Enable/disable SAM2.1 service |
| `SAM_MODEL` | `sam2.1_l.pt` | SAM model filename |
| `SAM_DEVICE` | `1` | Local CUDA device for SAM2.1 |
| `MODEL_PATH` | `models/yoloe-26l-seg.pt` | YOLOE prompt model path |
| `HOST` | `0.0.0.0` | Backend bind address |
| `PORT` | `3131` | Backend port |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

### Train Tune Variables

| Variable | Default | Description |
|---|---|---|
| `TRAIN_VISIBLE_DEVICES_STANDARD` | `1` | GPUs for Standard mode training |
| `TRAIN_VISIBLE_DEVICES_HIGH_SPEED` | `1,2` | GPUs for High-Speed DDP training |
| `TRAIN_DEVICE_STANDARD` | `1` | Device ID for Standard mode |
| `TRAIN_DEVICE_HIGH_SPEED` | `1,2` | Device IDs for High-Speed mode |
| `TRAIN_AMP_STANDARD` | `true` | AMP enabled for Standard mode |
| `TRAIN_AMP_HIGH_SPEED` | `false` | AMP disabled for High-Speed DDP |
| `LABELLENS_TRAIN_DDP_FIND_UNUSED` | `0` | DDP `find_unused_parameters` flag |
| `LABELLENS_TRAIN_TUNE_FAKE` | `0` | Set `1` for dry-run testing without GPU |

### Setting Environment Variables

**Linux (bash):**
```bash
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export LABELLENS_CUDA_VISIBLE_DEVICES=1,2
export DEVICE=0
```

**Windows (PowerShell):**
```powershell
$env:CUDA_DEVICE_ORDER = "PCI_BUS_ID"
$env:LABELLENS_CUDA_VISIBLE_DEVICES = "1,2"
$env:DEVICE = "0"
```

Or create a `.env` file in the project root (loaded by the application on startup).

---

## 6. Running the Application

### Quick Start (Both Services)

**Linux:**
```bash
./run-dev.sh
```

**Windows:** Start backend and frontend in separate terminals (see below).

### Backend Only

**Linux:**
```bash
source env/bin/activate
CUDA_DEVICE_ORDER=PCI_BUS_ID DEVICE=0 python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 3131 --reload
```

**Windows (PowerShell):**
```powershell
env\Scripts\activate
$env:CUDA_DEVICE_ORDER = "PCI_BUS_ID"
$env:DEVICE = "0"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3131 --reload
```

### Frontend Only

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 8282
```

The frontend dev server proxies API requests to `http://localhost:3131` automatically.

### Access URLs

| Service | URL |
|---|---|
| Frontend | `http://localhost:8282` |
| Backend API | `http://localhost:3131` |
| LAN access | `http://<your-ip>:8282` |

---

## 7. Verification

### Health Check

```bash
curl http://localhost:3131/api/health
```

Expected response: `{"status": "healthy"}`

### Model Status

```bash
curl http://localhost:3131/api/model/status
```

Returns YOLOE model load state and device info.

### SAM Status

```bash
curl http://localhost:3131/api/sam/status
```

Returns SAM2.1 service state (loaded/unloaded/unavailable).

### Backend Unit Tests

```bash
# Linux
source env/bin/activate
python -m unittest discover backend/tests

# Windows
env\Scripts\activate
python -m unittest discover backend\tests
```

### Frontend Build Check

```bash
cd frontend
npm run build
```

Should complete with no errors.

---

## 8. Production Build

### Build Frontend

```bash
cd frontend
npm run build
```

Output goes to `frontend/dist/`. Serve with any static file server (nginx, caddy, etc.) or configure the backend to serve it.

### Run Backend (Production)

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3131 --workers 1
```

> **Note:** Use `--workers 1` — model state is in-process and does not support multi-worker sharing.

---

## 9. Troubleshooting

### CUDA device not found

```
RuntimeError: CUDA out of memory / device not available
```

- Verify GPUs visible: `nvidia-smi`
- Check `LABELLENS_CUDA_VISIBLE_DEVICES` matches your hardware
- Ensure `CUDA_DEVICE_ORDER=PCI_BUS_ID` is set
- Reduce to a single GPU if VRAM is limited

### Model weights not found

```
FileNotFoundError: models/yoloe-26l-seg.pt
```

- Confirm model files exist in `models/` directory
- Check `MODEL_PATH` env var points to correct file
- Verify file integrity (re-download if corrupted)

### Port already in use

```
OSError: [Errno 98] Address already in use
```

- Backend: change `PORT` env var or `--port` flag
- Frontend: change `--port` flag in `npm run dev`
- Find process: `lsof -i :3131` (Linux) or `netstat -ano | findstr :3131` (Windows)

### Frontend can't reach backend

- Confirm backend is running on expected port
- Check Vite proxy config in `frontend/vite.config.ts` points to backend
- Verify `CORS_ORIGINS` allows frontend origin
- For LAN access, ensure firewall allows traffic on both ports

### SAM2.1 fails to load

- Non-fatal — application continues without auto-mask
- Verify `sam2.1_l.pt` exists in `models/`
- Check `SAM_DEVICE` points to an available GPU
- Set `SAM_ENABLED=false` to suppress load attempts

### Python venv issues

- Ensure venv uses correct Python version: `python --version`
- Recreate venv if dependency conflicts occur:
  ```bash
  rm -rf env
  python3 -m venv env
  source env/bin/activate  # or env\Scripts\activate on Windows
  pip install -r backend/requirements.txt
  ```

---

## 10. Runtime Directories

| Path | Purpose | Backup |
|---|---|---|
| `models/` | Model weights | Yes |
| `datasets/` | Dataset projects and metadata | Yes — user data |
| `datasets/_train_tune/` | Dataset version snapshots | Yes |
| `traintune-workspace/` | Training checkpoints, logs, results | Yes for important runs |
| `temp/` | Runtime debug/scratch data | No |
| `frontend/dist/` | Production build output | No — rebuildable |
