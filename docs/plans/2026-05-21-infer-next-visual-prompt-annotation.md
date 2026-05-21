# Infer Next Visual Prompt Annotation Plan

## Summary
Add Infer Next in Dataset Review so a selected bbox on the current image can become a YOLOE Visual Prompt for the next image. Results are candidate annotations only until the user accepts and saves them.

## Implementation
- Add `POST /api/datasets/{name}/images/{source_img_id}/infer-next` to run `setup_visual_prompt()` on the source image and `predict_with_vpe()` on the target image.
- Return temporary candidates with `assisted: true` and `source: visual_prompt`; do not call `label_image()` or replace target detections.
- Preserve assisted metadata when accepted candidates are saved through detection CRUD.
- Add Dataset Review controls to load the prompt model, run Infer Next, hide duplicate candidates by IoU >= 0.7, accept/reject candidates, and save accepted candidates.
- Update README, AGENTS, and CLAUDE workflow docs.

## Verification
- Backend unit tests cover candidate-only infer-next behavior and assisted metadata persistence.
- Frontend production build verifies Vue/TypeScript integration.
- Actual YOLOE model behavior still needs end-to-end testing with `models/yoloe-26l-seg.pt`.
