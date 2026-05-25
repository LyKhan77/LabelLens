<script setup lang="ts">
import { useInferenceStore } from '../../../shared/stores/inference'
import { useTestModel } from '../../../shared/composables/useTestModel'
import { useDatasetStore } from '../../../shared/stores/dataset'
import { computed } from 'vue'

const emit = defineEmits<{ openAutoLabel: [] }>()

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
  store.inferenceMode = 'free'
  store.runInference()
}
</script>

<template>
  <aside class="w-65 shrink-0 border-r border-hairline bg-canvas flex flex-col overflow-y-auto">
    <div class="p-3 space-y-3 flex-1">
      <!-- Model info card -->
      <div v-if="testModelInfo" class="rounded-lg border border-hairline bg-canvas-soft p-3 space-y-2">
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
          <span v-for="cls in classNames" :key="cls" class="px-1.5 py-0.5 text-[10px] rounded bg-canvas border border-hairline text-ink-mute">{{ cls }}</span>
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
        <div v-if="store.mediaMode === 'image'">
          <input
            type="file"
            accept="image/jpeg,image/png"
            class="w-full text-xs file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-canvas-soft file:text-ink-mute hover:file:bg-canvas file:cursor-pointer"
            @change="(e: Event) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) store.file = f }"
          />
          <p v-if="store.file" class="text-xs text-ink-mute mt-1 truncate">{{ store.file.name }}</p>
        </div>

        <!-- Video upload -->
        <div v-else-if="store.mediaMode === 'video'">
          <input
            type="file"
            accept="video/mp4,video/avi,video/quicktime"
            class="w-full text-xs file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-canvas-soft file:text-ink-mute hover:file:bg-canvas file:cursor-pointer"
            @change="(e: Event) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) store.file = f }"
          />
          <p v-if="store.file" class="text-xs text-ink-mute mt-1 truncate">{{ store.file.name }}</p>
        </div>

        <!-- RTSP input -->
        <div v-else>
          <input
            v-model="store.rtspUrl"
            type="text"
            placeholder="rtsp://..."
            class="w-full text-xs px-2 py-1.5 rounded border border-hairline bg-canvas text-ink"
          />
        </div>
        <button
          v-if="store.hasMediaInput"
          class="w-full py-1 text-xs font-medium rounded border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
          @click="store.clearMediaInput()"
        >
          Clear Media
        </button>
        <p v-if="store.error && store.canSwitchMediaMode === false" class="text-xs text-red-500">{{ store.error }}</p>
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

      <!-- Auto-label toggle -->
      <div class="space-y-1.5">
        <label class="flex items-center justify-between cursor-pointer">
          <span class="text-xs text-ink-mute">Auto-Label to Dataset</span>
          <button
            type="button"
            role="switch"
            :aria-checked="datasetStore.autoLabelActive"
            class="relative w-8 h-4.5 rounded-full transition-colors cursor-pointer"
            :class="datasetStore.autoLabelActive ? 'bg-primary' : 'bg-hairline-strong'"
            @click="datasetStore.autoLabelActive ? datasetStore.disableAutoLabel() : emit('openAutoLabel')"
          >
            <span
              class="absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full bg-white shadow transition-transform"
              :class="datasetStore.autoLabelActive ? 'translate-x-3.5' : ''"
            />
          </button>
        </label>
        <p v-if="datasetStore.autoLabelActive" class="text-[10px] text-primary">
          {{ datasetStore.autoLabelDataset }} · {{ datasetStore.autoLabelFps }} fps
        </p>
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
    <div class="p-3 border-t border-hairline">
      <button
        class="w-full py-2 text-sm font-medium rounded-md text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        :class="store.isRunning ? 'bg-red-500 hover:bg-red-600' : 'bg-emerald-500 hover:bg-emerald-600'"
        :disabled="!canRun && !store.isRunning"
        @click="store.isRunning ? store.stopInference() : runInference()"
      >
        {{ store.isRunning ? 'Stop' : 'Run Inference' }}
      </button>
    </div>
  </aside>
</template>
