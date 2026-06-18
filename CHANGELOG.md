# LabelLens Changelog

This file is the long-term memory ledger for LabelLens across all AI agents. It records what the codebase can do now, why important changes were made, where the related code lives, what still needs validation, and how future agents must document their work.

Use this file as the durable context bridge between sessions. Chat history can disappear, but this file should let the next agent understand the current product state and continue work without rediscovering old decisions.

## Agent Memory Contract

Every AI agent must treat this file as the source of truth for implemented codebase history.

Read order for a new agent:

1. Read `AGENTS.md` for operating rules.
2. Read this file's `Current Codebase State` for the latest product capability map.
3. Read the newest entries in `AI-Agent Change Entries` before touching related areas.
4. Check `Long-Term Decision Log` before reversing or refactoring previous choices.
5. Check `Pending Validation and Known Gaps` before claiming a workflow is fully verified.

Update rules:

- Update this file for every implemented behavior, architecture, model/CV stack, workflow, or major developer-documentation change.
- Add new entries at the top of `AI-Agent Change Entries`, newest first.
- Keep historical entries unless they are factually wrong; correct them with a new entry when possible.
- Update `Current Codebase State` when a change affects the product capability map.
- Update `Long-Term Decision Log` when a change creates a decision future agents must preserve or understand.
- Update `Pending Validation and Known Gaps` when verification status changes.
- Do not record plans, ideas, or proposed work as completed changes.
- Do not duplicate this changelog back into `AGENTS.md`; keep `AGENTS.md` as a pointer.

## Required Entry Schema

Use this structure for every new AI-agent change entry:

```markdown
### YYYY-MM-DD - Short change title

**Agent scope**

- Request: one sentence describing the user request.
- Intent: one sentence describing why the change exists.
- Status: Completed | Partially completed | Reverted | Superseded.

**Changed files**

- `path/to/file`: what changed in this file.

**Behavior before**

- Describe the previous behavior or documentation state.

**What changed**

- Concrete implemented changes only.

**After the change**

- Describe how the app, workflow, architecture, or agent memory behaves now.

**Verification**

- Commands run, tests run, manual checks, or "Not run" with reason.

**Follow-up notes**

- Remaining validation, risks, or related areas future agents should inspect.
```

## Current Codebase State

This table is the high-level capability map. Keep it concise but current. Detailed implementation notes belong in dated entries below.

| Area | Timeline (git) | What was developed | After the change |
| ------ | ---------------- | -------------------- | ------------------ |
| Feature Modes and Routing | 2026-05-19 - 2026-06-18 | Added deterministic `/` mode selection for Free Inference, Prompt Inference, Train Tune, and a Test Model entry (`/test`) with a master-detail model-version picker. | Users start from a mode selector, inference model loading is deferred until workspace entry, `/datasets` plus `/train-tune` remain independently reachable, and trained models can be picked and tested directly from the landing page. |
| Inference Workspaces | 2026-05-19 - 2026-06-17 | Implemented Free Mode, Text Prompt, Visual Prompt, image inference, video processing, and RTSP WebSocket streaming through the backend model service, plus task-matched result parsing/rendering for bbox, masks, pose keypoint skeletons, and classification top-1/Top-5. | Backend exposes `predict_free()`, `predict_text()`, and `predict_visual()` paths, the frontend runs image/video/live-stream detection flows, and output is rendered per task type across inference workspaces and the Test Model page. |
| Dataset Manager and Auto-Labelling | 2026-05-20 - 2026-06-17 | Built standalone dataset management, gallery review, bbox editing, class controls, auto-save from inference, YOLO/COCO/classification/pose export, task-aware Rapid Inference flows, and Auto-Crop Objects. Auto-Crop supports detect/segment to raw HD crops into a target or new dataset for classification annotation, during inference and as an Upload Data crop job with pre-trained or trained model source. | Datasets can be created, reviewed, corrected, propagated with prompt-assisted inference, cropped per object for defect classification, and exported for downstream training workflows. |
| Pose Annotation | 2026-06-05 - 2026-06-08 | Added Ultralytics-style pose editing with keypoint templates, visibility cycling, bbox/keypoint drag behavior, pan/zoom, and pose infer assist. | Pose datasets can be reviewed and corrected directly in the Dataset Manager with task-specific controls. |
| SAM2.1 Auto-mask | 2026-05-22 | Added backend `SAMService`, status/load/unload endpoints, dataset-scoped mask generation, and frontend auto-mask trigger from manual bbox save. | Manual bbox annotations can optionally receive generated segmentation masks, while bbox saves remain non-fatal if SAM is unavailable. |
| Train Tune Workspace | 2026-05-22 - 2026-06-18 | Implemented task-selectable training builder, immutable Dataset Version snapshots with persisted training architecture config, Roboflow-style Train/Valid/Test split controls in Policy, preprocessing policy, augmentation controls, training preflight with base-checkpoint auto-download and multi-GPU AutoBatch handling, job queueing, task-aware live metrics, explicit missing-checkpoint diagnostics, result pages, resume/recompute/delete, artifact testing, and model registry. | Detection, segmentation, pose, and single-label classification jobs can be configured, split with a combined slider before snapshot creation, relaunched from Dataset Versions with their saved YOLO family/size/checkpoint/settings, monitored with task-matched metrics, failed clearly when Ultralytics saves no checkpoint, resumed, tested, and tracked as reusable model versions. |
| GPU Settings | 2026-06-01 - 2026-06-02 | Added CUDA GPU auto-detection, inference GPU assignment, SAM GPU assignment, Train Tune Standard/High-Speed GPU selection, and persisted GPU config files. | Runtime GPU mapping can be managed from UI/config instead of relying only on environment defaults. |
| Backend Runtime and Tests | 2026-05-19 - 2026-06-17 | Added dataset, Train Tune service/runtime, model parsing, drawing, task-aware training metric parsing, and missing-checkpoint failure unit coverage around implemented backend workflows. | Core dataset, training orchestration, Train Tune worker metrics/checkpoint handling, and inference parsing behavior has automated coverage, with full target-hardware validation still pending. |

