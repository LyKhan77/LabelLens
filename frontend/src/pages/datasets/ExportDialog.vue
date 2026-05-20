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
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition ease-in duration-150"
    leave-to-class="opacity-0"
  >
    <div class="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" @click.self="emit('close')">
      <div class="bg-canvas rounded-(--radius-xl) w-full max-w-[400px] border border-hairline shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]">
        <div class="flex items-start justify-between p-6 pb-0">
          <div>
            <h3 class="text-[18px] font-medium text-ink tracking-[-0.3px]">Export Dataset</h3>
            <p class="text-[12px] text-ink-mute mt-1">Download annotations for training</p>
          </div>
          <button class="w-8 h-8 rounded-(--radius-sm) flex items-center justify-center text-ink-faint hover:bg-canvas-soft hover:text-ink transition-colors cursor-pointer" @click="emit('close')">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>

        <div class="p-6">
          <!-- Format selector -->
          <div class="mb-5">
            <div class="text-[11px] text-ink-mute uppercase tracking-wide mb-2.5">Format</div>
            <div class="flex gap-4">
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
          <div class="mb-0">
            <div class="flex justify-between mb-2">
              <span class="text-[11px] text-ink-mute uppercase tracking-wide">Train / Val Split</span>
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
        </div>

        <!-- Actions -->
        <div class="flex justify-between px-6 pb-6">
          <button
            @click="emit('close')"
            class="px-4 py-2.5 text-[13px] text-ink-mute rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            @click="doExport"
            :disabled="exporting"
            class="px-5 py-2.5 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep disabled:opacity-50 transition-colors cursor-pointer"
          >
            {{ exporting ? 'Exporting...' : 'Download ZIP' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
