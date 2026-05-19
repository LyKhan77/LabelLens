# Raster Mask Overlay Plan

## Summary
Render YOLOE segmentation masks like the Ultralytics demo: blend raster mask pixels instead of drawing extracted contour polygons.

## Key Changes
- Add compact cropped RLE mask payloads from `r.masks.data` for each detection.
- Keep polygon masks as fallback for compatibility.
- Draw `mask_rle` in the frontend canvas as a tinted raster alpha mask.
- Avoid polygon outlines when raster masks are available.
- Update docs to describe raster live mask overlay.

## Test Plan
- Compile backend Python files.
- Build frontend TypeScript/Vite.
- Verify synthetic mask RLE encoding returns compact payload.
- Run whitespace diff check.

## Assumptions
- This matches the Ultralytics rendering approach more closely. It improves display quality but does not change YOLOE's predicted segmentation.
