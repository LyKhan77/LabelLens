<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'

const store = useInferenceStore()
</script>

<template>
  <div>
    <p class="text-xs font-medium text-ink-mute uppercase tracking-wider mb-2">
      Step 3 — Settings
    </p>

    <!-- Confidence slider -->
    <div class="mb-3">
      <div class="flex items-center justify-between mb-1">
        <label class="text-sm text-ink">Confidence Threshold</label>
        <span class="text-sm font-mono text-primary">{{ store.confidence.toFixed(2) }}</span>
      </div>
      <input
        v-model.number="store.confidence"
        type="range"
        min="0"
        max="1"
        step="0.05"
        class="w-full h-1.5 rounded-full appearance-none bg-hairline-cool accent-primary cursor-pointer"
      />
    </div>

    <!-- Toggles -->
    <div class="space-y-2 mb-4">
      <label class="flex items-center justify-between">
        <span class="text-sm text-ink">Show Labels</span>
        <button
          class="relative w-9 h-5 rounded-full transition-colors"
          :class="store.showLabels ? 'bg-primary' : 'bg-hairline'"
          @click="store.showLabels = !store.showLabels"
        >
          <span
            class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-canvas shadow transition-transform"
            :class="store.showLabels ? 'translate-x-4' : ''"
          />
        </button>
      </label>

      <label class="flex items-center justify-between">
        <span class="text-sm text-ink">Show Bounding Boxes</span>
        <button
          class="relative w-9 h-5 rounded-full transition-colors"
          :class="store.showBbox ? 'bg-primary' : 'bg-hairline'"
          @click="store.showBbox = !store.showBbox"
        >
          <span
            class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-canvas shadow transition-transform"
            :class="store.showBbox ? 'translate-x-4' : ''"
          />
        </button>
      </label>

      <label class="flex items-center justify-between">
        <span class="text-sm text-ink">Show Masks</span>
        <button
          class="relative w-9 h-5 rounded-full transition-colors"
          :class="store.showMasks ? 'bg-primary' : 'bg-hairline'"
          @click="store.showMasks = !store.showMasks"
        >
          <span
            class="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-canvas shadow transition-transform"
            :class="store.showMasks ? 'translate-x-4' : ''"
          />
        </button>
      </label>
    </div>

    <!-- Action button -->
    <div>
      <button
        v-if="store.isRunning"
        class="w-full px-4 py-2 text-sm font-medium rounded-(--radius-sm) bg-red-500 text-white hover:bg-red-600 transition-colors cursor-pointer"
        @click="store.stopInference()"
      >
        Stop Inference
      </button>
      <button
        v-else
        class="w-full px-4 py-2 text-sm font-medium rounded-(--radius-sm) bg-primary text-on-primary hover:bg-primary-deep transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        :disabled="!store.canRun"
        @click="store.runInference()"
      >
        Start Inference
      </button>
    </div>
  </div>
</template>
