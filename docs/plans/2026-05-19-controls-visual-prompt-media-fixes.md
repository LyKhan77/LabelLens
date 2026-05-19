# Controls Visual Prompt And Media UX Fixes

## Summary

Fix Visual Prompt state loss when Controls is collapsed, align Media Input tab colors with Grounding Prompt, make the Start/Stop action reflect active inference state, prevent result media clipping after layout changes, and add thin X/Y guide lines while drawing visual prompt annotations.

## Key Changes

- Keep Sidebar panel contents mounted with `v-show` during collapse so Visual Prompt state is not destroyed.
- Restore Visual Prompt reference preview from `store.referImage` on remount as an additional guard.
- Match Media Input tab active/inactive classes to Grounding Prompt.
- Use an active inference computed state in SettingsPanel for Stop button display.
- Add `min-h-0`/`min-w-0` layout constraints around Viewer/App result areas.
- Draw thin horizontal and vertical cursor guides while annotating bounding boxes.

## Test Plan

- Run `npm run build` in `frontend/`.
- Manually verify Visual Prompt reference image and annotations remain after collapse/expand.
- Verify Media Input tab active color matches Grounding Prompt.
- Verify active inference shows Stop Inference.
- Verify result images/videos are not clipped after collapsing Controls.
- Verify X/Y guide lines appear while drawing annotation boxes.