## Long-Term Decision Log

Record decisions here when future agents need the context before changing behavior.

| Date | Area | Decision | Reason | Preserve until |
| ------ | ------ | ---------- | -------- | --------------- |
| 2026-06-18 | Agent memory | Keep detailed implemented change history in `CHANGELOG.md`, with `AGENTS.md` pointing to it instead of duplicating the content. | `AGENTS.md` should remain an instruction file, while `CHANGELOG.md` acts as durable cross-agent memory. | Superseded by an explicit user-approved memory system change. |
| 2026-06-18 | Train Tune | Dataset split policy is represented as a combined Train/Valid/Test slider before Dataset Version snapshot creation. | The split must be locked into immutable training snapshots and visible in training summaries. | Superseded by a new training dataset policy. |
| 2026-06-17 | Dataset workflow | Auto-Crop Objects saves raw HD object crops into target datasets for classification review instead of annotated crops. | Defect-classification workflows need clean crops for OK/NG annotation and classifier training. | Superseded by a new crop dataset contract. |

## Pending Validation and Known Gaps

Track known gaps here so future agents do not overstate verification.

| Date noted | Area | Gap | Next validation |
| ---------- | ---- | --- | --------------- |
| 2026-06-18 | Backend Runtime and Tests | Full target-hardware validation is still pending for GPU-heavy inference, SAM, RTSP, and Train Tune workflows. | Run end-to-end validation on the intended CUDA workstation with representative image, video, RTSP, dataset export, SAM mask, and training jobs. |
| 2026-06-18 | Documentation | `CHANGELOG.md` now stores long-term agent memory, but future entries depend on agent discipline. | Each future agent should update this file before finishing work that changes behavior or architecture. |

## AI-Agent Change Entries

### 2026-06-18 - Long-term agent memory format

**Agent scope**

- Request: Make `CHANGELOG.md` useful as long-term memory across all AI agents.
- Intent: Turn the file from a simple changelog into a durable state ledger that future agents can read before continuing work.
- Status: Completed.

**Changed files**

- `CHANGELOG.md`: added agent memory contract, required entry schema, current-state guidance, long-term decision log, pending validation table, and this detailed entry.
- `AGENTS.md`: clarified that `CHANGELOG.md` is the long-term cross-agent memory file.
- `CLAUDE.md`: synced the pointer text with the updated `AGENTS.md` meaning.

**Behavior before**

- `CHANGELOG.md` existed as a separated changelog with current codebase state and dated entries.
- It did not yet define a stable long-term memory contract, required entry schema, decision log, or validation-gap tracking.

