# Free Mode Inference — Design Spec

**Date:** 2026-05-19
**Status:** Draft
**Branch:** feat/mask-overlay (base)

## Context

LabelLens currently supports two prompt-driven detection modes: **Text Prompt** (comma-separated labels via `set_classes`) and **Visual Prompt** (reference image + bbox via SAVPE). Both require user-supplied prompts.

YOLOE's **LRPC (Lazy Region-Prompt Contrast)** module enables a third mode: **prompt-free detection** using internal embeddings trained on 1200+ categories (LVIS + Objects365). This requires separate model weights (`yoloe-26l-seg-pf.pt` with `-pf` suffix) — not the same `yoloe-26l-seg.pt` used for text/visual prompts.

This spec adds a **Feature Modes** landing page where users choose between Free Inference Mode and Prompt Inference Mode. Only one model is loaded in VRAM at a time.

## Architecture

### Flow

```
[Feature Modes Page /mode]
  ├── Click "Free Inference"   → POST /model/load {mode:"free"}  → load yoloe-26l-seg-pf.pt
  └── Click "Prompt Inference" → POST /model/load {mode:"prompt"} → load yoloe-26l-seg.pt
       ↓ (on success)
[Dashboard /dashboard]
  ├── Free Mode:    Step 1 hidden, Step 2 (Media) + Step 3 (Settings) visible
  └── Prompt Mode:  Step 1 (Text/Visual) + Step 2 + Step 3 visible
       ↓
  "Switch Mode" button → navigate back to /mode → unload model → select new mode
```

### Route Map

| Route | Component | Description |
|-------|-----------|-------------|
| `/mode` | `FeatureModes.vue` | NEW landing page, mode selection |
| `/dashboard` | Current app | Renamed from `/`, guard checks model loaded |

## Backend Changes

### New Endpoints

**`POST /model/load`**
- Request: `{ "mode": "free" | "prompt" }`
- Behavior: Unloads current model (frees VRAM), loads new model (blocking, ~5-10s)
- Response: `{ "success": true, "mode": "free", "model": "yoloe-26l-seg-pf.pt" }`
- Error: `{ "success": false, "error": "Model file not found" }`

**`GET /model/status`**
- Response: `{ "mode": "free" | "prompt" | null, "loaded": true/false, "model_name": "...", "device": "cuda:0" }`

### Model Service Changes (`backend/services/model.py`)

**New method: `load_model(mode: str)`**
- `mode == "prompt"` → load `models/yoloe-26l-seg.pt` (existing behavior)
- `mode == "free"` → load `models/yoloe-26l-seg-pf.pt` (new)
- Unloads previous model before loading new one
- Stores current mode in `self.current_mode`

**New method: `predict_free(image, conf)`**
- Calls `self.model.predict(image, conf=conf, device=self.device, verbose=False, retina_masks=True)`
- No `set_classes()` call — model uses internal LRPC vocabulary (1200+ LVIS categories)
- Uses existing `_parse_results()` for consistent output format

**Startup behavior change:**
- Backend starts **without loading any model** (deferred to user selection)
- `GET /model/status` returns `{ loaded: false }` until mode is selected

### Detection Router Changes (`backend/routers/detection.py`)

- `POST /detect/image` and `/detect/video` accept `prompt_type: "free"`
- When `prompt_type == "free"` → route to `model_service.predict_free()`
- No labels/refer_image/bboxes fields required

### Stream Router Changes (`backend/routers/stream.py`)

- WebSocket config accepts `prompt_type: "free"`
- Routes to `predict_free()` instead of `predict_text()`/`predict_visual()`

### Video/RTSP Service Changes

- `backend/services/video.py`: Process frames with `predict_free()` when `prompt_type == "free"`
- `backend/services/rtsp.py`: Same — stream frames through `predict_free()`

## Frontend Changes

### New Component: `FeatureModes.vue`

- Two cards: **Free Inference** and **Prompt Inference**
- Each card: icon, title, short description
- Click → `POST /model/load` → loading state on card → navigate to `/dashboard` on success
- Loading state: spinner + "Loading model..." + model filename
- Other card dimmed/disabled during load
- Error state: error message on card, both cards re-enabled
- Design tokens: Supabase-inspired (follow DESIGN.md)

### Router Changes

- `/mode` → `FeatureModes.vue` (new default route)
- `/dashboard` → Current main layout (renamed from `/`)
- Route guard on `/dashboard`: if `modelLoaded === false`, redirect to `/mode`

### Store Changes (`stores/inference.ts`)

**New state:**
- `inferenceMode: Ref<'free' | 'prompt' | null>` — selected mode
- `modelLoaded: Ref<boolean>` — whether model is ready

**Updated `canRun` computed:**
- Free mode: no label/annotation validation needed, only media required
- Prompt mode: existing validation unchanged

**Updated `buildPromptParams()`:**
- Free mode: sends `prompt_type: 'free'`, no labels/refer_image/bboxes

### API Client Changes (`api/client.ts`)

**New methods:**
- `loadModel(mode: 'free' | 'prompt')` → `POST /model/load`
- `getModelStatus()` → `GET /model/status`

### Dashboard UI Adaptation

- **Free Mode:** `GroundingInput.vue` (Step 1) hidden entirely
- **Prompt Mode:** Current UI unchanged
- "Switch Mode" button in Dashboard header → navigate to `/mode`
- If RTSP is running when switching → stop stream first, then navigate

### Type Changes (`types/index.ts`)

- `PromptMode` extended: `'text' | 'visual' | 'free'`
- New `InferenceMode` type: `'free' | 'prompt'`

## Files to Modify

### Backend
- `backend/services/model.py` — add `load_model()`, `predict_free()`, startup change
- `backend/routers/detection.py` — handle `prompt_type: "free"`
- `backend/routers/stream.py` — handle `prompt_type: "free"` in WS config
- `backend/routers/health.py` — add `GET /model/status`
- `backend/services/video.py` — route to `predict_free()` for free mode
- `backend/services/rtsp.py` — route to `predict_free()` for free mode

### Frontend
- `frontend/src/components/FeatureModes.vue` — NEW
- `frontend/src/router/index.ts` — new routes + guard
- `frontend/src/stores/inference.ts` — new state + updated logic
- `frontend/src/api/client.ts` — new API methods
- `frontend/src/types/index.ts` — extended types
- `frontend/src/components/Sidebar.vue` or equivalent — "Switch Mode" button
- `frontend/src/components/GroundingInput.vue` — conditional visibility based on mode
- `frontend/src/App.vue` — route updates

### Config
- `models/` directory — needs `yoloe-26l-seg-pf.pt` placement

## Model Files Required

| Mode | File | Source |
|------|------|--------|
| Prompt (text/visual) | `models/yoloe-26l-seg.pt` | Already in use |
| Free (prompt-free) | `models/yoloe-26l-seg-pf.pt` | NEW — download from YOLOE releases |

## Verification

1. **Mode Selection:** Open app → see Feature Modes page → click Free Inference → model loads → Dashboard shows without Step 1
2. **Free Mode Image:** Upload image → run inference → detections appear with LVIS class labels
3. **Free Mode Video:** Upload video → process → detections with LVIS labels
4. **Free Mode RTSP:** Connect RTSP → stream → detections with LVIS labels
5. **Switch Mode:** Click "Switch Mode" → back to Feature Modes → select Prompt → model reloads → Dashboard shows Step 1
6. **Guard:** Navigate directly to `/dashboard` without selecting mode → redirected to `/mode`
7. **Backend Status:** `GET /model/status` returns correct state at each step
8. **Error Handling:** Select mode without model file present → error shown on card
