# ReviewPage + Train Tune UI Improvements Plan

## Summary
Improve Train Tune list density/tooltips and Dataset Review annotation precision. Use backend-persisted per-dataset class colors so Rapid Inference/manual annotations stay visually consistent after reload and across browsers.

## Key Changes
- Train Tune:
  - Move Model Version delete action into each model card row, alongside compact status badge.
  - Make status badges in Model Versions and Training Jobs smaller.
  - Add hover-only info icons beside Training Configuration / Architecture and Versioning, Split, and Prep / Policy.
- Dataset Review:
  - Add wheel zoom only while cursor is inside the canvas.
  - Add compact zoom toolbar plus `+`, `-`, and `0` shortcuts while canvas is hovered/focused.
  - Add `Space + drag` panning when zoomed.
  - Clamp the Edit BBox popover to the visible stage so bottom-edge objects do not clip it.
- Class colors:
  - Store `class_colors` in dataset metadata.
  - Auto-assign distinct colors when classes are introduced.
  - Add API/store support to update one class color manually.
  - Use persisted class colors for ReviewPage boxes, masks, labels, and relevant dataset overlays.

## Test Plan
- Backend: `env/bin/python -m unittest backend.tests.test_dataset_service`
- Frontend: `cd frontend && npm run build`
- Manual QA: Train Tune density/tooltips, ReviewPage zoom/pan/popover, persisted manual class colors, and randomized Rapid Inference colors.

## Docs + Commit Requirements
- Update `README.md`, `AGENTS.md`, and `CLAUDE.md` for key workflow changes.
- Do not overwrite unrelated existing `AGENTS.md` changes.
- Commit functional chunks separately where feasible.
