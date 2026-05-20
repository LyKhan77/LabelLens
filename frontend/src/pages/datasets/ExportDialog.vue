<script setup lang="ts">
import { ref } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'

const emit = defineEmits<{ close: [] }>()
const store = useDatasetStore()

const format = ref<'yolo' | 'coco'>('yolo')
const split = ref(0.8)
const exporting = ref(false)

async function doExport() {
  exporting.value = true
  try {
    await store.exportDataset(format.value, split.value)
  } finally {
    exporting.value = false
  }
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="emit('close')">
    <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[360px] border border-hairline">
      <h3 class="text-[16px] font-medium text-ink mb-(--spacing-lg)">Export Dataset</h3>

      <!-- Format selector -->
      <div class="mb-(--spacing-lg)">
        <div class="text-[12px] text-ink-mute uppercase tracking-wide mb-2">Format</div>
        <div class="flex gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" v-model="format" value="yolo" class="accent-[#3ecf8e]" />
            <span class="text-[13px] text-ink">YOLO TXT</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" v-model="format" value="coco" class="accent-[#3ecf8e]" />
            <span class="text-[13px] text-ink">COCO JSON</span>
          </label>
        </div>
      </div>

      <!-- Train/val split -->
      <div class="mb-(--spacing-lg)">
        <div class="flex justify-between mb-2">
          <span class="text-[12px] text-ink-mute uppercase tracking-wide">Train / Val Split</span>
          <span class="text-[12px] text-ink font-mono">{{ Math.round(split * 100) }} / {{ Math.round((1 - split) * 100) }}</span>
        </div>
        <input
          type="range"
          v-model.number="split"
          min="0.7"
          max="0.95"
          step="0.05"
          class="w-full accent-[#3ecf8e]"
        />
      </div>

      <!-- Actions -->
      <div class="flex gap-3 justify-end">
        <button
          @click="emit('close')"
          class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5"
        >
          Cancel
        </button>
        <button
          @click="doExport"
          :disabled="exporting"
          class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
        >
          {{ exporting ? 'Exporting...' : 'Download ZIP' }}
        </button>
      </div>
    </div>
  </div>
</template>
