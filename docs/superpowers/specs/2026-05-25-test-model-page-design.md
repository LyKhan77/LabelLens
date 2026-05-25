# Test Model Page — Design Spec

**Date**: 2026-05-25
**Status**: Draft
**Scope**: New dedicated page for testing inference with trained/tuned custom models

## Context

Train Tune produces trained YOLO models (`.pt` checkpoints) with metadata (class names, metrics, architecture). Currently there is no way to run inference with these custom models — the inference workspace only supports pre-built YOLOE models (free/prompt modes). Users need a way to validate trained model quality by running detections on new media before deciding to export or iterate.

## Approach

**Dedicated page** at `/train-tune/test/:modelId`. Accessible via "Test Model" button on the Train Tune results page. Shares viewer/canvas components from the existing workspace but has a streamlined compact sidebar — no mode selection, no prompt inputs. The trained model's fixed class list drives detection.

### Why dedicated page over extending workspace

- Clean separation — test page is focused on model validation, not general inference
- No prompt mode selection needed — custom models have fixed classes
- Stays within Train Tune navigation context (breadcrumb: Train Tune > Results > Test)
- Workspace doesn't need conditional logic for custom vs pre-built models
- Easy to add model-specific features later (e.g., comparison mode)

## Architecture

### Route

- **New route**: `/train-tune/test/:modelId`
- **Entry point**: "Test Model" button on results page (`/train-tune/results/:modelId`)
- **Navigation**: Back button returns to results page

### Data Flow

```
Results Page → "Test Model" click → /train-tune/test/:modelId
  → Load model metadata from training store (class_names, arch, path)
  → Call POST /api/model/load-custom with model_id
  → Backend loads .pt weights into YOLOE runtime
  → User uploads media → runs inference
  → Detections displayed via reused viewer components
  → "Save to Dataset" → existing auto-label flow
```

### Frontend Components

**New files:**
- `frontend/src/pages/train-tune/TestModelPage.vue` — main page layout
- `frontend/src/pages/train-tune/components/TestSidebar.vue` — compact sidebar

**Reused from workspace (import, not copy):**
- `workspace/components/Viewer.vue` — detection result display
- `workspace/components/DetectionLog.vue` — scrollable detection list
- `workspace/components/StatsGrid.vue` — inference stats
- `workspace/sections/media/MediaInput.vue` — image/video/RTSP input
- `workspace/components/AutoLabelModal.vue` — save-to-dataset modal

**New sidebar sections:**
1. **Model info card** (read-only) — model name, architecture, class list, best mAP badge
2. **Media input** — image/video/RTSP mode tabs + upload area
3. **Confidence slider** — threshold control
4. **Action buttons** — Run Inference + Save to Dataset

### Backend Changes

**New endpoint:**
- `POST /api/model/load-custom` — load trained model by ID
  - Request: `{ model_id: string }`
  - Resolves model metadata from training service (best_model_path, class_names)
  - Loads `.pt` checkpoint into YOLOE runtime via Ultralytics
  - Sets model as active for inference

**Extended service method:**
- `ModelService.load_model()` — add support for custom model path loading
  - New parameter: `model_path: str | None = None`
  - When `model_path` provided, load from filesystem instead of predefined modes
  - Store loaded class names for detection response

**Inference behavior:**
- Existing `predict_text()` works with custom models — classes come from the model's training data
- No prompt configuration needed — the model's class list is used automatically
- Detection response format unchanged (image + detections + stats)

### State Management

**New composable `frontend/src/shared/composables/useTestModel.ts`**:
- Keeps test model state separate from the existing inference store
- `testModelId: string | null` — currently loaded test model
- `testModelInfo: ModelVersion | null` — model metadata
- `loadModelInfo(modelId)` — fetch model metadata from training store
- `loadTestModel(modelId)` — calls load-custom endpoint
- `unloadTestModel()` — cleanup on page leave
- Media, settings, and result state reuse existing inference store patterns via imports

### Save to Dataset

Uses the existing auto-label workflow:
- "Save to Dataset" button opens `AutoLabelModal`
- For images: save current detection with annotations
- For video: batch save with frame sampling
- For RTSP: continuous save with optional timer
- Same endpoints: `POST /datasets/{name}/save`, `POST /datasets/{name}/save-stream`

## UI Design

### Compact Sidebar Layout

```
┌──────────────────────────────────────────────┐
│  AppHeader (shared)                          │
├─────────────┬────────────────────────────────┤
│  SIDEBAR    │  VIEWER                        │
│             │                                │
│ ┌─────────┐ │  ┌──────────────────────────┐  │
│ │Model Info│ │  │                          │  │
│ │● Loaded  │ │  │   Detection Canvas       │  │
│ │bottle-v1 │ │  │   (reused Viewer.vue)    │  │
│ │yolo11s   │ │  │                          │  │
│ │3 classes │ │  │                          │  │
│ └─────────┘ │  └──────────────────────────┘  │
│             │                                │
│ Media Input │  ┌──────┐ ┌────────────────┐   │
│ [Img][Vid]  │  │Stats │ │ Detection Log  │   │
│ [RTSP]      │  │Grid  │ │ (scrollable)   │   │
│ ┌─────────┐ │  └──────┘ └────────────────┘   │
│ │Drop file│ │                                │
│ └─────────┘ │                                │
│             │                                │
│ Confidence  │                                │
│ ═══●══════  │                                │
│             │                                │
│ [▶ Run]     │                                │
│ [💾 Save]   │                                │
├─────────────┴────────────────────────────────┤
</pre>
```

### Design Tokens

Follows existing DESIGN.md Supabase-inspired tokens:
- Model info card: `surface-card` background, `emerald-500` status indicator
- Action buttons: `emerald-500` (Run), `blue-500` (Save)
- Media tabs: same tab style as workspace
- Confidence slider: same component as workspace settings

### Key UX Decisions

1. **No prompt configuration** — custom models have fixed class lists from training
2. **No mode selection** — no "free vs prompt" choice, model is pre-selected
3. **Model info is read-only** — shows architecture, classes, best metrics as reference
4. **Back navigation** — clear breadcrumb back to results page
5. **Auto-label reuse** — identical save flow to workspace auto-label

## Verification

1. Start backend, place a trained `.pt` model in the training output directory
2. Navigate to `/train-tune/results/:modelId` → click "Test Model"
3. Verify model loads (status indicator turns green)
4. Upload test image → run inference → verify detections appear
5. Test video upload → verify frame-by-frame inference works
6. Test RTSP stream → verify live detection works
7. Click "Save to Dataset" → verify auto-label modal opens and saves correctly
8. Test back navigation → returns to results page
9. Test with model that fails to load → verify error state

## Files to Modify/Create

**New:**
- `frontend/src/pages/train-tune/TestModelPage.vue`
- `frontend/src/pages/train-tune/components/TestSidebar.vue`

**Modified:**
- `frontend/src/app/App.vue` — add `/train-tune/test/:modelId` route
- `frontend/src/shared/composables/useTestModel.ts` — new composable for test model state
- `frontend/src/shared/stores/inference.ts` — minor adjustments to support external model loading
- `frontend/src/shared/api/detection.ts` — add load-custom model API call
- `frontend/src/shared/types/index.ts` — add test model types if needed
- `frontend/src/pages/train-tune/TrainTunePage.vue` — add "Test Model" button in results view
- `backend/routers/health.py` — add `POST /api/model/load-custom` endpoint
- `backend/services/model.py` — extend `load_model()` for custom model paths
- `frontend/src/pages/train-tune/components/ResultHeader.vue` (or wherever the result actions are) — add Test Model button
