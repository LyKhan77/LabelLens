# YOLOE-26L, Live Mask Overlay, RTX 5080 Plan

## Summary
Upgrade LabelLens to `yoloe-26l-seg.pt`, add optional live mask overlay, and run inference on RTX 5080 GPU `0`.

`nvidia-smi` showed GPU `0` and `1` as NVIDIA GeForce RTX 5080 with about 16 GB VRAM and almost idle. GPU `2` is RTX 4090 but heavily used. Use `CUDA_DEVICE_ORDER=PCI_BUS_ID DEVICE=0`.

Sources:
- YOLOE docs: https://docs.ultralytics.com/models/yoloe
- YOLOE-26 benchmarks: https://docs.ultralytics.com/models/yolo26
- SAM 3 reference for future semantic upgrade: https://docs.ultralytics.com/models/sam-3

## Key Changes
- Change default model to `models/yoloe-26l-seg.pt`; keep `MODEL_PATH` override for rollback.
- Keep backend device default as `DEVICE=0`; set `CUDA_DEVICE_ORDER=PCI_BUS_ID` before Ultralytics/PyTorch import so `DEVICE=0` matches RTX 5080 index `0` from `nvidia-smi`.
- Parse segmentation masks from YOLOE results in `backend/services/model.py` using `r.masks.xy`.
- Extend each detection payload with optional polygon mask data while preserving `box`, `label`, `confidence`, and `cls_id`.
- Add `showMasks` state in Pinia, default `false`.
- Add `Show Masks` toggle in Settings.
- Implement live frontend canvas overlay in `Viewer.vue` so masks can be toggled without rerunning inference.
- For video, use detections from the current `videoIndex` so mask overlay follows the active frame.
- For RTSP, use latest WebSocket detections and redraw masks as frames update.
- Update `README.md` with YOLOE-26L default, RTX 5080 `DEVICE=0`, and mask overlay workflow.

## Public Interfaces
- REST image/video responses add optional `mask` per detection.
- WebSocket `detections` entries add optional `mask`.
- No breaking API changes.
- Environment:
  - `MODEL_PATH=models/yoloe-26l-seg.pt`
  - `CUDA_DEVICE_ORDER=PCI_BUS_ID`
  - `DEVICE=0`

## Test Plan
- Confirm `nvidia-smi` shows inference process on GPU `0`.
- Backend config check: default model path is `models/yoloe-26l-seg.pt`.
- Image text prompt: detections still return and mask polygons appear when available.
- Image visual prompt: SAVPE labels still remap correctly and masks align with objects.
- Toggle test: turn `Show Masks` on/off after inference without rerun.
- Video test: masks track current frame when scrubbing and playing.
- RTSP smoke test: masks redraw over live frames without breaking stream.
- Regression: labels, bboxes, confidence slider, detection log, and stats still work.

## Assumptions
- No extra external plans/discussions need validation.
- Mask display should be live-toggle, so mask geometry is returned with detections even when hidden.
- YOLOE-26L fits on one 16 GB RTX 5080; if not, rollback via `MODEL_PATH=models/yoloe-26s-seg.pt`.
- SAM 3 remains a later separate upgrade because it changes output semantics toward concept segmentation/tracking.
