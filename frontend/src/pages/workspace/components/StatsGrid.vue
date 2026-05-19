<script setup lang="ts">
import { computed } from 'vue'
import { useInferenceStore } from '../../../shared/stores/inference'

const store = useInferenceStore()

const fps = computed(() => {
  const ms = store.stats?.inference_ms ?? 0
  return ms > 0 ? (1000 / ms).toFixed(1) : '0'
})

const classCount = computed(() => store.stats ? Object.keys(store.stats.classes_count).length : 0)
</script>

<template>
  <div class="grid grid-cols-2 gap-px overflow-hidden rounded-(--radius-sm) border border-hairline bg-hairline">
    <div class="min-w-0 bg-canvas px-2.5 py-2">
      <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">Objects</p>
      <p class="text-sm font-semibold leading-tight text-ink">{{ store.stats?.total_objects ?? 0 }}</p>
    </div>
    <div class="min-w-0 bg-canvas px-2.5 py-2">
      <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">FPS</p>
      <p class="text-sm font-semibold leading-tight text-ink">{{ fps }}</p>
    </div>
    <div class="min-w-0 bg-canvas px-2.5 py-2">
      <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">Latency</p>
      <p class="text-sm font-semibold leading-tight text-ink">{{ store.stats?.inference_ms?.toFixed(0) ?? '0' }} ms</p>
    </div>
    <div class="min-w-0 bg-canvas px-2.5 py-2">
      <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">Classes</p>
      <p class="text-sm font-semibold leading-tight text-ink">{{ classCount }}</p>
    </div>
  </div>
</template>
