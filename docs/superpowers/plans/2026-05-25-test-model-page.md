# Test Model Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/train-tune/test/:modelId` page for testing inference with trained/tuned custom YOLO models, with media input (image/video/RTSP), detection display, and save-to-dataset support.

**Architecture:** New backend endpoint `POST /api/model/load-custom` loads trained `.pt` weights into the YOLOE runtime. New frontend route renders a compact sidebar + reused workspace viewer components. The inference store handles detection execution; a new composable manages test model lifecycle.

**Tech Stack:** Vue 3 + Pinia, FastAPI + Ultralytics YOLOE, WebSocket for RTSP

---

## File Structure

**New files:**
- `frontend/src/shared/composables/useTestModel.ts` — test model state composable
- `frontend/src/pages/train-tune/TestModelPage.vue` — main test page layout
- `frontend/src/pages/train-tune/components/TestSidebar.vue` — compact sidebar

**Modified files:**
- `backend/services/model.py` — extend `load_model()` for custom model paths
- `backend/routers/health.py` — add `POST /api/model/load-custom` endpoint
- `frontend/src/shared/api/client.ts` — add `loadCustomModel()` API function
- `frontend/src/app/App.vue` — add `/train-tune/test/:modelId` route
- `frontend/src/pages/train-tune/TrainTunePage.vue` — add "Test Model" button on results page

---

### Task 1: Backend — Extend ModelService for custom model loading

**Files:**
- Modify: `backend/services/model.py:35-63`

- [ ] **Step 1: Add `load_custom_model()` method to ModelService**

Add this method after the existing `load_model()` method (after line 63):

```python
def load_custom_model(self, model_path: str, class_names: list[str]):
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Custom model not found: {model_path}")

    # Unload previous model
    if self.model is not None:
        del self.model
        self.model = None
        gc.collect()
        torch.cuda.empty_cache()

    # Load with Ultralytics YOLO (supports both YOLOE and standard YOLO models)
    self.model = YOLO(model_path)

    self._is_seg_model = "seg" in model_path.lower()
    self.current_mode = "custom"
    self.model_path = model_path
    self.current_classes = list(class_names)
    self._vpe_labels = []
```

Also add the `YOLO` import at the top of `backend/services/model.py` (alongside existing `YOLOE` import on line 12). Custom trained models use standard Ultralytics YOLO format, not YOLOE:

```python
from ultralytics import YOLO, YOLOE
```

- [ ] **Step 2: Update `get_status()` to include custom model info**

Modify the `get_status()` method to also return custom model info:

```python
def get_status(self) -> dict:
    return {
        "mode": self.current_mode,
        "loaded": self.model is not None,
        "model_name": os.path.basename(self.model_path) if self.model_path else None,
        "device": f"cuda:{self.device}",
        "class_names": self.current_classes if self.current_mode == "custom" else [],
    }
```

- [ ] **Step 3: Update `predict_text()` to auto-use custom model classes**

Modify `predict_text()` to skip `set_classes` when the model already has custom classes loaded:

```python
def predict_text(
    self,
    image: np.ndarray,
    labels: list[str],
    conf: float = 0.5,
) -> dict:
    self._require_model()
    if self.current_mode == "custom":
        # Custom model already has its classes baked in — use predict directly
        t0 = time.perf_counter()
        results = self.model.predict(
            image, conf=conf, device=self.device, verbose=False, retina_masks=True
        )
        inference_ms = (time.perf_counter() - t0) * 1000
        return self._parse_results(results, inference_ms)
    # Existing logic for YOLOE prompt mode
    if set(labels) != set(self.current_classes):
        self.model.set_classes(labels)
        self.current_classes = list(labels)

    t0 = time.perf_counter()
    results = self.model.predict(
        image, conf=conf, device=self.device, verbose=False, retina_masks=True
    )
    inference_ms = (time.perf_counter() - t0) * 1000

    return self._parse_results(results, inference_ms)
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/model.py
git commit -m "feat: extend ModelService with custom model loading for trained models"
```

---

### Task 2: Backend — Add load-custom endpoint

**Files:**
- Modify: `backend/routers/health.py:1-41`
- Modify: `backend/routers/training.py` (import `training_service`)

