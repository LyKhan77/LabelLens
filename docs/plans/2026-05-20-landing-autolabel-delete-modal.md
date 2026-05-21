# ModeSelect Landing + Auto-Label Workflow Stabilization

## Summary

Implement deterministic landing at `/` (ModeSelect), workspace entry via `/workspace`, dataset delete confirmation modal, removal of sidebar quick-save flicker, RTSP continuous auto-label from viewer frames with optional `MM:SS` timer, and overlay clamping in Dataset Review modal for narrow aspect ratios.

## Key Changes

- App routing in `frontend/src/app/App.vue`:
  - `/datasets` -> `DatasetsPage`
  - `/workspace` + `modelLoaded` -> `WorkspacePage`
  - all other paths -> `ModeSelectPage`
- `ModeSelectPage` now navigates to `/workspace` only after successful `selectMode`.
- `DatasetList` delete flow uses custom confirmation modal (no native `confirm()`).
- Workspace sidebar removes `QuickSave` UI (`Save to...`) and keeps auto-save trigger only from Auto-Label modal.
- Dataset store auto-label config now includes optional `autoLabelRtspTimerSeconds`.
- Inference store:
  - `stopInference()` disables auto-label.
  - RTSP auto-label saves live viewer frames continuously at configured sampling FPS.
  - Optional RTSP timer stops auto-label only (stream inference continues).
  - Video auto-label remains one-pass save-stream (no playback-loop duplication).
- Dataset review overlay clamping:
  - Clamp bbox + mask points into frame bounds.
  - Reposition label chips to prevent rendering outside frame.
  - Add tighter mobile clipping/padding behavior.

## Verification Plan

- Frontend sanity build: `cd frontend && npm run build`
- Backend dataset tests: `python3 -m unittest backend.tests.test_dataset_service`
- Manual checks:
  - root landing, mode select -> workspace navigation
  - delete dataset modal behavior
  - no sidebar quick-save control
  - image/video/rtsp auto-label behavior including timer and stop rules
  - dataset review overlay containment on narrow viewport
