# Train Tune Training Reliability Improvements

## Summary
- Keep Train Tune GPU target as physical RTX 5080 indexes `1` and `2` per `temp/nvidia-smi.txt`.
- Add Basic vs Advanced augmentation without removing any model family choices.
- Harden training jobs with backend validation, preflight checks, safer cancellation, resume support, opt-in DDP patching, logs, and restart recovery.

## Key Changes
- Add Basic and Advanced augmentation modes. Basic is online-only and Advanced preserves current materialized augmentation controls.
- Validate training config on the backend while keeping all YOLO11/YOLO26 family choices visible.
- Preflight job inputs before worker launch: checkpoint, dataset YAML, dataset split, output path, Ultralytics import, and RTX 5080 GPU policy metadata.
- Start workers in their own process group and cancel the full group.
- Add resume action from `last.pt` for failed/cancelled jobs.
- Make the DDP `find_unused_parameters=True` patch opt-in.
- Write per-job `train.log`, preserve `results.csv` path, and fail stale running jobs on backend startup.

## Tests
- Backend training service, router, and worker tests cover augmentation normalization, config validation, resume, DDP flag behavior, cancellation, and metadata.
- Frontend build verifies Basic/Advanced UI and API typing.

## Assumptions
- Physical GPU `1` and `2` remain reserved for Train Tune RTX 5080 training.
- Standard mode uses physical GPU `1`; High-Speed uses physical GPUs `1,2`.
- Model family choices stay as-is; missing weights fail through validation/preflight rather than being removed from UI.
