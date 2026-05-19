# Fix YOLOE Mask Scaling Plan

## Summary
Fix the current LabelLens mask overlay regression by scaling YOLOE masks with Ultralytics `ops.scale_masks()` instead of plain OpenCV resize.

## Key Changes
- Replace direct `cv2.resize()` mask scaling with `ops.scale_masks()` in `backend/services/model.py`.
- Preserve existing `mask_rle` and polygon fallback payloads.
- Keep frontend raster rendering unchanged.

## Test Plan
- Compile backend Python files.
- Build frontend TypeScript/Vite.
- Verify synthetic mask helper still returns expected shape and valid RLE.
- Run whitespace diff check.

## Assumptions
- The bad overlay came from letterbox/padding mismatch in mask scaling.
- `ops.scale_masks()` matches Ultralytics `Results.plot()` behavior for segmentation masks.
