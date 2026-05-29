# Testing and Validation

LabelLens has automated backend unit tests and frontend type/build verification. Full CV behavior still requires manual end-to-end validation with real models, media, RTSP feeds, and GPU hardware.

## Automated Backend Tests

Run from repo root:

```bash
env/bin/python -m unittest discover backend/tests
```

Current coverage focuses on:

| Test area | Files |
|-----------|-------|
| Dataset service and router jobs | `backend/tests/test_dataset_service.py`, `backend/tests/test_dataset_router_jobs.py` |
| Train Tune service | `backend/tests/test_training_service.py` |
| Train Tune router | `backend/tests/test_training_router.py` |
| Training runtime | `backend/tests/test_training_runtime.py` |
| Train worker policy/runtime behavior | `backend/tests/test_train_worker.py` |

## Frontend Build Verification

Run from `frontend/`:

```bash
npm run build
```

This runs Vue TypeScript build checks and Vite production build.

## Local App Smoke Test

Run both services:

```bash
./run-dev.sh
```

Then open:

```text
http://localhost:8282
```

## Manual E2E Checklist

### Inference

- Load Free Inference model.
- Run image detection with prompt-free model.
- Load Prompt model.
- Run Text Prompt image detection.
- Run Visual Prompt image detection with a reference bbox.
- Run video detection with sample FPS.
- Run RTSP WebSocket inference against a known-good stream.
- Toggle labels, boxes, and masks.
- Stop inference and verify Clear Media behavior.

### Dataset Manager

- Create dataset.
- Upload multiple images.
- Upload/sampling video frames.
- Run Rapid Inference in Free mode.
- Run Rapid Inference in Text Prompt mode.
- Run Rapid Inference in Visual Prompt mode.
- Review paginated gallery overlays.
- Select all visible files and delete.
- Open modal review.
- Add manual bbox.
- Edit bbox through viewport-clamped popover.
- Delete detection.
- Accept/reject detections.
- Run Infer Next candidates.
- Export YOLO TXT zip.
- Export COCO JSON zip.

### SAM2.1

- Verify `/api/sam/status` reports enabled.
- Load SAM through `/api/sam/load` or first manual bbox save.
- Draw bbox and confirm mask is generated.
- Confirm bbox still saves if SAM is disabled or unavailable.

### Train Tune

- Create detection Dataset Version from live dataset.
- Create segmentation Dataset Version from masked dataset.
- Confirm missing-mask validation blocks incomplete segmentation snapshots.
- Generate policy preview samples.
- Apply recommended settings.
- Start Standard Mode job.
- Start High-Speed Mode job when GPUs are available.
- Cancel a job.
- Recompute failed job.
- Resume from `last.pt`.
- Open live job page.
- Open result page.
- Test registered Model Version.
- Delete unused Dataset Version.
- Delete Model Version and linked failed job where allowed.

## Hardware Validation

Record results for:

| Item | Expected |
|------|----------|
| `nvidia-smi` PCI order | Physical GPU IDs match project assumptions |
| `LABELLENS_CUDA_VISIBLE_DEVICES=1,2` | LabelLens does not use physical GPU `0` |
| YOLOE inference | Uses local `DEVICE=0` after visible mapping |
| SAM2.1 | Uses local `SAM_DEVICE=1` after visible mapping |
| Train Tune Standard | Uses physical GPU `1` |
| Train Tune High-Speed | Uses physical GPUs `1,2` with AMP off |

## Known Test Note

The backend training router mock runtime test can expose timing-sensitive behavior around background job metadata writes. If the full suite fails once in that area, rerun the specific failing test and then rerun the full suite before treating it as a documentation-change regression.