**What changed**

- Added a new `Agent Memory Contract` section explaining read order and update rules for future agents.
- Added a `Required Entry Schema` template to make future AI-agent entries consistent.
- Kept `Current Codebase State` as the compact capability map.
- Added `Long-Term Decision Log` for decisions future agents should not casually reverse.
- Added `Pending Validation and Known Gaps` so future agents can distinguish implemented work from fully validated work.

**After the change**

- Future agents can use `CHANGELOG.md` as durable memory across sessions.
- New work should be documented as structured entries, not scattered notes.
- Product state, decisions, and validation gaps are separated so the file can scale over time.

**Verification**

- Documentation-only change.
- Verified by reviewing the edited Markdown sections and repository diff.

**Follow-up notes**

- For future code changes, update this file in the same change set.
- If `Current Codebase State` grows too large, keep it as a compact index and move details into dated entries.

### 2026-06-18 - Changelog split from AGENTS.md

**Changed files**

- `CHANGELOG.md`
- `AGENTS.md`
- `CLAUDE.md`

**What changed**

- Created this dedicated `CHANGELOG.md` file.
- Moved the implemented codebase state table out of `AGENTS.md`.
- Replaced the long `AGENTS.md` Current State table with an explicit pointer to `CHANGELOG.md`.
- Added `CHANGELOG.md` to the documented project structure.
- Synced `CLAUDE.md` so it continues to point agents back to `AGENTS.md` and records this synchronization.

**After the change**

- AI agents have one dedicated file for detailed codebase change history.
- `AGENTS.md` stays shorter and remains focused on project instructions, high-level overview, and agent behavior.
- Future implemented behavior changes should update `CHANGELOG.md`; `AGENTS.md` should only be updated when project instructions, high-level overview, references, feature list, or structure pointer changes.

### 2026-05-19 - 2026-06-18 - Feature Modes and Routing

**What changed**

- Added a deterministic landing page at `/`.
- Added mode selection for Free Inference, Prompt Inference, Train Tune, and Test Model.
- Added `/test` as a trained-model entry point with a master-detail model-version picker.
- Deferred inference model loading until the selected workspace is entered.
- Kept `/datasets` and `/train-tune` independently reachable.

**After the change**

- Users start from an explicit mode selector instead of landing directly in a workspace.
- Trained models can be selected and tested from a dedicated gallery.
- Workspace routing is clearer and does not force eager model loading on the initial page.

### 2026-05-19 - 2026-06-17 - Inference Workspaces

**What changed**

- Implemented Free Mode inference using YOLOE LRPC internal vocabulary.
- Implemented Text Prompt inference through `set_classes` style prompt labels.
- Implemented Visual Prompt inference using reference image bbox annotations and SAVPE-style visual grounding.
- Added static image inference, video processing, and RTSP WebSocket streaming flows.
- Added task-aware result parsing and rendering for detection boxes, segmentation masks, pose skeletons, and classification predictions.
- Reused task-matched rendering in inference workspaces and the Test Model page.

**After the change**

- Backend inference paths support `predict_free()`, `predict_text()`, and `predict_visual()`.
- Users can run image, video, and live RTSP inference from the frontend.
- Detection, segmentation, pose, and classification outputs render with controls relevant to the active task type.

### 2026-05-20 - 2026-06-17 - Dataset Manager and Auto-Labelling

**What changed**

- Built a standalone `/datasets` page for dataset management.
- Added dataset creation, review, thumbnail gallery, modal review navigation, and paginated gallery behavior.
- Added bbox annotation review and editing, class controls, per-dataset colors, class rename/merge, class delete, image delete, and manual annotation editing.
- Added inference-assisted review flows including prompt-assisted propagation and Rapid Inference jobs.
- Added export workflows for YOLO TXT, COCO JSON, classification, and pose datasets.
- Added Auto-Labelling from inference workspaces and batch upload flows.
- Added Auto-Crop Objects for detection/segmentation workflows, saving raw full-resolution object crops into target datasets for classification/defect review.
- Added upload-dialog crop jobs through `POST /datasets/{name}/crop-jobs` with pre-trained YOLOE or trained registry model sources.

**After the change**

