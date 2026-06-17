# Project Overview

## Project Synopsis - ALWAYS Update this section based on Codebase or Workflow Changes

**LabelLens** is a web-based object detection, segmentation, pose, classification, and dataset iteration application powered by **YOLOE-26L**, Ultralytics YOLO task models, and SAM/SAM2-style mask generation workflows. It provides visual workspaces for real-time and batch inference, dataset review/export, auto-labelling, and immutable Train Tune jobs using live Dataset Version snapshots or exported zips. The architecture separates compute-heavy CV workloads (FastAPI, PyTorch, Ultralytics, OpenCV, Albumentations) from the presentation layer (Vue 3 SPA with Vite and Pinia), communicating via REST API and WebSockets.

## References - ALWAYS Update this section based on Model, CV Stack, Workflow, or Architecture Changes

**Model and Computer Vision Stack**
- YOLOE repository: `https://github.com/THU-MIG/yoloe`
- YOLOE documentation: `https://docs.ultralytics.com/models/yoloe/`
- YOLOE Hugging Face Space: `https://huggingface.co/spaces/jameslahm/yoloe`
- Ultralytics YOLO documentation: `https://docs.ultralytics.com/`
- Ultralytics YOLO task docs: `https://docs.ultralytics.com/tasks/`
- Ultralytics SAM docs: `https://docs.ultralytics.com/models/sam/`
- Meta SAM2 repository: `https://github.com/facebookresearch/sam2`
- Ultralytics CLIP dependency: `https://github.com/ultralytics/CLIP`
- PyTorch documentation: `https://pytorch.org/docs/stable/index.html`
- OpenCV documentation: `https://docs.opencv.org/`
- Albumentations documentation: `https://albumentations.ai/docs/`
- NumPy documentation: `https://numpy.org/doc/`
- Pillow documentation: `https://pillow.readthedocs.io/`

**Application Stack**
- FastAPI documentation: `https://fastapi.tiangolo.com/`
- Uvicorn documentation: `https://www.uvicorn.org/`
- Python websockets documentation: `https://websockets.readthedocs.io/`
- Vue documentation: `https://vuejs.org/`
- Vite documentation: `https://vite.dev/`
- Pinia documentation: `https://pinia.vuejs.org/`

## Key Features - ALWAYS Update this section based on Changes or Features Made

- **Feature Modes Page** — Deterministic landing page at `/` with mode selection: Free Inference (LRPC, 1200+ LVIS categories), Prompt Inference (text/visual), or Train Tune, then navigates to the matching workspace
- **Train Tune Workspace** — dedicated `/train-tune` YOLO detection/segmentation/pose/single-label classification builder with task-selectable immutable Dataset Version snapshots, bbox, polygon-mask, keypoint, or class-folder label export, missing-mask validation with Dataset Workspace handoff, preprocessing Policy with Keep/Letterbox/Stretch resize strategies, Basic online augmentation or Advanced Add Augmentation Step workflow with optional 1x-5x train-only materialized images, smart recommended training settings by dataset size, Auto Batch (`batch=-1`), early-stopping Patience, real backend policy preview samples with bbox/mask/keypoint overlays, locked split/prep/augmentation summary, backend training config validation/preflight, modal deletion for unused dataset versions and model versions with linked job history, compact model/job badges, JSON-safe task-aware metric history with non-blocking job navigation, compact metric trends plus scrollable epoch history and dataset/run/compute details on live progress and model result views, explicit missing-checkpoint failure diagnostics when Ultralytics completes without `best.pt`/`last.pt`, dedicated `/train-tune/jobs/:id` live progress pages, dedicated `/train-tune/results/:id` result pages, dedicated `/train-tune/test/:id` model testing, Standard vs High-Speed GPU modes with auto-detected GPU selection (manual assignment from detected devices), full-process cancellation, failed-job re-compute/delete, last-checkpoint resume, train log/results CSV artifacts under `traintune-workspace/`, and model version registry.
- **Free Inference Mode** — Prompt-free detection using YOLOE LRPC internal vocabulary (separate `yoloe-26l-seg-pf.pt` weights, no user prompts needed)
- **Dual Prompt Modes** — Text prompt (comma-separated labels via `set_classes`) and Visual Prompt (reference image + bbox annotations via SAVPE encoder)
- **Multi-Media Input** — Static image upload (JPG/PNG), video processing (MP4/AVI/MOV), and RTSP live streaming
- **Canvas BBox Annotation** — Interactive drawing tool with thin hover/drag X/Y guide lines for annotating reference images as visual grounding input
- **Configurable Inference** — Confidence threshold slider plus backend-rendered label/bbox visibility and clipped mask overlay toggles. Task-matched rendering: bbox (detect), clipped masks (segment), keypoint skeletons (pose), and classification top-1 banner with Top-5 class panel — used by inference workspaces and the Test Model page.
- **Detection Dashboard** — Floating right-side inference panel with compact stats and scrollable detection log
- **Clear Media Workflow** — Media mode switching is locked until inference is stopped and current media input is cleared
- **Network-Accessible** — Hosts on `0.0.0.0:3131`, accessible from any device on the local network
- **Auto-Labelling** — Save inference results as labeled datasets for YOLO fine-tuning. Trigger from Workspace Auto-Label modal or batch upload via Dataset Manager. While active on RTSP, continuous viewer-frame annotations are saved until auto-label is stopped (modal, optional MM:SS timer, or Stop Inference). Accept/reject detections, add/edit/delete manual bboxes, and use per-class/per-object overlay controls. Export in YOLO TXT + COCO JSON formats with train/val split, preserving original input filenames in exported artifacts whenever available.
- **Dataset Manager** — Standalone `/datasets` page for multi-project dataset management with Inference-style header navigation, delete confirmation modals, Select All Files gallery selection, real overlay paginated thumbnail gallery (25/page), centered modal review with cross-page Prev/Next, compact class/status review controls, zoomable/pannable review canvas for pixel-level bbox editing, viewport-clamped Edit BBox popover, per-dataset manual class colors, global class rename (inline double-click with merge support) and delete (bulk across all images), manual bbox add/edit/delete annotation editor, simplified multi-prompt Infer Next + Infer Current visual-prompt candidate propagation with per-candidate Accept/Reject plus Accept All & Continue, canvas annotation toolbar with Select/BBox/Pan tools and SAM mask toggle (keyboard shortcuts V/B/H/M), direct annotation delete, granular overlay controls and image delete, Ultralytics-style Pose annotation editor with a Move/BBox/Pan-Zoom/Visibility toolbar (M/B/H/C), anatomically-templated draggable keypoint skeletons (COCO Person 17 / Box Corners), bbox-clamped keypoint drag plus full-bbox interior drag to translate the box with all keypoints, cursor-anchored wheel zoom/pan, list↔canvas keypoint hover/select sync, click-to-cycle keypoint visibility, and click-to-edit/update/delete of saved pose instances, toolbar-triggered per-image Pose Infer Assist floating bar (Infer Current) with on-canvas candidate skeleton overlay, Ultralytics pose model candidate accept/reject and Accept All, task-matched Rapid Inference jobs with YOLOE prompts for detection, segmentation, and single-label classification plus Ultralytics task models for pose, frame-by-frame `Frame x/y` progress, configurable frame sampling, and zip export.
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

