
# Train Tune Workspace Implementation Notes

Date: 2026-05-22

## Summary

Implemented the first Train Tune release for LabelLens:
- new `/train-tune` workspace in the frontend
- immutable dataset version snapshots from live datasets or exported zips
- training estimate flow
- queued single-job backend runtime
- Standard vs High-Speed GPU policy with inference guard
- live websocket events, metrics history, and model version registry

## Notes

- High-Speed Mode blocks new inference while active and requires inference to be idle before the job starts.
- Dataset exports now preserve original input filenames in output artifacts when that metadata is available.
- Custom trained models are registered, but not yet wired into the existing `/workspace` inference experience.
- Train Tune supports real training via the worker process and also supports mock progress with `LABELLENS_TRAIN_TUNE_FAKE=1` for dry runs.