- Datasets can be created, inspected, corrected, inferred, cropped, and exported from one UI.
- Inference results can become labelled datasets.
- Object crops can feed a classification workflow without keeping annotated source images in the target crop dataset.

### 2026-06-05 - 2026-06-08 - Pose Annotation

**What changed**

- Added task-specific pose annotation editing.
- Added keypoint templates including COCO Person 17 and Box Corners.
- Added drag behavior for keypoints, bounding boxes, and full-instance movement.
- Added click-to-cycle keypoint visibility.
- Added pose canvas pan/zoom behavior and list-to-canvas keypoint hover/select synchronization.
- Added Pose Infer Assist for per-image model-assisted skeleton candidates.

**After the change**

- Pose datasets can be reviewed and corrected directly in Dataset Manager.
- Operators can edit skeletons, visibility, and bounding boxes with task-specific controls instead of generic bbox-only tools.

### 2026-05-22 - SAM2.1 Auto-mask

**What changed**

- Added backend `SAMService`.
- Added SAM status, load, and unload endpoints.
- Added dataset-scoped mask generation from manual bbox annotations.
- Added frontend trigger to request masks when manual bbox annotations are saved.
- Kept mask generation non-fatal when SAM is unavailable.

**After the change**

- Manual bbox annotations can optionally receive generated segmentation masks.
- Bbox annotation remains usable even if SAM loading or inference fails.
- YOLOE and SAM can be assigned to separate GPUs through runtime configuration.

### 2026-05-22 - 2026-06-18 - Train Tune Workspace

**What changed**

- Built dedicated `/train-tune` workflows for detection, segmentation, pose, and single-label classification.
- Added immutable Dataset Version snapshots.
- Persisted per-version training architecture configuration.
- Added Roboflow-style combined Train/Valid/Test split slider in Policy before snapshot creation.
- Added preprocessing policy and resize strategy support: Keep, Letterbox, and Stretch.
- Added basic online augmentation and advanced materialized augmentation steps.
- Added task-aware export handling for bbox, polygon masks, keypoints, and class-folder labels.
- Added missing-mask validation with Dataset Workspace handoff.
- Added recommended training settings by dataset size.
- Added Auto Batch support with `batch=-1`.
- Added early-stopping patience configuration.
- Added backend policy preview samples with task-aware overlays.
- Added training config validation/preflight.
- Added base-checkpoint auto-download and multi-GPU AutoBatch handling.
- Added Standard and High-Speed GPU mode selection.
- Added live job pages, result pages, artifact testing pages, job badges, metric trends, epoch history, and model version registry.
- Added cancellation, failed-job recompute/delete, and last-checkpoint resume.
- Added explicit missing-checkpoint diagnostics when Ultralytics completes without `best.pt` or `last.pt`.

**After the change**

- Users can configure and launch task-specific YOLO training jobs from dataset snapshots.
- Dataset split, preprocessing, augmentation, architecture, compute, and training settings are preserved with the dataset version/job.
- Jobs expose live progress, task-aware metrics, artifacts, resumability, failure diagnostics, and reusable model versions.

### 2026-06-01 - 2026-06-02 - GPU Settings

**What changed**

- Added CUDA GPU auto-detection through `torch.cuda`.
- Added inference GPU assignment controls.
- Added SAM GPU assignment controls.
- Added Train Tune Standard and High-Speed GPU selection.
- Added persisted inference GPU config via `gpu_config.json`.
- Added persisted training GPU config via `training_gpu_config.json`.
- Added startup config loading with environment-variable fallback.

**After the change**

- Runtime GPU assignment can be controlled through UI/config.
- YOLOE, SAM, and Train Tune workloads no longer rely only on hard-coded or environment-default GPU placement.

### 2026-05-19 - 2026-06-17 - Backend Runtime and Tests

**What changed**

- Added dataset service/runtime behavior around dataset storage, annotations, exports, and inference-assisted updates.
- Added Train Tune service/runtime orchestration.
- Added training worker metric parsing and checkpoint handling.
- Added model output parsing utilities.
- Added backend drawing utilities for task-aware rendering.
- Added missing-checkpoint failure unit coverage.
- Added task-aware training metric parsing coverage.

**After the change**

- Core dataset workflows, training orchestration, worker checkpoint behavior, and inference parsing have automated coverage.
- Full target-hardware validation remains a separate manual/operations concern.
