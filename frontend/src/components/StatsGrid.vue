<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'

const store = useInferenceStore()
</script>

<template>
  <div class="grid grid-cols-4 gap-2">
    <div class="p-2 rounded-(--radius-md) bg-canvas border border-hairline text-center">
      <p class="text-lg font-medium text-ink">{{ store.stats?.total_objects ?? 0 }}</p>
      <p class="text-xs text-ink-mute">Objects</p>
    </div>
    <div class="p-2 rounded-(--radius-md) bg-canvas border border-hairline text-center">
      <p class="text-lg font-medium text-ink">{{ store.stats ? (1000 / store.stats.inference_ms).toFixed(1) : '0' }}</p>
      <p class="text-xs text-ink-mute">FPS</p>
    </div>
    <div class="p-2 rounded-(--radius-md) bg-canvas border border-hairline text-center">
      <p class="text-lg font-medium text-ink">{{ store.stats?.inference_ms?.toFixed(0) ?? '0' }}</p>
      <p class="text-xs text-ink-mute">ms/frame</p>
    </div>
    <div class="p-2 rounded-(--radius-md) bg-canvas border border-hairline text-center">
      <p class="text-lg font-medium text-ink">{{ store.stats ? Object.keys(store.stats.classes_count).length : 0 }}</p>
      <p class="text-xs text-ink-mute">Classes</p>
    </div>
  </div>
</template>
