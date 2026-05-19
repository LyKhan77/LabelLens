<script setup lang="ts">
import { ref, watch } from 'vue'
import { useInferenceStore } from '../../../../shared/stores/inference'
import BBoxAnnotation from './BBoxAnnotation.vue'

const store = useInferenceStore()
const imageSrc = ref('')
const isDragOver = ref(false)

function loadPreview(file: File) {
  const reader = new FileReader()
  reader.onload = (e) => {
    imageSrc.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
}

function handleFile(file: File) {
  if (!file.type.startsWith('image/')) return
  store.referImage = file
  store.clearAnnotations()
  loadPreview(file)
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

watch(() => store.referImage, (newFile) => {
  if (newFile) {
    loadPreview(newFile)
  } else {
    imageSrc.value = ''
  }
}, { immediate: true })
</script>

<template>
  <div>
    <label class="text-sm font-medium text-ink mb-1 block">
      Visual Prompt
    </label>
    <p class="text-xs text-ink-mute mb-2">
      Upload a reference image and draw bounding boxes on objects to detect
    </p>

    <!-- Upload zone (when no image) -->
    <div
      v-if="!imageSrc"
      class="border-2 border-dashed rounded-(--radius-md) p-6 text-center transition-colors"
      :class="isDragOver ? 'border-primary bg-primary/5' : 'border-hairline hover:border-hairline-strong'"
      @drop="onDrop"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
    >
      <svg class="w-8 h-8 mx-auto mb-2 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <path d="m21 15-5-5L5 21" />
      </svg>
      <p class="text-sm text-ink-mute mb-1">Drop reference image here</p>
      <label class="inline-block px-3 py-1.5 text-sm font-medium rounded-(--radius-sm) bg-primary text-on-primary cursor-pointer hover:bg-primary-deep transition-colors">
        Browse
        <input type="file" accept="image/*" class="hidden" @change="onFileInput" />
      </label>
    </div>

    <!-- Annotation canvas (when image loaded) -->
    <div v-else>
      <BBoxAnnotation
        :image-src="imageSrc"
        :annotations="store.annotations"
        @add="store.addAnnotation($event)"
        @remove="store.removeAnnotation($event)"
      />

      <!-- Annotation list -->
      <div v-if="store.annotations.length > 0" class="mt-2 space-y-1">
        <div
          v-for="(ann, idx) in store.annotations"
          :key="idx"
          class="flex items-center justify-between px-2 py-1 rounded-(--radius-xs) bg-canvas-soft text-sm"
        >
          <span class="text-ink">
            <span class="inline-block w-2 h-2 rounded-full bg-primary mr-1.5" />
            {{ ann.label }}
            <span class="text-ink-faint text-xs ml-1">
              [{{ ann.bbox.join(', ') }}]
            </span>
          </span>
          <button
            class="text-ink-mute hover:text-red-500 transition-colors text-xs"
            @click="store.removeAnnotation(idx)"
          >
            Remove
          </button>
        </div>
      </div>

      <!-- Change image -->
      <label class="mt-2 inline-block text-xs text-ink-mute hover:text-ink cursor-pointer transition-colors">
        Change reference image
        <input type="file" accept="image/*" class="hidden" @change="onFileInput" />
      </label>
    </div>
  </div>
</template>
