# Project Overview

## Project Synopsis

**LabelLens** is a web-based object detection application powered by **YOLOE-26L**. It provides a visual interface for running real-time and batch inference using both text prompts and visual prompts (SAVPE — Semantic-Activated Visual Prompt Encoder). The architecture separates compute-heavy CV workloads (FastAPI + PyTorch) from the presentation layer (Vue 3 SPA), communicating via REST API and WebSockets.

## References
- `https://github.com/THU-MIG/yoloe`
- `https://docs.ultralytics.com/models/yoloe`
- `https://huggingface.co/spaces/jameslahm/yoloe`

## Key Features - ALWAYS Update this section based on Changes or Features Made

- **Feature Modes Page** — Deterministic landing page at `/` with mode selection: Free Inference (LRPC, 1200+ LVIS categories) or Prompt Inference (text/visual), then navigates to `/workspace` after model load
- **Free Inference Mode** — Prompt-free detection using YOLOE LRPC internal vocabulary (separate `yoloe-26l-seg-pf.pt` weights, no user prompts needed)
- **Dual Prompt Modes** — Text prompt (comma-separated labels via `set_classes`) and Visual Prompt (reference image + bbox annotations via SAVPE encoder)
- **Multi-Media Input** — Static image upload (JPG/PNG), video processing (MP4/AVI/MOV), and RTSP live streaming
- **Canvas BBox Annotation** — Interactive drawing tool with thin hover/drag X/Y guide lines for annotating reference images as visual grounding input
- **Configurable Inference** — Confidence threshold slider plus backend-rendered label/bbox visibility and clipped mask overlay toggles
- **Detection Dashboard** — Floating right-side inference panel with compact stats and scrollable detection log
- **Clear Media Workflow** — Media mode switching is locked until inference is stopped and current media input is cleared
- **Network-Accessible** — Hosts on `0.0.0.0:3131`, accessible from any device on the local network
- **Auto-Labelling** — Save inference results as labeled datasets for YOLO fine-tuning. Trigger from Workspace Auto-Label modal or batch upload via Dataset Manager. While active on RTSP, continuous viewer-frame annotations are saved until auto-label is stopped (modal, optional MM:SS timer, or Stop Inference). Accept/reject detections, add/edit/delete manual bboxes, and use per-class/per-object overlay controls. Export in YOLO TXT + COCO JSON formats with train/val split.
- **Dataset Manager** — Standalone `/datasets` page for multi-project dataset management with Inference-style header navigation, delete confirmation modals, Select All Files gallery selection, real overlay paginated thumbnail gallery (25/page), centered modal review with cross-page Prev/Next, manual bbox add/edit/delete annotation editor, Infer Next visual-prompt candidate propagation for missing objects, granular overlay controls and image delete, Rapid Inference jobs with frame-by-frame `Frame x/y` progress, configurable frame sampling, and zip export.

## Project Structure - ALWAYS Update this section based on Changes or Features Made

```
LabelLens/
├── frontend/src/
│   ├── shared/
│   │   ├── api/             (client.ts, detection.ts, ws.ts, dataset.ts)
│   │   ├── composables/     (useBackendStatus.ts, useWebSocket.ts)
│   │   ├── stores/          (inference.ts, dataset.ts — Pinia)
│   │   └── types/           (index.ts)
│   └── pages/
│       ├── mode-select/     (ModeSelectPage.vue — inference mode selection)
│       ├── datasets/        (DatasetsPage, DatasetList, DatasetDetail, ReviewPanel,
│       │                    EditableAnnotationOverlay, ExportDialog, BatchUploadDialog)
│       └── workspace/       (components, sections)
├── backend/
│   ├── routers/         (health.py, detection.py, stream.py, dataset.py)
│   ├── services/        (model.py, video.py, rtsp.py, dataset.py)
│   └── utils/           (drawing.py, encoding.py)
├── datasets/            (runtime dataset storage, gitignored)
├── docs/plans/          (saved implementation plans)
├── docs/superpowers/specs/ (design specs)
├── temp/                (runtime/debug snapshots)
├── PRD.md, DESIGN.md, AGENTS.md, README.md
```

## Current State - ALWAYS Update this section based on Changes or Features Made

**Condition:** In active development. All three phases (Image, Video, RTSP) are scaffolded and integrated. Core backend model service supports `predict_text()`, `predict_visual()` (SAVPE), and `predict_free()` (LRPC prompt-free mode). Model loading is deferred — users always land on `/` (Feature Modes), navigate to `/workspace` after mode load, while Dataset Manager remains independently available at `/datasets`. Frontend UI components are built with DESIGN.md Supabase-inspired tokens. BBox annotation canvas tool with hover/drag X/Y guides, floating compact inference panel, scrollable detection log, backend-rendered clipped mask overlay, state-preserving collapsible Controls panel, explicit Clear Media mode switching, paginated real-overlay thumbnail dataset gallery with Select All Files, Dataset Manager delete confirmation modals, centered modal review with image delete, manual bbox add/edit/delete, Infer Next visual-prompt candidate review, and cross-page Prev/Next, Rapid Inference job polling with frame-by-frame progress, and workspace RTSP auto-label continuous save with optional timer are functional.

``` 
In THIS (**Being Developed**) section, always double-check features or items that have been completed. Make sure the features are working and set them aside or remove them from the list. 
```
**Being Developed:**
- Auto-Labelling / Rapid Inference: Standalone Dataset Manager page, project overview/delete controls, image bulk/card/review delete controls, Select All Files, real overlay paginated thumbnail gallery, centered modal review with cross-page navigation, manual bbox add/edit/delete, Infer Next visual-prompt candidates, batch label jobs with frame-by-frame progress, inline Free/Text/Visual prompt wizard, and workspace image/video/RTSP auto-save hook implemented — needs end-to-end testing with actual model weights
- Free Mode Inference: Backend + Frontend complete — needs `models/yoloe-26l-seg-pf.pt` placement and testing
- Phase 1 (Image Detection): Backend + Frontend complete — needs end-to-end testing with actual YOLOE model weights
- Phase 2 (Video Processing): Backend + Frontend complete — needs testing with sample videos
- Phase 3 (RTSP Streaming): Backend WebSocket + Frontend integration complete — needs testing with live RTSP feeds
- Overall: Awaiting `models/yoloe-26l-seg.pt` and `models/yoloe-26l-seg-pf.pt` placement and integration testing on RTX 5080 device `0` with `CUDA_DEVICE_ORDER=PCI_BUS_ID`

=====================

# IMPORTANT — DO NOT EDIT BELOW

This section contains critical agent behavior guidelines. Any changes require explicit user approval.

## Important Notes - Project RULES

- Always use relevant skills to help with tasks.
- Always ask the user if there are any plans or discussions that need to be validated.
- Always provide a summary after finishing a task.
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