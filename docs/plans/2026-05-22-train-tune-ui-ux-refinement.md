# Train Tune UI/UX Refinement Plan

## Summary
- Keep Train Tune backend interfaces unchanged while tightening builder, live progress, and result UX.
- Separate editable Dataset Version draft flow from immutable selected snapshot metadata.
- Add compact visual metric trends and keep exact epoch values available.

## Key Changes
- Fix long Dataset Version and job output path overflow in Result context panels.
- Add local SVG sparklines for mAP50, mAP50-95, precision, recall, train loss, and val loss on Live Progress and Result.
- Keep Live Progress epoch rows as a scrollable `Epoch History` table.
- Expose immutable Dataset Version source, split policy/counts, preprocessing, and augmentation in builder summary and Result.
- Replace flat builder inputs with a gated stepper: source, architecture/config, split/prep/augment, snapshot preview, create version.
- Move job creation into Training Preview as `Start Training Job`.
- Keep Dataset Version delete inside the version card with current confirmation and conflict feedback.

## Interfaces
- Reuse existing Dataset Version metadata: `split_config`, `split_counts`, `preprocessing_config`, and `augmentation_config`.
- Reuse existing job metric history and selected model to job linkage for metric trends.
- Do not change training API payloads or backend schema in this UI pass.

## Test Plan
- Frontend build/typecheck.
- Rendered smoke checks for builder stepper, selected immutable version summary, Live Progress trends/epoch scroll, and Result overflow/config panels.
- Confirm draft split/prep/augmentation edits do not mutate selected Dataset Version summary.
- Confirm Start Training Job remains disabled until a selected Dataset Version estimate exists.

## Assumptions
- Sparklines stay dependency-free and compact.
- Evaluation plus loss metrics are the chart scope; LR and ETA remain supporting metadata.
- Dataset Versions remain immutable after creation and changed policies require a new version.
