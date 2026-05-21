# Dataset Workspace Rapid Inference Polish Plan

## Summary
- Improve Dataset Workspace delete workflow: per-card delete, bulk selected delete, and delete from Image Review.
- Fix overlay placement by using one shared overlay renderer for thumbnails, Image Review, and Rapid Inference progress preview.
- Rename **Upload + Auto-Label** to **Rapid Inference** and show clearer per-image labeling progress.

## Key Changes
- Extend `GET /api/datasets/{name}/images` response with lightweight `detections_preview` for gallery overlays.
- Extend label job status with `items` log entries:
  `img_id`, `filename`, `image_url`, `state`, `detections_count`, optional `detections`, optional `error`.
- Add shared frontend overlay component for dataset media:
  - Uses image/annotation aspect ratio, not fixed card percentages.
  - Renders bbox/label/mask with same coordinate mapping in thumbnail, review modal, and progress preview.
  - Uses contained media plane so portrait/mobile-ratio images do not shift overlays outside the image.

## Implementation Changes
- Dataset gallery:
  - Replace dummy `.dataset-card-bbox` overlays with real detection overlays.
  - Add checkbox selection per image.
  - Add visible `Delete Selected (n)` action when selection exists.
  - Add per-card delete icon/button with confirmation modal.
- Image Review modal:
  - Add delete button in header/action area.
  - Confirm before delete.
  - After delete, navigate to next image if available, otherwise previous, otherwise close modal.
- Rapid Inference modal:
  - Rename button/title/step text from `Upload + Auto-Label` / `Auto-Label` to `Rapid Inference`.
  - Progress view shows global bar, current/last image preview with overlay, processed count, detection count, and scrollable per-image log.
  - Failed/skipped items show clear status without stopping display of completed items.
- Docs:
  - Update `README.md` Dataset Manager workflow and feature list.
  - Update `AGENTS.md` Key Features / Current State to mention Rapid Inference, real overlay previews, and image delete controls.
- Commit changes in logical commits:
  1. API/job progress data shape.
  2. Shared overlay renderer and gallery/review fixes.
  3. Rapid Inference progress UI and docs.

## Test Plan
- Backend:
  - Add/adjust `backend/tests/test_dataset_service.py` coverage for `detections_preview` in `list_images`.
  - Run `python -m unittest backend.tests.test_dataset_service`.
- Frontend:
  - Run `cd frontend && npm run build`.
  - Verify gallery overlays align on landscape and portrait images.
  - Verify bulk delete, per-card delete, and review-modal delete all refresh counts/pages correctly.
  - Verify Rapid Inference progress log updates per processed image and preview overlay aligns.
- Manual browser check:
  - Open `/datasets`.
  - Test with 16:9 video frames and portrait/mobile-ratio images.
  - Confirm overlay stays inside actual image in thumbnail, modal review, and progress preview.

## Assumptions
- Use existing delete image endpoint; no new bulk delete backend endpoint unless frontend sequential deletes become too slow.
- Gallery preview can include lightweight detections from page results; full review still uses `GET /images/{img_id}`.
- Confirmation modal is required for destructive image deletes, matching existing dataset delete style.
