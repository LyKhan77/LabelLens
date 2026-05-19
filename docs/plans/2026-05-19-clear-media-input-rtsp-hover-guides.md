# Clear Media Input + RTSP Stop UX + Hover Guides Plan

## Summary

Add explicit Clear Media workflow so media mode changes only after current media input is cleared. Stop Inference only stops active work and keeps the current media input reusable. Visual Prompt alignment guides render on hover and drag.

## Key Changes

- Add store computed state for `hasMediaInput` and `canSwitchMediaMode`.
- Add `clearMediaInput()` and `selectMediaMode()` store actions.
- Keep RTSP URL after Stop Inference, but reset running/result state so Start is available again.
- Disable media mode tabs while inference is running or media input exists.
- Add Clear Media control and user hints in Media Input.
- Route Image/Video remove buttons through `clearMediaInput()`.
- Add hover X/Y guides in BBox annotation.

## Test Plan

- Run `npm run build` in `frontend/`.
- Manually test RTSP Start/Stop/Start, Clear Media, mode switching lock, Image/Video clear, and hover/drag annotation guides.
