# Project Overview

## Project Synopsis

**LabelLens** is a web-based object detection and dataset iteration application powered by **YOLOE-26L** for inference, with a dedicated **Train Tune** workspace for YOLO fine-tuning orchestration. It provides a visual interface for real-time and batch inference, dataset review/export, and immutable training job workflows using live dataset snapshots or exported zips. The architecture separates compute-heavy CV workloads (FastAPI + PyTorch) from the presentation layer (Vue 3 SPA), communicating via REST API and WebSockets.

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Key Features - ALWAYS Update this section based on Changes or Features Made

- **Feature Modes Page** — Deterministic landing page at `/` with mode selection: Free Inference (LRPC, 1200+ LVIS categories), Prompt Inference (text/visual), or Train Tune, then navigates to the matching workspace
- **Train Tune Workspace** — dedicated `/train-tune` YOLO detection/segmentation builder with task-selectable immutable Dataset Version snapshots, bbox or polygon-mask label export, missing-mask validation with Dataset Workspace handoff, Roboflow-like preprocessing Policy with Keep/Letterbox/Stretch resize strategies, optional Add Augmentation Step modal workflow, train-only hybrid augmentation with 1x-5x Maximum Version Size, real backend policy preview samples with bbox/mask overlays, locked split/prep/augmentation summary, modal deletion for unused dataset versions and model versions with linked job history, compact model/job badges, checkpoint task validation, JSON-safe metric history with non-blocking job navigation, compact metric trends plus scrollable epoch history and dataset/run configuration details on live progress and model result views, dedicated `/train-tune/jobs/:id` live progress pages, dedicated `/train-tune/results/:id` result pages, dedicated `/train-tune/test/:id` model testing, Standard vs High-Speed GPU modes with RTX 5080 physical GPU mapping (`device=1` or `1,2` for Ultralytics, AMP off for High-Speed DDP), failed-job re-compute/delete actions, output artifacts under `traintune-workspace/`, and model version registry. LabelLens globally defaults to physical GPUs `1,2` so physical GPU `0` (RTX 4090) remains reserved for vLLM.
- **Free Inference Mode** — Prompt-free detection using YOLOE LRPC internal vocabulary (separate `yoloe-26l-seg-pf.pt` weights, no user prompts needed)
- **Dual Prompt Modes** — Text prompt (comma-separated labels via `set_classes`) and Visual Prompt (reference image + bbox annotations via SAVPE encoder)
- **Multi-Media Input** — Static image upload (JPG/PNG), video processing (MP4/AVI/MOV), and RTSP live streaming
- **Canvas BBox Annotation** — Interactive drawing tool with thin hover/drag X/Y guide lines for annotating reference images as visual grounding input
- **Configurable Inference** — Confidence threshold slider plus backend-rendered label/bbox visibility and clipped mask overlay toggles
- **Detection Dashboard** — Floating right-side inference panel with compact stats and scrollable detection log
- **Clear Media Workflow** — Media mode switching is locked until inference is stopped and current media input is cleared
- **Network-Accessible** — Hosts on `0.0.0.0:3131`, accessible from any device on the local network
- **Auto-Labelling** — Save inference results as labeled datasets for YOLO fine-tuning. Trigger from Workspace Auto-Label modal or batch upload via Dataset Manager. While active on RTSP, continuous viewer-frame annotations are saved until auto-label is stopped (modal, optional MM:SS timer, or Stop Inference). Accept/reject detections, add/edit/delete manual bboxes, and use per-class/per-object overlay controls. Export in YOLO TXT + COCO JSON formats with train/val split, preserving original input filenames in exported artifacts whenever available.
- **Dataset Manager** — Standalone `/datasets` page for multi-project dataset management with Inference-style header navigation, delete confirmation modals, Select All Files gallery selection, real overlay paginated thumbnail gallery (25/page), centered modal review with cross-page Prev/Next, compact class/status review controls, zoomable/pannable review canvas for pixel-level bbox editing, viewport-clamped Edit BBox popover, per-dataset manual class colors, manual bbox add/edit/delete annotation editor, simplified multi-prompt Infer Next visual-prompt candidate propagation with per-candidate Accept/Reject plus Accept All & Continue, direct annotation delete, granular overlay controls and image delete, Rapid Inference jobs with frame-by-frame `Frame x/y` progress, configurable frame sampling, and zip export.
- **SAM2.1 Auto-mask** — SAM2.1 (Hiera Large) runs on GPU 1 independently from YOLOE on GPU 0. Automatically generates mask segmentation when users draw manual bbox annotations in Dataset Manager review. Lazy-loaded, thread-safe, with status/load/unload API endpoints. Non-fatal — bbox saves without mask if SAM unavailable.

