# Train Tune Detection Fix and Versioning UX Plan

Date: 2026-05-22

## Summary

Fix Train Tune detection jobs that currently fail when the builder selects a segmentation checkpoint for bbox-only dataset versions. Add safe Dataset Version deletion and make the Versioning, Split, and Prep controls easier to understand before creating an immutable snapshot.

## Implementation Changes

- Keep Train Tune v1 detection-only for LabelLens bbox datasets.
- Default YOLO26 runs to detection checkpoints and reject non-detection checkpoints in the worker with a clear failure reason.
- Add `DELETE /api/training/dataset-versions/{version_id}` and block deletion while jobs or model versions reference the snapshot.
- Add frontend delete support for Dataset Versions and clear selected version state after a successful delete.
- Replace the flat versioning control grid with a visual split bar, grouped preprocessing and augmentation controls, and a snapshot preview.
- Update Train Tune docs in `README.md`, `AGENTS.md`, and `CLAUDE.md`.

## Test Plan

- Cover unused and referenced Dataset Version deletion in backend service and router tests.
- Cover worker checkpoint task validation before Ultralytics training starts.
- Verify the Train Tune backend test suite, frontend build, fake training flow, and a manual detection-checkpoint smoke path when weights are available.

## Assumptions

- Segmentation fine-tuning remains out of scope until Dataset Versions can carry segment labels.
- Dataset Version deletion does not cascade into job or model history.
- Versioning UX remains inside the current builder page instead of becoming a wizard.