- [ ] **Step 1: Add the `POST /api/model/load-custom` endpoint**

Add to `backend/routers/health.py` after the existing `load_model` endpoint:

```python
from backend.services.training import training_service

class LoadCustomModelRequest(BaseModel):
    model_id: str


@router.post("/model/load-custom")
async def load_custom_model(req: LoadCustomModelRequest):
    try:
        model_meta = training_service.get_model(req.model_id)
        if not model_meta:
            return JSONResponse(status_code=404, content={"error": f"Model {req.model_id} not found"})
        model_service.load_custom_model(
            model_path=model_meta["best_model_path"],
            class_names=model_meta["class_names"],
        )
        return model_service.get_status()
    except FileNotFoundError as e:
        logger.error(f"Custom model file not found: {e}")
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        logger.error(f"Custom model load error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
```

- [ ] **Step 2: Verify `training_service.get_model()` exists**

Check if `backend/services/training.py` already has a `get_model()` method that returns model metadata by ID. If it doesn't exist, add it:

```python
def get_model(self, model_id: str) -> dict | None:
    path = self._model_path(model_id)
    return self._read_json(path, None)
```

This method reads the model JSON file. Verify the returned dict contains `best_model_path` and `class_names` keys.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/health.py backend/services/training.py
git commit -m "feat: add POST /api/model/load-custom endpoint for trained models"
```

---

### Task 3: Frontend — Add loadCustomModel API function

**Files:**
- Modify: `frontend/src/shared/api/client.ts:1-23`

- [ ] **Step 1: Add `loadCustomModel` function**

Append to `frontend/src/shared/api/client.ts`:

```typescript
export async function loadCustomModel(modelId: string) {
  const res = await api.post('/model/load-custom', { model_id: modelId })
  return res.data as {
    mode: string | null
    loaded: boolean
    model_name: string | null
    device: string
    class_names: string[]
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/shared/api/client.ts
git commit -m "feat: add loadCustomModel API function"
```

---

### Task 4: Frontend — Create useTestModel composable

**Files:**
- Create: `frontend/src/shared/composables/useTestModel.ts`

- [ ] **Step 1: Write the composable**

Create `frontend/src/shared/composables/useTestModel.ts`:

```typescript
import { ref, computed } from 'vue'
import { loadCustomModel } from '../api/client'
import type { ModelVersion } from '../api/training'
import { getModelVersion } from '../api/training'

const testModelId = ref<string | null>(null)
const testModelInfo = ref<ModelVersion | null>(null)
const loading = ref(false)
const loaded = ref(false)
const error = ref<string | null>(null)

export function useTestModel() {
  const modelName = computed(() => testModelInfo.value?.model_name ?? null)
  const classNames = computed(() => testModelInfo.value?.class_names ?? [])
  const modelArch = computed(() =>
    testModelInfo.value ? `${testModelInfo.value.family} / ${testModelInfo.value.size}` : '',
  )

  async function loadModelInfo(modelId: string) {
    loading.value = true
    error.value = null
    try {
      testModelInfo.value = await getModelVersion(modelId)
      testModelId.value = modelId
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load model info'
    } finally {
      loading.value = false
    }
  }

  async function loadTestModel(modelId: string) {
    loading.value = true
    error.value = null
    try {
      await loadModelInfo(modelId)
      const result = await loadCustomModel(modelId)
      loaded.value = result.loaded
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load test model'
      loaded.value = false
    } finally {
      loading.value = false
    }
  }

  function reset() {
    testModelId.value = null
    testModelInfo.value = null
    loading.value = false
    loaded.value = false
    error.value = null
  }

  return {
    testModelId,
    testModelInfo,
    loading,
    loaded,
    error,
    modelName,
    classNames,
    modelArch,
    loadModelInfo,
    loadTestModel,
    reset,
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/shared/composables/useTestModel.ts
git commit -m "feat: add useTestModel composable for test model state"
```

---

### Task 5: Frontend — Create TestSidebar component

**Files:**
- Create: `frontend/src/pages/train-tune/components/TestSidebar.vue`

- [ ] **Step 1: Write the TestSidebar component**

Create `frontend/src/pages/train-tune/components/TestSidebar.vue`:

```vue
<script setup lang="ts">
import { useInferenceStore } from '../../../shared/stores/inference'
import { useTestModel } from '../../../shared/composables/useTestModel'
import { useDatasetStore } from '../../../shared/stores/dataset'
import { computed } from 'vue'

const store = useInferenceStore()
const { testModelInfo, loaded, loading, error: modelError, classNames, modelArch } = useTestModel()
const datasetStore = useDatasetStore()

const canRun = computed(() => {
  if (store.isRunning) return false
  if (store.mediaMode === 'image' && !store.file) return false
  if (store.mediaMode === 'video' && !store.file) return false
  if (store.mediaMode === 'rtsp' && !store.rtspUrl.trim()) return false
  return loaded.value
})

function runInference() {
  // For custom models, we use 'free' prompt type since the model has baked-in classes
  store.inferenceMode = 'free'
  store.runInference()
}
</script>

<template>
  <aside class="w-[260px] shrink-0 border-r border-hairline bg-canvas flex flex-col overflow-y-auto">
    <div class="p-3 space-y-3 flex-1">
      <!-- Model info card -->
      <div v-if="testModelInfo" class="rounded-lg border border-hairline bg-surface-card p-3 space-y-2">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full shrink-0" :class="loaded ? 'bg-emerald-500' : loading ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'" />
          <span class="text-xs font-medium uppercase tracking-wider" :class="loaded ? 'text-emerald-600' : 'text-ink-mute'">
            {{ loaded ? 'Model Loaded' : loading ? 'Loading...' : 'Not Loaded' }}
          </span>
        </div>
        <div class="text-sm font-medium text-ink truncate">{{ testModelInfo.model_name }}</div>
        <div class="text-xs text-ink-mute">{{ modelArch }} · {{ classNames.length }} classes</div>
        <div v-if="testModelInfo.metrics_best" class="text-xs text-ink-mute">
          mAP50: {{ testModelInfo.metrics_best.map50 }}
        </div>
        <div class="flex flex-wrap gap-1 pt-1">
          <span v-for="cls in classNames" :key="cls" class="px-1.5 py-0.5 text-[10px] rounded bg-canvas-soft border border-hairline text-ink-mute">{{ cls }}</span>
        </div>
      </div>
      <p v-if="modelError" class="text-xs text-red-500">{{ modelError }}</p>

      <!-- Media input -->
      <div class="space-y-2">
        <p class="text-xs font-medium uppercase tracking-wider text-ink-mute">Media Input</p>
        <div class="flex gap-1">
          <button
            v-for="mode in (['image', 'video', 'rtsp'] as const)"
            :key="mode"
            class="flex-1 px-2 py-1.5 text-xs font-medium rounded border transition-colors cursor-pointer"
            :class="store.mediaMode === mode ? 'border-primary bg-primary/10 text-primary-deep' : 'border-hairline text-ink-mute hover:bg-canvas-soft'"
            @click="store.selectMediaMode(mode)"
          >
            {{ mode === 'image' ? 'Image' : mode === 'video' ? 'Video' : 'RTSP' }}
          </button>
        </div>

        <!-- Image upload -->
        <div v-if="store.mediaMode === 'image'" class="relative">
          <input
            type="file"
            accept="image/jpeg,image/png"
            class="w-full text-xs file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-canvas-soft file:text-ink-mute hover:file:bg-canvas file:cursor-pointer"
            @change="(e: Event) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) store.file = f }"
          />
          <p v-if="store.file" class="text-xs text-ink-mute mt-1 truncate">{{ store.file.name }}</p>
        </div>

        <!-- Video upload -->
        <div v-else-if="store.mediaMode === 'video'" class="relative">
          <input
            type="file"
            accept="video/mp4,video/avi,video/quicktime"
            class="w-full text-xs file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-canvas-soft file:text-ink-mute hover:file:bg-canvas file:cursor-pointer"
            @change="(e: Event) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) store.file = f }"
          />
          <p v-if="store.file" class="text-xs text-ink-mute mt-1 truncate">{{ store.file.name }}</p>
        </div>

        <!-- RTSP input -->
        <div v-else class="space-y-1">
          <input
            v-model="store.rtspUrl"
            type="text"
            placeholder="rtsp://..."
            class="w-full text-xs px-2 py-1.5 rounded border border-hairline bg-canvas text-ink"
          />
        </div>
      </div>

      <!-- Confidence slider -->
      <div class="space-y-1">
        <div class="flex items-center justify-between">
          <p class="text-xs text-ink-mute">Confidence</p>
          <span class="text-xs font-mono text-ink-mute">{{ store.confidence.toFixed(2) }}</span>
        </div>
        <input
          v-model.number="store.confidence"
          type="range"
          min="0.05"
          max="0.95"
          step="0.05"
          class="w-full h-1.5 rounded-full appearance-none bg-hairline-cool accent-primary cursor-pointer"
        />
      </div>

      <!-- Display toggles -->
      <div class="space-y-1.5">
        <label class="flex items-center gap-2 text-xs text-ink-mute cursor-pointer">
          <input v-model="store.showLabels" type="checkbox" class="accent-primary" />
          Show Labels
        </label>
        <label class="flex items-center gap-2 text-xs text-ink-mute cursor-pointer">
          <input v-model="store.showBbox" type="checkbox" class="accent-primary" />
          Show BBox
        </label>
        <label class="flex items-center gap-2 text-xs text-ink-mute cursor-pointer">
          <input v-model="store.showMasks" type="checkbox" class="accent-primary" />
          Show Masks
        </label>
      </div>
    </div>

    <!-- Action buttons (sticky bottom) -->
    <div class="p-3 border-t border-hairline space-y-2">
      <button
        class="w-full py-2 text-sm font-medium rounded-md text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        :class="store.isRunning ? 'bg-red-500 hover:bg-red-600' : 'bg-emerald-500 hover:bg-emerald-600'"
        :disabled="!canRun && !store.isRunning"
        @click="store.isRunning ? store.stopInference() : runInference()"
      >
        {{ store.isRunning ? 'Stop' : 'Run Inference' }}
      </button>
      <button
        class="w-full py-2 text-sm font-medium rounded-md bg-blue-500 hover:bg-blue-600 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!store.detections.length"
        @click="datasetStore.autoLabelActive = true"
      >
        Save to Dataset
      </button>
    </div>
  </aside>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/train-tune/components/TestSidebar.vue
git commit -m "feat: add TestSidebar component with compact model info and media input"
```

---

### Task 6: Frontend — Create TestModelPage

**Files:**
- Create: `frontend/src/pages/train-tune/TestModelPage.vue`

- [ ] **Step 1: Write TestModelPage**

Create `frontend/src/pages/train-tune/TestModelPage.vue`:

```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useInferenceStore } from '../../shared/stores/inference'
import { useTestModel } from '../../shared/composables/useTestModel'
import TestSidebar from './components/TestSidebar.vue'
import Viewer from '../workspace/components/Viewer.vue'
import AutoLabelModal from '../workspace/components/AutoLabelModal.vue'

const props = defineProps<{ modelId: string }>()

const store = useInferenceStore()
const { loadTestModel, loaded, reset } = useTestModel()

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

onMounted(async () => {
  store.reset()
  store.inferenceMode = 'free'
  await loadTestModel(props.modelId)
})

onUnmounted(() => {
  store.reset()
  reset()
})
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas text-ink">
    <!-- Header -->
    <header class="flex items-center justify-between px-4 h-12 border-b border-hairline bg-canvas shrink-0">
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-1.5 text-xs font-medium text-primary-deep cursor-pointer hover:underline"
          @click="navigate('/train-tune/results/' + props.modelId)"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6" /></svg>
          <span>Back to Results</span>
        </button>
        <span class="text-ink-mute">|</span>
        <span class="text-sm font-medium text-ink">Test Model</span>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full"
          :class="loaded ? 'bg-emerald-500' : 'bg-yellow-500'"
        />
        <span class="text-xs text-ink-mute">{{ loaded ? 'Model Ready' : 'Loading Model...' }}</span>
      </div>
    </header>

    <!-- Body: Sidebar + Viewer -->
    <div class="flex flex-1 min-h-0 overflow-hidden">
      <TestSidebar />
      <Viewer />
    </div>

    <!-- Auto-label modal (reused from workspace) -->
    <AutoLabelModal />
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/train-tune/TestModelPage.vue
git commit -m "feat: add TestModelPage with sidebar, viewer, and auto-label modal"
```

---

### Task 7: Frontend — Wire up routing and "Test Model" button

**Files:**
- Modify: `frontend/src/app/App.vue:1-31`
- Modify: `frontend/src/pages/train-tune/TrainTunePage.vue:60-64` (route detection) and line 873 (Test Model button)

- [ ] **Step 1: Add TestModelPage import and route in App.vue**

Add import at the top of the `<script setup>` section in `frontend/src/app/App.vue`:

```typescript
import TestModelPage from '../pages/train-tune/TestModelPage.vue'
```

Update the route detection. The `path.startsWith('/train-tune')` check needs to handle the new test route before the generic catch-all. Replace the current route logic in the template:

```html
<template>
  <div class="h-screen flex flex-col bg-canvas">
    <DatasetsPage v-if="path === '/datasets'" />
    <TestModelPage v-else-if="path.match(/^\/train-tune\/test\/[^/]+$/)" :model-id="path.split('/').filter(Boolean)[2]" />
    <TrainTunePage v-else-if="path.startsWith('/train-tune')" :path="path" />
    <WorkspacePage v-else-if="path === '/workspace' && store.modelLoaded" />
    <ModeSelectPage v-else />
  </div>
</template>
```

Note: `TestModelPage` must come before `TrainTunePage` since both match `/train-tune/*`.

- [ ] **Step 2: Add "Test Model" button on results page in TrainTunePage.vue**

In `TrainTunePage.vue`, find the results header action area (around line 872-876). Add a "Test Model" button next to the existing "Delete Model" button:

Find this block:
```html
<div class="flex items-center gap-(--spacing-sm)">
  <span class="dataset-status-pill is-completed">{{ trainingStore.selectedModel.status }}</span>
  <button class="dataset-secondary-button" @click="requestModelDelete(trainingStore.selectedModel)">Delete Model</button>
</div>
```

Replace with:
```html
<div class="flex items-center gap-(--spacing-sm)">
  <span class="dataset-status-pill is-completed">{{ trainingStore.selectedModel.status }}</span>
  <button class="dataset-primary-button" @click="navigate(`/train-tune/test/${trainingStore.selectedModel.id}`)">Test Model</button>
  <button class="dataset-secondary-button" @click="requestModelDelete(trainingStore.selectedModel)">Delete Model</button>
</div>
```

The `navigate()` function already exists in `TrainTunePage.vue` (line 55-58).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/App.vue frontend/src/pages/train-tune/TrainTunePage.vue
git commit -m "feat: wire up /train-tune/test/:modelId route and add Test Model button"
```

---

### Task 8: Frontend — Fix inference store for custom model flow

**Files:**
- Modify: `frontend/src/shared/stores/inference.ts:197-213`

- [ ] **Step 1: Update `buildPromptParams()` to handle custom model mode**

The `buildPromptParams()` method currently only handles `free` and prompt modes. When `inferenceMode` is `'free'`, it sends `promptType: 'free'` which works for custom models too (the backend `predict_free` method just calls `model.predict()` without setting classes, which is exactly what we want for custom models).

However, verify that `detectImage` sends `promptType: 'free'` correctly when `inferenceMode` is `'free'`. Looking at the existing code:

```typescript
function buildPromptParams() {
  const effectivePromptType = inferenceMode.value === 'free' ? 'free' as const : promptMode.value
  return {
    promptType: effectivePromptType,
    labels: effectivePromptType === 'text' ? labels.value : undefined,
    ...
  }
}
```

This already works — when `inferenceMode` is `'free'`, `promptType` is `'free'`, no labels needed. The backend `predict_free` method doesn't need labels. For custom models loaded via `load_custom_model`, the model already has its classes.

But the backend detection endpoint `POST /api/detect/image` dispatches to `predict_free` when `prompt_type == 'free'`. For custom models, we need to dispatch to `predict_text` instead (with empty labels, since classes are baked in). Actually, looking at the backend `predict_text` change in Task 1 — when `current_mode == "custom"`, it skips `set_classes` and just runs predict. So we should send `promptType: 'text'` with empty labels for custom models.

Wait — `detectImage` only sends labels when `promptType === 'text' && labels`. If labels is empty, the backend `detect/image` endpoint will call `predict_free` anyway. Let's check the detection router.

Read `backend/routers/detection.py` to see how `prompt_type` is dispatched.

**If the detection router dispatches `'free'` → `model_service.predict_free()` and `'text'` → `model_service.predict_text()`**, then for custom models we need `promptType: 'text'` with the model's class names as labels. This ensures `predict_text` is called, which has the custom model shortcut.

Update `buildPromptParams()` in the inference store:

```typescript
function buildPromptParams() {
  const effectivePromptType = inferenceMode.value === 'free' ? 'free' as const : promptMode.value
  return {
    promptType: effectivePromptType,
    labels: effectivePromptType === 'text' ? labels.value : undefined,
    referImage: effectivePromptType === 'visual' ? referImage.value ?? undefined : undefined,
    bboxes: effectivePromptType === 'visual'
      ? annotations.value.map(a => a.bbox) as [number, number, number, number][]
      : undefined,
    vcls: effectivePromptType === 'visual'
      ? annotations.value.map(a => a.label)
      : undefined,
    confidence: confidence.value,
    showLabels: showLabels.value,
    showBbox: showBbox.value,
    showMasks: showMasks.value,
  }
}
```

The TestSidebar already sets `store.inferenceMode = 'free'` before calling `runInference()`. Since `predict_free()` in the custom model case (Task 1) will also work correctly (it just calls `model.predict()` without labels), **no changes are needed to the inference store for the basic flow**.

The only concern: if the detection router's `prompt_type == 'free'` path calls `model_service.predict_free()`, which we need to verify also works for custom models. In Task 1, we only modified `predict_text()` to handle custom models. Let's also make `predict_free()` work:

In `backend/services/model.py`, `predict_free()` already calls `self.model.predict()` directly — no `set_classes` needed. This works for custom models too. No changes needed.

**Conclusion: No changes needed to the inference store.** The existing `'free'` mode flow works correctly for custom models. The TestSidebar sets `inferenceMode = 'free'` and calls `runInference()`, which sends `promptType: 'free'` → backend calls `predict_free()` → model.predict() runs with the custom model's baked-in classes.

- [ ] **Step 2: Commit (if any changes were needed — skip if not)**

No changes needed — skip this commit.

---

### Task 9: End-to-end wiring and test

**Files:** None new (verification only)

- [ ] **Step 1: Start the backend**

```bash
cd /home/gspe-ai3/project_cv/LabelLens && source env/bin/activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 3131
```

- [ ] **Step 2: Start the frontend dev server**

```bash
cd /home/gspe-ai3/project_cv/LabelLens/frontend && npm run dev
```

- [ ] **Step 3: Verify route navigation**

1. Navigate to `/train-tune` — builder page loads
2. Click on a model version in sidebar — results page loads
3. Click "Test Model" button — navigates to `/train-tune/test/:modelId`
4. Verify sidebar shows model info (name, classes, architecture)
5. Click "Back to Results" — returns to results page

- [ ] **Step 4: Verify backend endpoint**

```bash
curl -X POST http://localhost:3131/api/model/load-custom \
  -H "Content-Type: application/json" \
  -d '{"model_id": "<test-model-id>"}'
```

Expected: `{"mode": "custom", "loaded": true, "model_name": "best.pt", "device": "cuda:0", "class_names": [...]}`

- [ ] **Step 5: Verify inference flow**

1. On test page, upload a test image
2. Click "Run Inference"
3. Verify detection results appear in viewer
4. Verify stats grid shows inference time and class counts
5. Click "Save to Dataset" — verify auto-label modal opens

- [ ] **Step 6: Verify video and RTSP**

1. Test with a video file — verify frame-by-frame detection works
2. Test with an RTSP URL — verify live detection works

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete test model page with inference and save-to-dataset"
```

---

## Verification Summary

1. Backend: `POST /api/model/load-custom` loads trained `.pt` weights
2. Frontend: `/train-tune/test/:modelId` renders compact sidebar + workspace viewer
3. Image/video/RTSP inference works with custom model classes
4. Save-to-dataset via existing auto-label modal
5. "Test Model" button on results page navigates to test page
6. Back navigation returns to results page
7. Model loading state (loading/loaded/error) shown in sidebar
