# Project Overview

## Project Synopsis

**LabelLens** is a web-based object detection and dataset iteration application powered by **YOLOE-26L** for inference, with a dedicated **Train Tune** workspace for YOLO fine-tuning orchestration. It provides a visual interface for real-time and batch inference, dataset review/export, and immutable training job workflows using live dataset snapshots or exported zips. The architecture separates compute-heavy CV workloads (FastAPI + PyTorch) from the presentation layer (Vue 3 SPA), communicating via REST API and WebSockets.

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Key Features - ALWAYS Update this section based on Changes or Features Made

- **Feature Modes Page** — Deterministic landing page at `/` with mode selection: Free Inference (LRPC, 1200+ LVIS categories), Prompt Inference (text/visual), or Train Tune, then navigates to the matching workspace
- **Train Tune Workspace** — dedicated `/train-tune` YOLO detection/segmentation builder with task-selectable immutable Dataset Version snapshots, bbox or polygon-mask label export, missing-mask validation with Dataset Workspace handoff, preprocessing Policy with Keep/Letterbox/Stretch resize strategies, Basic online augmentation or Advanced Add Augmentation Step workflow with optional 1x-5x train-only materialized images, smart recommended training settings by dataset size, Auto Batch (`batch=-1`), early-stopping Patience, real backend policy preview samples with bbox/mask overlays, locked split/prep/augmentation summary, backend training config validation/preflight, modal deletion for unused dataset versions and model versions with linked job history, compact model/job badges, JSON-safe metric history with non-blocking job navigation, compact metric trends plus scrollable epoch history and dataset/run/compute details on live progress and model result views, dedicated `/train-tune/jobs/:id` live progress pages, dedicated `/train-tune/results/:id` result pages, dedicated `/train-tune/test/:id` model testing, Standard vs High-Speed GPU modes with auto-detected GPU selection (manual assignment from detected devices), full-process cancellation, failed-job re-compute/delete, last-checkpoint resume, train log/results CSV artifacts under `traintune-workspace/`, and model version registry.
- **Free Inference Mode** — Prompt-free detection using YOLOE LRPC internal vocabulary (separate `yoloe-26l-seg-pf.pt` weights, no user prompts needed)
- **Dual Prompt Modes** — Text prompt (comma-separated labels via `set_classes`) and Visual Prompt (reference image + bbox annotations via SAVPE encoder)
- **Multi-Media Input** — Static image upload (JPG/PNG), video processing (MP4/AVI/MOV), and RTSP live streaming
- **Canvas BBox Annotation** — Interactive drawing tool with thin hover/drag X/Y guide lines for annotating reference images as visual grounding input
- **Configurable Inference** — Confidence threshold slider plus backend-rendered label/bbox visibility and clipped mask overlay toggles
- **Detection Dashboard** — Floating right-side inference panel with compact stats and scrollable detection log
- **Clear Media Workflow** — Media mode switching is locked until inference is stopped and current media input is cleared
- **Network-Accessible** — Hosts on `0.0.0.0:3131`, accessible from any device on the local network
- **Auto-Labelling** — Save inference results as labeled datasets for YOLO fine-tuning. Trigger from Workspace Auto-Label modal or batch upload via Dataset Manager. While active on RTSP, continuous viewer-frame annotations are saved until auto-label is stopped (modal, optional MM:SS timer, or Stop Inference). Accept/reject detections, add/edit/delete manual bboxes, and use per-class/per-object overlay controls. Export in YOLO TXT + COCO JSON formats with train/val split, preserving original input filenames in exported artifacts whenever available.
- **Dataset Manager** — Standalone `/datasets` page for multi-project dataset management with Inference-style header navigation, delete confirmation modals, Select All Files gallery selection, real overlay paginated thumbnail gallery (25/page), centered modal review with cross-page Prev/Next, compact class/status review controls, zoomable/pannable review canvas for pixel-level bbox editing, viewport-clamped Edit BBox popover, per-dataset manual class colors, global class rename (inline double-click with merge support) and delete (bulk across all images), manual bbox add/edit/delete annotation editor, simplified multi-prompt Infer Next + Infer Current visual-prompt candidate propagation with per-candidate Accept/Reject plus Accept All & Continue, canvas annotation toolbar with Select/BBox/Pan tools and SAM mask toggle (keyboard shortcuts V/B/H/M), direct annotation delete, granular overlay controls and image delete, Rapid Inference jobs with frame-by-frame `Frame x/y` progress, configurable frame sampling, and zip export.
- **SAM2.1 Auto-mask** — SAM2.1 (Hiera Large) runs on GPU 1 independently from YOLOE on GPU 0. Automatically generates mask segmentation when users draw manual bbox annotations in Dataset Manager review. Lazy-loaded, thread-safe, with status/load/unload API endpoints. Non-fatal — bbox saves without mask if SAM unavailable.
- **GPU Settings** — Auto-detect CUDA GPUs at runtime via `torch.cuda`. Settings modal (gear icon in header) for manual YOLOE/SAM device assignment with hot-swap model reload. Persistent inference config via `gpu_config.json`. Train Tune has separate GPU detection and selection for Standard (1 GPU) and High-Speed (2+ GPUs) modes via `training_gpu_config.json`. Both configs loaded on startup with env var fallback.

## Project Structure - ALWAYS Update this section based on Changes or Features Made

