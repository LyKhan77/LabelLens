<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'

const store = useInferenceStore()
</script>

<template>
  <div class="min-h-0">
    <p class="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-ink-mute">Detection Log</p>
    <div class="max-h-56 overflow-y-auto pr-1 space-y-0.5">
      <div
        v-for="(det, idx) in store.detections"
        :key="idx"
        class="flex items-center justify-between gap-3 rounded-(--radius-sm) px-1.5 py-1 text-xs hover:bg-canvas-soft"
      >
        <span class="min-w-0 truncate text-ink">{{ det.label }}</span>
        <span class="shrink-0 font-mono text-primary">{{ (det.confidence * 100).toFixed(1) }}%</span>
      </div>
      <p v-if="store.detections.length === 0" class="text-xs text-ink-faint">No detections yet</p>
    </div>
  </div>
</template>