**Codebase Changelog:** This section records the implemented codebase state as a change log. Each entry should describe what was developed and what changed in the application after that work. The Timeline column lists the git commit date range (first–latest relevant commit) for that area.

| Area | Timeline (git) | What was developed | After the change |
| ------ | ---------------- | -------------------- | ------------------ |
| Feature Modes and Routing | 2026-05-19 | Added deterministic `/` mode selection for Free Inference, Prompt Inference, and Train Tune. | Users start from a mode selector, inference model loading is deferred until workspace entry, and `/datasets` plus `/train-tune` remain independently reachable. |
| Inference Workspaces | 2026-05-19 – 2026-06-17 | Implemented Free Mode, Text Prompt, Visual Prompt, image inference, video processing, and RTSP WebSocket streaming through the backend model service, plus task-matched result parsing/rendering (bbox, masks, pose keypoint skeletons, classification top-1/Top-5). | Backend exposes `predict_free()`, `predict_text()`, and `predict_visual()` paths, the frontend runs image/video/live-stream detection flows, and output is rendered per task type across inference workspaces and the Test Model page. |
| Dataset Manager and Auto-Labelling | 2026-05-20 – 2026-06-08 | Built standalone dataset management, gallery review, bbox editing, class controls, auto-save from inference, YOLO/COCO/classification/pose export, and task-aware Rapid Inference flows. | Datasets can be created, reviewed, corrected, propagated with prompt-assisted inference, and exported for downstream training workflows. |
| Pose Annotation | 2026-06-05 – 2026-06-08 | Added Ultralytics-style pose editing with keypoint templates, visibility cycling, bbox/keypoint drag behavior, pan/zoom, and pose infer assist. | Pose datasets can be reviewed and corrected directly in the Dataset Manager with task-specific controls. |
| SAM2.1 Auto-mask | 2026-05-22 | Added backend `SAMService`, status/load/unload endpoints, dataset-scoped mask generation, and frontend auto-mask trigger from manual bbox save. | Manual bbox annotations can optionally receive generated segmentation masks, while bbox saves remain non-fatal if SAM is unavailable. |
| Train Tune Workspace | 2026-05-22 – 2026-06-17 | Implemented task-selectable training builder, immutable Dataset Version snapshots, preprocessing policy, augmentation controls, training preflight (with base-checkpoint auto-download and multi-GPU AutoBatch handling), job queueing, task-aware live metrics, explicit missing-checkpoint diagnostics, result pages, resume/recompute/delete, artifact testing, and model registry. | Detection, segmentation, pose, and single-label classification jobs can be configured, launched, monitored with task-matched metrics, failed clearly when Ultralytics saves no checkpoint, resumed, tested, and tracked as reusable model versions. |
| GPU Settings | 2026-06-01 – 2026-06-02 | Added CUDA GPU auto-detection, inference GPU assignment, SAM GPU assignment, Train Tune Standard/High-Speed GPU selection, and persisted GPU config files. | Runtime GPU mapping can be managed from UI/config instead of relying only on environment defaults. |
| Backend Runtime and Tests | 2026-05-19 – 2026-06-17 | Added dataset, Train Tune service/runtime, model parsing, drawing, task-aware training metric parsing, and missing-checkpoint failure unit coverage around implemented backend workflows. | Core dataset, training orchestration, Train Tune worker metrics/checkpoint handling, and inference parsing behavior has automated coverage, with full target-hardware validation still pending. |


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
