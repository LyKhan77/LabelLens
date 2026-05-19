# Floating Inference Stats Plan

## Summary

Move compact Inference Stats out of the bottom MetricsBar into a floating right-side panel inside the Viewer. Keep Detection Log in the bottom MetricsBar.

## Key Changes

- Render `StatsGrid` from `Viewer.vue` as a compact floating panel on the right side when stats are available.
- Make `StatsGrid.vue` use a small 2-column layout suitable for a floating panel.
- Remove `StatsGrid` from `MetricsBar.vue`, leaving Detection Log as the bottom bar content.
- Update `README.md`, `AGENTS.md`, and `temp/html.txt` to reflect the new floating stats placement.

## Test Plan

- Run `npm run build` in `frontend/`.
- Manually verify Image, Video, and RTSP result states show stats in the right floating panel without blocking controls.
- Verify bottom MetricsBar only shows Detection Log.
