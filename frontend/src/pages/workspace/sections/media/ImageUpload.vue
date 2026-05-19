<script setup lang="ts">
import { ref } from 'vue'
import { useInferenceStore } from '../../../../shared/stores/inference'

const store = useInferenceStore()
const isDragOver = ref(false)

function handleFile(file: File) {
  const validTypes = ['image/jpeg', 'image/png', 'image/jpg']
  if (!validTypes.includes(file.type)) return
  if (file.size > 10 * 1024 * 1024) return
  store.file = file
}

function onFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) handleFile(target.files[0])
}

function onDrop(e: DragEvent) {
  isDragOver.value = false
  const file = e.dataTransfer?.files[0]
  if (file) handleFile(file)
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = true
}

function onDragLeave() {
  isDragOver.value = false
}
</script>

<template>
  <div>
    <div
      v-if="!store.file"
      class="border-2 border-dashed rounded-(--radius-md) p-6 text-center transition-colors"
      :class="isDragOver ? 'border-primary bg-primary/5' : 'border-hairline hover:border-hairline-strong'"
      @drop="onDrop"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
    >
      <svg class="w-8 h-8 mx-auto mb-2 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <p class="text-sm text-ink-mute mb-1">Drop image here</p>
      <p class="text-xs text-ink-faint mb-2">JPG, PNG — max 10MB</p>
      <label class="inline-block px-3 py-1.5 text-sm font-medium rounded-(--radius-sm) bg-primary text-on-primary cursor-pointer hover:bg-primary-deep transition-colors">
        Browse
        <input type="file" accept=".jpg,.jpeg,.png" class="hidden" @change="onFileInput" />
      </label>
    </div>

    <div v-else class="flex items-center gap-2 p-2 rounded-(--radius-md) bg-canvas-soft">
      <div class="flex-1 min-w-0">
        <p class="text-sm text-ink truncate">{{ store.file.name }}</p>
        <p class="text-xs text-ink-faint">{{ (store.file.size / 1024).toFixed(1) }} KB</p>
      </div>
      <button
        class="text-xs text-ink-mute hover:text-red-500 transition-colors"
        @click="store.clearMediaInput()"
      >
        Clear Media
      </button>
    </div>
  </div>
</template>
