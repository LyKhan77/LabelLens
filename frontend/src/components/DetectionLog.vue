<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'

const store = useInferenceStore()
</script>

<template>
  <div>
    <p class="text-xs font-medium text-ink-mute uppercase tracking-wider mb-1.5">Detection Log</p>
    <div class="max-h-32 overflow-y-auto space-y-0.5">
      <div
        v-for="(det, idx) in store.detections"
        :key="idx"
        class="flex items-center justify-between text-xs py-0.5"
      >
        <span class="text-ink">{{ det.label }}</span>
        <span class="font-mono text-primary">{{ (det.confidence * 100).toFixed(1) }}%</span>
      </div>
      <p v-if="store.detections.length === 0" class="text-xs text-ink-faint">No detections yet</p>
    </div>
  </div>
</template>
