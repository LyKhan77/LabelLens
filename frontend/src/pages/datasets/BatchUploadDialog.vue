<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

const files = ref<File[]>([])
const labels = ref('')
const sampleFps = ref(1)
const uploading = ref(false)
const progress = ref(0)
const result = ref<{ processed: number } | null>(null)

const modelReady = computed(() => inferenceStore.modelLoaded)
const promptMode = computed(() => inferenceStore.promptMode)

const isDragging = ref(false)

function onDrop(e: DragEvent) {
  isDragging.value = false
  if (!e.dataTransfer) return
  files.value = [...files.value, ...Array.from(e.dataTransfer.files)]
}

function removeFile(idx: number) {
  files.value.splice(idx, 1)
}

async function startBatch() {
  if (!files.value.length || !modelReady.value) return

  uploading.value = true
  progress.value = 0
  result.value = null

  try {
    const labelList = labels.value.split(',').map((s) => s.trim()).filter(Boolean)
    const res = await datasetStore.batchUpload(
      files.value,
      promptMode.value === 'free' ? 'free' : 'text',
      labelList,
      inferenceStore.confidence,
    )
    result.value = { processed: res.processed }
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="emit('close')">
    <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[480px] border border-hairline max-h-[80vh] overflow-y-auto">
      <h3 class="text-[16px] font-medium text-ink mb-(--spacing-lg)">Batch Upload &amp; Auto-Label</h3>

      <!-- Model status -->
      <div class="mb-(--spacing-md) p-3 rounded-(--radius-md) text-[12px]" :class="modelReady ? 'bg-primary/10 text-primary' : 'bg-red-500/10 text-red-400'">
        {{ modelReady ? `Model ready (${promptMode} mode)` : 'No model loaded — load a model first' }}
      </div>

      <!-- Drop zone -->
      <div
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop="onDrop"
        class="border-2 border-dashed rounded-(--radius-md) p-6 text-center mb-(--spacing-md) transition-colors cursor-pointer"
        :class="isDragging ? 'border-primary bg-primary/5' : 'border-hairline'"
        @click="($refs.fileInput as HTMLInputElement)?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          multiple
          accept="image/*,video/*"
          class="hidden"
          @change="(e) => files.push(...Array.from((e.target as HTMLInputElement).files ?? []))"
        />
        <p class="text-[13px] text-ink-faint">Drop images or videos here, or click to browse</p>
      </div>

      <!-- File list -->
      <div v-if="files.length" class="mb-(--spacing-md) max-h-[120px] overflow-y-auto">
        <div v-for="(f, i) in files" :key="f.name + i" class="flex items-center justify-between py-1 text-[12px]">
          <span class="text-ink-mute truncate">{{ f.name }}</span>
          <button @click="removeFile(i)" class="text-ink-faint hover:text-red-400 ml-2">
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
      </div>

      <!-- Labels input (for text mode) -->
      <div v-if="promptMode === 'text'" class="mb-(--spacing-md)">
        <label class="block">
          <span class="text-[12px] text-ink-mute uppercase tracking-wide">Labels (comma-separated)</span>
          <input
            v-model="labels"
            placeholder="defect, scratch, dent"
            class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
          />
        </label>
      </div>

      <!-- Frame rate for video -->
      <div class="mb-(--spacing-lg)">
        <label class="block">
          <div class="flex justify-between">
            <span class="text-[12px] text-ink-mute uppercase tracking-wide">Frame Rate (for video)</span>
            <span class="text-[12px] text-ink font-mono">{{ sampleFps }} fps</span>
          </div>
          <input
            type="range"
            v-model.number="sampleFps"
            min="0.5"
            max="10"
            step="0.5"
            class="w-full mt-1 accent-[#3ecf8e]"
          />
        </label>
      </div>

      <!-- Progress -->
      <div v-if="uploading" class="mb-(--spacing-md)">
        <div class="w-full bg-ink/5 rounded-full h-1.5">
          <div class="bg-primary h-1.5 rounded-full transition-all" style="width: 50%" />
        </div>
        <p class="text-[11px] text-ink-faint mt-1 text-center">Processing...</p>
      </div>

      <!-- Result -->
      <div v-if="result" class="mb-(--spacing-md) p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px] text-center">
        {{ result.processed }} images processed and saved
      </div>

      <!-- Actions -->
      <div class="flex gap-3 justify-end">
        <button
          @click="emit('close')"
          class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5"
        >
          {{ result ? 'Done' : 'Cancel' }}
        </button>
        <button
          v-if="!result"
          @click="startBatch"
          :disabled="uploading || !files.length || !modelReady"
          class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
        >
          {{ uploading ? 'Processing...' : 'Start' }}
        </button>
      </div>
    </div>
  </div>
</template>