```
LabelLens/
├── frontend/src/
│   ├── shared/
│   │   ├── api/             (client.ts, detection.ts, ws.ts, dataset.ts, training.ts, sam.ts, system.ts)
│   │   ├── composables/     (useBackendStatus.ts, useWebSocket.ts)
│   │   ├── components/      (SettingsModal.vue)
│   │   ├── stores/          (inference.ts, dataset.ts, training.ts — Pinia)
│   │   └── types/           (index.ts)
│   └── pages/
│       ├── mode-select/     (ModeSelectPage.vue — inference mode selection)
│       ├── datasets/        (DatasetsPage, DatasetList, DatasetDetail, ReviewPanel,
│       │                    EditableAnnotationOverlay, CanvasToolbar, ExportDialog, BatchUploadDialog)
│       ├── train-tune/      (TrainTunePage — builder/live/result routes, TestModelPage — artifact testing)
│       └── workspace/       (components, sections)
├── backend/
│   ├── routers/         (health.py, detection.py, stream.py, dataset.py, training.py, sam.py, system.py)
│   ├── services/        (model.py, video.py, rtsp.py, dataset.py, activity.py, training.py,
│   │                    training_events.py, training_runtime.py, sam.py, gpu.py)
│   ├── train_worker.py  (background training worker process for Train Tune jobs)
│   └── utils/           (drawing.py, encoding.py, masks.py, postprocess.py)
├── datasets/            (runtime dataset storage, gitignored)
├── docs/
│   ├── ARCHITECTURE.md  (system architecture and data flow)
│   ├── API.md           (REST/WebSocket endpoint catalog)
│   ├── MODELS.md        (YOLOE/SAM/checkpoint and GPU guide)
│   ├── WORKFLOWS.md     (operator workflows)
│   ├── TESTING.md       (automated/manual validation checklist)
│   ├── OPERATIONS.md    (local LAN runbook and troubleshooting)
│   ├── REFERENCES.md    (external and project-local references)
│   ├── assets/          (README and documentation media)
│   ├── plans/           (saved implementation plans)
│   └── superpowers/specs/ (design specs)
├── temp/                (runtime/debug snapshots)
├── PRD.md, DESIGN.md, AGENTS.md, CLAUDE.md, README.md
```

## Current State - ALWAYS Update this section based on Changes or Features Made

**Condition:** Implemented and awaiting full end-to-end validation. All three inference phases (Image, Video, RTSP) are scaffolded, integrated, and routed through the backend model service, which supports `predict_text()`, `predict_visual()` (SAVPE), and `predict_free()` (LRPC prompt-free mode). Model loading is deferred: users land on `/` (Feature Modes), navigate to `/workspace` after inference model load, while Dataset Manager remains independently available at `/datasets` and Train Tune is independently available at `/train-tune`. Frontend UI components use the DESIGN.md Supabase-inspired tokens. Backend unit coverage exists for dataset and Train Tune services/runtime.

**Implemented and pending end-to-end validation:**

- **Inference Workspaces:** Free Mode, Text Prompt, Visual Prompt, Image Detection, Video Processing, and RTSP WebSocket streaming are implemented across backend and frontend. Validation still needs real YOLOE weights, sample videos, and live RTSP feeds on target hardware.
- **Dataset Manager / Auto-Labelling / Rapid Inference:** Standalone Dataset Manager, delete controls, Select All Files, paginated overlay gallery, modal review, zoom/pan canvas, viewport-clamped bbox editor, persisted class colors, manual bbox add/edit/delete, direct saved-label delete, multi-prompt Infer Next, Rapid Inference jobs, workspace image/video/RTSP auto-save, and YOLO/COCO export are implemented. Validation still needs complete runs with actual model outputs.
- **Train Tune / Custom Model Reuse:** Detection vs segmentation task selection, Dataset Version snapshots, bbox/polygon export, missing-mask validation, preprocessing Policy, Basic/Advanced augmentation, smart defaults, policy previews, locked Dataset Version summaries, backend validation/preflight, queueing, Standard vs High-Speed RTX 5080 GPU policy, cancellation, recompute/delete, resume from `last.pt`, train log/results CSV tracking, live websocket progress, metric trends, model registry, result pages, and `/train-tune/test/:id` artifact testing are implemented. Validation still needs real detection and segmentation checkpoint runs.
- **SAM2.1 Auto-mask:** Backend `SAMService`, status/load/unload endpoints, dataset-scoped mask generation, and frontend auto-mask flow for manual bbox save are implemented. Validation still needs full SAM2.1 GPU execution checks on the target RTX 5080 device.

**Operational validation still needed:**

- Verify required model files on the target machine: `models/yoloe-26l-seg.pt`, `models/yoloe-26l-seg-pf.pt`, and `models/sam2.1_l.pt`.
- Run full image/video/RTSP inference validation with real media and expected detections.
- Run Train Tune detection and segmentation jobs using real checkpoints, including Standard Mode and High-Speed Mode.
- Confirm SAM2.1 mask generation quality and failure behavior when SAM is unavailable.
- Confirm physical GPU mapping: LabelLens defaults to `CUDA_VISIBLE_DEVICES=1,2` but now supports runtime auto-detection and manual reassignment via Settings modal. Train Tune GPU selection uses auto-detected devices for Standard (1 GPU) and High-Speed (2+ GPUs) modes. Both configs persist to JSON files with env var fallback.


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
- Save every plan or specification to the `docs/plans/` folder so you can track which plans have been created or are currently being created. This allows you to resume the session if the AI agent's token expires. USE `Superpowers` skill to provide the plan. REMEMBER This file does not need to be updated unless requested. It is intended solely as a record of past information. Make sure not to DUPLICATE it; if you’ve already created a plan outside of Superpowers, there’s no need to create another one, and vice versa.
- DO NOT commit the Plans.
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