## Project Structure - ALWAYS Update this section based on Changes or Features Made

```
LabelLens/
├── frontend/src/
│   ├── shared/
│   │   ├── api/             (client.ts, detection.ts, ws.ts, dataset.ts, training.ts, sam.ts)
│   │   ├── composables/     (useBackendStatus.ts, useWebSocket.ts)
│   │   ├── stores/          (inference.ts, dataset.ts, training.ts — Pinia)
│   │   └── types/           (index.ts)
│   └── pages/
│       ├── mode-select/     (ModeSelectPage.vue — inference mode selection)
│       ├── datasets/        (DatasetsPage, DatasetList, DatasetDetail, ReviewPanel,
│       │                    EditableAnnotationOverlay, ExportDialog, BatchUploadDialog)
│       ├── train-tune/      (TrainTunePage — builder/live/result routes, TestModelPage — artifact testing)
│       └── workspace/       (components, sections)
├── backend/
│   ├── routers/         (health.py, detection.py, stream.py, dataset.py, training.py, sam.py)
│   ├── services/        (model.py, video.py, rtsp.py, dataset.py, activity.py, training.py,
│   │                    training_events.py, training_runtime.py, sam.py)
│   ├── train_worker.py  (background training worker process for Train Tune jobs)
│   └── utils/           (drawing.py, encoding.py, masks.py, postprocess.py)
├── datasets/            (runtime dataset storage, gitignored)
├── docs/plans/          (saved implementation plans)
├── docs/superpowers/specs/ (design specs)
├── temp/                (runtime/debug snapshots)
├── PRD.md, DESIGN.md, AGENTS.md, README.md
```

## Current State - ALWAYS Update this section based on Changes or Features Made

**Condition:** In active development. All three inference phases (Image, Video, RTSP) remain scaffolded and integrated. Core backend model service supports `predict_text()`, `predict_visual()` (SAVPE), and `predict_free()` (LRPC prompt-free mode). Model loading is deferred — users always land on `/` (Feature Modes), navigate to `/workspace` after inference model load, while Dataset Manager remains independently available at `/datasets` and Train Tune is independently available at `/train-tune`. Frontend UI components are built with DESIGN.md Supabase-inspired tokens. BBox annotation canvas tool with hover/drag X/Y guides, floating compact inference panel, scrollable detection log, backend-rendered clipped mask overlay, state-preserving collapsible Controls panel, explicit Clear Media mode switching, paginated real-overlay thumbnail dataset gallery with Select All Files, Dataset Manager delete confirmation modals, centered modal review with compact class/status controls, zoom/pan review canvas, viewport-clamped bbox editor popover, persisted per-dataset class colors, image delete, manual bbox add/edit/delete, simplified multi-prompt Infer Next visual-prompt candidate auto-save review, direct saved-label delete, cross-page Prev/Next, Rapid Inference job polling with frame-by-frame progress, workspace RTSP auto-label continuous save with optional timer, and Train Tune detection/segmentation task selection / Roboflow-like Policy with resize strategies, optional augmentation step modals, train-only hybrid augmentation, and preview samples / locked Dataset Version summary / compact metric trends / checkpoint task validation / scrollable epoch history / result metadata / queue / model registry / Test Model route are functional.

``` 
In THIS (**Being Developed**) section, always double-check features or items that have been completed. Make sure the features are working and set them aside or remove them from the list. 
```

