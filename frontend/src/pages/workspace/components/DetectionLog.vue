<script setup lang="ts">
import { computed } from 'vue'
import { useInferenceStore } from '../../../shared/stores/inference'

const store = useInferenceStore()

const top5 = computed(() => store.classification?.top5 ?? [])
const isClassify = computed(() => top5.value.length > 0)
</script>

<template>
  <div class="min-h-0">
    <p class="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-ink-mute">
      {{ isClassify ? 'Predictions' : 'Detection Log' }}
    </p>
    <div class="max-h-56 overflow-y-auto pr-1 space-y-0.5">
      <!-- Classification: Top-5 predictions -->
      <template v-if="isClassify">
        <div
          v-for="(p, idx) in top5"
          :key="idx"
          class="flex items-center justify-between gap-3 rounded-(--radius-sm) px-1.5 py-1 text-xs hover:bg-canvas-soft"
        >
          <span class="min-w-0 truncate" :class="idx === 0 ? 'font-semibold text-ink' : 'text-ink-mute'">{{ p.label }}</span>
          <span class="shrink-0 font-mono" :class="idx === 0 ? 'font-semibold text-primary' : 'text-ink-mute'">{{ (p.confidence * 100).toFixed(1) }}%</span>
        </div>
      </template>

      <!-- Detection / Segmentation / Pose -->
      <template v-else>
        <div
          v-for="(det, idx) in store.detections"
          :key="idx"
          class="flex items-center justify-between gap-3 rounded-(--radius-sm) px-1.5 py-1 text-xs hover:bg-canvas-soft"
        >
          <span class="min-w-0 truncate text-ink">
            {{ det.label }}
            <span v-if="det.keypoints?.length" class="text-ink-faint">· {{ det.keypoints.length }} kpts</span>
          </span>
          <span class="shrink-0 font-mono text-primary">{{ (det.confidence * 100).toFixed(1) }}%</span>
        </div>
        <p v-if="store.detections.length === 0" class="text-xs text-ink-faint">No detections yet</p>
      </template>
    </div>
  </div>
</template>
