# Operations Runbook

LabelLens is currently operated as a local-network development application with GPU-backed backend services.

## Start Services

From repo root:

```bash
./run-dev.sh
```

Defaults:

| Service | Default |
|---------|---------|
| Frontend | `http://localhost:8282` |
| Backend | `http://localhost:3131` |
| Frontend host | `0.0.0.0` |
| Backend host | `0.0.0.0` |

## Backend Only

```bash
CUDA_DEVICE_ORDER=PCI_BUS_ID DEVICE=0   env/bin/python -m uvicorn backend.main:app   --host 0.0.0.0   --port 3131   --reload
```

## Frontend Only

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 8282
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL_PATH` | `models/yoloe-26l-seg.pt` | Prompt model path |
| `LABELLENS_CUDA_VISIBLE_DEVICES` | `1,2` | Physical GPUs visible to LabelLens |
| `DEVICE` | `0` | YOLOE local CUDA device after visible mapping |
| `SAM_ENABLED` | `true` | Enables SAM endpoints and auto-mask attempts |
| `SAM_MODEL` | `sam2.1_l.pt` | SAM model file or identifier |
| `SAM_DEVICE` | `1` | SAM local CUDA device after visible mapping |
| `CUDA_DEVICE_ORDER` | `PCI_BUS_ID` | Align CUDA order to PCI bus order |
| `HOST` | `0.0.0.0` | Backend host |
| `PORT` | `3131` | Backend port |
| `FRONTEND_PORT` | `8282` | Frontend dev server port |
| `CORS_ORIGINS` | `*` | Backend CORS origins |
| `TRAIN_VISIBLE_DEVICES_STANDARD` | `1` | Standard training visible physical GPUs |
| `TRAIN_VISIBLE_DEVICES_HIGH_SPEED` | `1,2` | High-speed training visible physical GPUs |
| `TRAIN_DEVICE_STANDARD` | `1` | Standard Ultralytics device arg |
| `TRAIN_DEVICE_HIGH_SPEED` | `1,2` | High-speed Ultralytics device arg |
| `TRAIN_AMP_STANDARD` | `true` | Standard AMP setting |
| `TRAIN_AMP_HIGH_SPEED` | `false` | High-speed DDP AMP setting |
| `LABELLENS_TRAIN_DDP_FIND_UNUSED` | `0` | Optional DDP patch flag |
| `LABELLENS_TRAIN_TUNE_FAKE` | `0` | Mock training runtime flag |

## Runtime Directories

| Path | Backup? | Notes |
|------|---------|-------|
| `models/` | Yes | Required model weights; large local artifacts |
| `datasets/` | Yes | Dataset projects and Train Tune metadata |
| `datasets/_train_tune/` | Yes | Dataset Versions, jobs, model registry metadata |
| `traintune-workspace/` | Yes for important runs | Checkpoints, logs, results CSV |
| `temp/` | Usually no | Debug/runtime scratch data |
| `frontend/dist/` | No | Rebuildable frontend output |

## Health Checks

```bash
curl http://localhost:3131/api/health
curl http://localhost:3131/api/model/status
curl http://localhost:3131/api/sam/status
```

## Common Recovery

| Problem | Action |
|---------|--------|
| Backend cannot import dependencies | Reinstall with `env/bin/python -m pip install -r backend/requirements.txt` |
| Frontend dependencies missing | Run `npm install` in `frontend/` |
| Prompt model load fails | Verify `models/yoloe-26l-seg.pt` |
| Free model load fails | Verify `models/yoloe-26l-seg-pf.pt` |
| SAM load fails | Verify `models/sam2.1_l.pt`, `SAM_ENABLED`, and GPU availability |
| CUDA device mismatch | Check `nvidia-smi`, `CUDA_DEVICE_ORDER`, and visible-device env vars |
| RTSP timeout | Test RTSP URL separately, confirm LAN/firewall access, lower stream resolution if needed |
| Training job stuck | Check `/api/training/jobs/{job_id}`, job events, worker logs, and `traintune-workspace/` |
| High-Speed DDP failure | Retry Standard Mode, keep `TRAIN_AMP_HIGH_SPEED=false`, inspect checkpoint task compatibility |

## Pre-Run Checklist

- `env/` exists and has backend dependencies.
- `frontend/node_modules/` exists or `npm install` has been run.
- Required model files are present.
- `nvidia-smi` shows expected GPU order.
- No unrelated process is using ports `3131` or `8282`.
- RTSP cameras are reachable from the backend machine.

## Shutdown

If started through `./run-dev.sh`, press `Ctrl+C`. The script traps exit and stops both backend and frontend child processes.
