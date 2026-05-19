# Floating Stats And Detection Log Plan

## Summary

Move Detection Log into the existing right-side floating Inference Stats panel. Separate stats and log with a divider, and constrain the log area with vertical scrolling so large detection lists do not stretch the viewer. Remove the bottom MetricsBar from the active layout.

## Key Changes

- Import and render `DetectionLog` inside `Viewer.vue` below `StatsGrid`.
- Make the floating panel wider and height-constrained with a scrollable log section.
- Update `DetectionLog.vue` spacing for compact floating-panel use.
- Remove `MetricsBar` from `App.vue` so the bottom bar no longer occupies space.
- Update docs and `temp/html.txt` preview to match the new right-side combined panel.

## Test Plan

- Run `npm run build` in `frontend/`.
- Verify image/video/RTSP result states show stats and log together on the right.
- Verify long detection lists scroll inside the panel instead of growing downward.
