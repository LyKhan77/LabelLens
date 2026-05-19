# Smooth Mask Overlay Plan

## Summary
Improve LabelLens mask overlay quality by cleaning YOLOE mask contours on the backend and drawing them as smoothed canvas curves on the frontend.

## Key Changes
- Derive detection `mask` polygons from `r.masks.data` when available, resized to the original image size.
- Apply light morphological close/open cleanup before extracting the largest external contour.
- Keep fallback to `r.masks.xy` for compatibility.
- Draw frontend polygons with quadratic curves instead of straight `lineTo` segments.
- Update README and AGENTS to mention smoothed live mask overlay.

## Test Plan
- Compile backend Python files.
- Build frontend with `npm run build`.
- Run a dummy YOLOE inference to confirm mask parsing path does not break detection output.
- Confirm git diff has no whitespace errors.

## Assumptions
- This improves overlay smoothness and contour cleanliness, but cannot correct model-level segmentation mistakes beyond the predicted YOLOE mask.
