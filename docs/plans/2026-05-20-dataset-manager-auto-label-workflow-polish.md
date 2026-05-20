# Dataset Manager + Auto-Label Workflow Polish Plan

## Summary

Move Dataset Manager to a standalone `/datasets` page, polish the gallery/review UX into a Roboflow-like workflow, and make batch auto-labeling run fully inside Dataset Manager with Free, Text, and Visual Prompt support.

## Key Changes

- Remove the Datasets tab from `ModeSelectPage`; add lightweight App-level routing for `/` and `/datasets` without adding Vue Router.
- Add real dataset thumbnails through `image_url` in `GET /api/datasets/{name}/images`.
- Replace the compact side review panel with a large modal reviewer that shows bbox/label/mask overlays, class filters, object visibility, accept/reject, and keyboard next/prev.
- Replace the batch upload dialog with a wizard: Upload -> Configure -> Load Model -> Start Labeling -> Progress.
- Add backend polling jobs for dataset label work and guard model usage with a single job lock.
- Fix workspace auto-label so image saves immediately and video uses backend frame extraction from the original file at configured `sample_fps`, not looping frontend playback frames.
- Update README and AGENTS project-doc sections after implementation.

## Test Plan

- Backend service tests for dataset image metadata and unlabeled status.
- Frontend build with `npm run build`.
- Backend import/compile check with `python3 -m compileall backend`.
- Manual smoke checks through the local dev server when possible.

## Assumptions

- Use existing Vue + Pinia + Tailwind stack.
- Use polling for batch progress.
- Dataset Manager visual prompts are independent from workspace state.
- Mixed image and video uploads in one batch are rejected.