**Being Developed:**

- SAM2.1 Auto-mask: Backend (SAMService on GPU 1, lazy load, thread-safe) + Frontend (auto-mask on manual bbox save in ReviewPage) + API endpoints (status/load/unload, dataset-scoped mask generation) implemented — needs `models/sam2.1_l.pt` placement and end-to-end testing with SAM2.1 weights on GPU 1 (RTX 5080)
- Train Tune / Custom Model Reuse: detection vs segmentation task selection, bbox/polygon Dataset Version export, missing-mask validation, Roboflow-like Policy sections, Keep/Letterbox/Stretch resize strategies, optional augmentation step modals, train-only hybrid augmentation with 1x-5x Maximum Version Size, real policy preview samples with bbox/mask overlays, locked Dataset Version preview, modal Dataset Version/Model Version deletion, compact model/job cards, checkpoint task validation, queueing, Standard vs High-Speed RTX 5080 GPU policy, live websocket progress, compact metric trends, dataset/run configuration detail panels, scrollable epoch history, model registry, and `/train-tune/test/:id` artifact testing are implemented — needs end-to-end validation with real detection and segmentation checkpoints
- Auto-Labelling / Rapid Inference: Standalone Dataset Manager page, project overview/delete controls, image bulk/card/review delete controls, Select All Files, real overlay paginated thumbnail gallery, centered modal review with cross-page navigation, compact class/status controls, zoomable/pannable canvas, viewport-clamped bbox editor, persisted manual class colors, manual bbox add/edit/delete, simplified multi-prompt Infer Next visual-prompt candidates with per-candidate Accept/Reject plus Accept All & Continue, direct saved-label delete, batch label jobs with frame-by-frame progress, inline Free/Text/Visual prompt wizard, and workspace image/video/RTSP auto-save hook implemented — needs end-to-end testing with actual model weights
- Free Mode Inference: Backend + Frontend complete — needs `models/yoloe-26l-seg-pf.pt` placement and testing
- Phase 1 (Image Detection): Backend + Frontend complete — needs end-to-end testing with actual YOLOE model weights
- Phase 2 (Video Processing): Backend + Frontend complete — needs testing with sample videos
- Phase 3 (RTSP Streaming): Backend WebSocket + Frontend integration complete — needs testing with live RTSP feeds
- Overall: Awaiting `models/yoloe-26l-seg.pt` and `models/yoloe-26l-seg-pf.pt` placement plus real YOLO detection/segmentation training checkpoints / hardware validation on RTX 5080 devices. LabelLens defaults to `CUDA_VISIBLE_DEVICES=1,2` so RTX 4090 physical GPU `0` is reserved for vLLM. Train Tune defaults to physical GPU `1` for Standard Mode and physical GPUs `1,2` for High-Speed Mode, passed directly to Ultralytics with `CUDA_DEVICE_ORDER=PCI_BUS_ID`; High-Speed DDP defaults AMP off.


=====================

# IMPORTANT — DO NOT EDIT BELOW

This section contains critical agent behavior guidelines. Any changes require explicit user approval.

## Important Notes - Project RULES

- Always use relevant skills to help with tasks.
- Always ask the user if there are any plans or discussions that need to be validated.
- Always provide a summary after finishing a task.
- Make sure the virtual environment or dependencies used for the backend are located in `@env/`.
- Always update `README.md` whenever there are changes to key features and the app's workflow.
- Commit every function change so you can roll back and view the code history in case of a malfunction or a failed change.
- Do not re-read files that have already been read in this session unless necessary.
- Minimize non-essential tool calls.
- Save every plan or specification to the `docs/plans/` folder so you can track which plans have been created or are currently being created. This allows you to resume the session if the AI agent's token expires. USE `Superpowers` skill to provide the plan.
- Be sure to update `@CLAUDE.md` as well if you have updated `@AGENTS.md`, and vice versa. 

===========================

# AGENTS.md — DO NOT EDIT BELOW

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
