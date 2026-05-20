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
    enter-from-class="opacity-0 scale-[0.98]"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition ease-in duration-150"
    leave-to-class="opacity-0 scale-[0.98]"
  >
    <div class="dataset-dialog-backdrop" @click.self="emit('close')">
      <section class="dataset-export-dialog">
        <header class="dataset-modal-header">
          <div>
            <h3 class="dataset-modal-title">Export Dataset</h3>
            <p class="dataset-modal-copy">Download accepted annotations for training.</p>
          </div>
          <button class="dataset-modal-close" @click="emit('close')" aria-label="Close export dialog">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </header>

        <div class="dataset-modal-body dataset-form-stack">
          <div>
            <div class="dataset-field-label">Format</div>
            <div class="dataset-export-options">
              <label :class="['dataset-choice-card', { 'is-active': format === 'yolo' }]">
                <input v-model="format" type="radio" value="yolo" />
                <span>
                  <strong>YOLO TXT</strong>
                  <small>Images, labels, and train/val split.</small>
                </span>
              </label>
              <label :class="['dataset-choice-card', { 'is-active': format === 'coco' }]">
                <input v-model="format" type="radio" value="coco" />
                <span>
                  <strong>COCO JSON</strong>
                  <small>Single annotation file for COCO tooling.</small>
                </span>
              </label>
            </div>
          </div>

          <div>
            <div class="dataset-field-row">
              <span class="dataset-field-label">Train / Val Split</span>
              <span class="dataset-field-value">{{ Math.round(split * 100) }} / {{ Math.round((1 - split) * 100) }}</span>
            </div>
            <input
              v-model.number="split"
              type="range"
              min="0.7"
              max="0.95"
              step="0.05"
              class="dataset-range"
            />
          </div>
        </div>

        <footer class="dataset-modal-footer">
          <button class="dataset-secondary-button" @click="emit('close')">Cancel</button>
          <button
            class="dataset-primary-button"
            :disabled="exporting"
            @click="doExport"
          >
            {{ exporting ? 'Exporting...' : 'Download ZIP' }}
          </button>
        </footer>
      </section>
    </div>
  </Transition>
</template>
