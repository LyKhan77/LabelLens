# Dataset Annotation Editor Plan

**Summary**
Build a manual bbox annotation editor inside Dataset Review so missed objects can be added without deleting the image. Scope is **bbox add/edit/delete**, with existing/custom labels. Mask editing is out of scope for v1; model-generated masks remain viewable/exportable where supported.

**Implementation Changes**
- Save this plan as `docs/plans/2026-05-21-dataset-annotation-editor.md` before coding.
- Backend:
  - Add detection CRUD methods to `DatasetService`:
    - create manual detection with `id = max(existing ids) + 1`, `accepted: true`, `manual: true`, `confidence: 1.0`.
    - update label and/or bbox for an existing detection.
    - delete a detection by id.
  - Add API endpoints:
    - `POST /datasets/{name}/images/{img_id}/detections`
    - `PATCH /datasets/{name}/images/{img_id}/detections/{det_id}`
    - `DELETE /datasets/{name}/images/{img_id}/detections/{det_id}`
  - Validate labels as non-empty trimmed strings.
  - Validate bbox as four finite pixel coordinates, clamped to image bounds, with positive width/height.
  - Update `class_to_id` when a new custom label is added; do not remove old class ids when labels are renamed/deleted, to keep export class ids stable.
  - When bbox geometry changes, drop `mask` and `mask_rle` for that detection because the segmentation no longer matches.
- Frontend:
  - Extend dataset API/types with `manual?: boolean` and add/create/update/delete detection calls.
  - Extend Pinia dataset store with `addDetection`, `updateDetection`, and `deleteDetection`; refresh selected image, gallery page, and projects after successful mutation.
  - Add an editable review overlay component for `ReviewPanel.vue`:
    - Add BBox mode: drag on image plane to create a rectangle.
    - Select detection by clicking bbox or detection row.
    - Edit selected detection label via existing class dropdown plus custom text input.
    - Edit bbox by drag/move/resize handles and numeric fields.
    - Save/Cancel controls for draft edits.
    - Delete selected annotation with confirmation.
  - Keep existing Accept/Reject behavior unchanged.
  - Manual detections show as `Manual` in the row instead of misleading `100%`.
  - Manual bbox annotations have no mask; existing model masks remain visible until their bbox is edited.
- Docs:
  - Update `README.md` workflow/features for manual annotation editor.
  - Update `AGENTS.md` feature/current-state sections, and mirror the same relevant changes in `CLAUDE.md`.

**Public Interfaces / Types**
- `DetectionAnnotation` and `DatasetOverlayDetection` gain optional `manual?: boolean`.
- New request shape for add/update:
  - `label: string`
  - `box: [number, number, number, number]`
  - optional `accepted?: boolean` for create defaults to `true`.
- Export behavior remains unchanged:
  - rejected detections excluded.
  - YOLO exports bbox only.
  - COCO exports polygon segmentation only when `mask` exists.

**Test Plan**
- Backend `unittest`:
  - Add manual annotation to an unlabeled image; verify `manual`, `accepted`, `cls_id`, stats, and `class_to_id`.
  - Add custom label; verify class id is persisted.
  - Update bbox on masked detection; verify mask fields are removed.
  - Update label only; verify bbox remains and class map updates.
  - Delete detection; verify it disappears and export excludes it.
  - Reject detection then export; verify rejected label is not included.
- Frontend:
  - Run `npm run build` in `frontend`.
  - Manual QA in `/datasets`: add missed bbox, edit bbox/label, reject/accept, delete annotation, export YOLO and COCO.
  - Check desktop and mobile review modal layout for no text/control overlap.

**Assumptions**
- No external prior plan needs validation.
- v1 editor is bbox-only; mask drawing/editing is deferred.
- Existing/custom labels are allowed, with custom labels updating dataset class mapping.
- Deleting an annotation means removing it from stored JSON, while Reject remains the safer reversible review action.
