<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

// Phase: 'upload' | 'label'
const phase = ref<'upload' | 'label'>('upload')

// Upload phase state
const files = ref<File[]>([])
const sampleFps = ref(1)
const uploading = ref(false)
const uploadResult = ref<{ uploaded: number } | null>(null)

// Label phase state
const labels = ref('')
const labeling = ref(false)
const labelResult = ref<{ labeled: number; total_unlabeled: number } | null>(null)

// Model loading
const loadingModel = ref(false)
const selectedMode = ref<'free' | 'prompt'>('free')

const modelReady = computed(() => inferenceStore.modelLoaded)
const promptMode = computed(() => inferenceStore.promptMode)
const isDragging = ref(false)

async function loadModel(mode: 'free' | 'prompt') {
  loadingModel.value = true
  try {
    await inferenceStore.selectMode(mode)
  } finally {
    loadingModel.value = false
  }
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  if (!e.dataTransfer) return
  files.value = [...files.value, ...Array.from(e.dataTransfer.files)]
}

function removeFile(idx: number) {
  files.value.splice(idx, 1)
}

// Phase 1: Upload raw images
async function startUpload() {
  if (!files.value.length) return
  uploading.value = true
  try {
    // Check if any file is a video
    const hasVideo = files.value.some((f) => f.type.startsWith('video/'))
    if (hasVideo) {
      const videoFile = files.value.find((f) => f.type.startsWith('video/'))!
      const result = await datasetStore.uploadStream({
        file: videoFile,
        sampleFps: sampleFps.value,
      })
      uploadResult.value = { uploaded: result.uploaded }
    } else {
      const result = await datasetStore.uploadRaw(files.value)
      uploadResult.value = { uploaded: result.uploaded }
    }
  } finally {
    uploading.value = false
  }
}

// Move to label phase
function goToLabelPhase() {
  phase.value = 'label'
}

// Phase 2: Run batch labeling
async function startLabeling() {
  if (!modelReady.value) return
  labeling.value = true
  labelResult.value = null

  try {
    const labelList = labels.value.split(',').map((s) => s.trim()).filter(Boolean)
    const result = await datasetStore.labelImages(
      promptMode.value === 'free' ? 'free' : 'text',
      labelList,
      inferenceStore.confidence,
    )
    labelResult.value = { labeled: result.labeled, total_unlabeled: result.total_unlabeled }
  } finally {
    labeling.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="close">
    <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[480px] border border-hairline max-h-[80vh] overflow-y-auto">
      <!-- Phase indicator -->
      <div class="flex items-center gap-2 mb-(--spacing-lg)">
        <div
          class="flex items-center gap-1.5 px-2 py-1 rounded-(--radius-md) text-[11px] font-medium"
          :class="phase === 'upload' ? 'bg-primary/10 text-primary' : 'text-ink-faint'"
        >
          <span class="w-4 h-4 rounded-full text-[10px] flex items-center justify-center" :class="phase === 'upload' ? 'bg-primary text-white' : 'bg-ink/10'">1</span>
          Upload Data
        </div>
        <div class="w-6 h-px bg-hairline" />
        <div
          class="flex items-center gap-1.5 px-2 py-1 rounded-(--radius-md) text-[11px] font-medium"
          :class="phase === 'label' ? 'bg-primary/10 text-primary' : 'text-ink-faint'"
        >
          <span class="w-4 h-4 rounded-full text-[10px] flex items-center justify-center" :class="phase === 'label' ? 'bg-primary text-white' : 'bg-ink/10'">2</span>
          Auto-Label
        </div>
      </div>

      <!-- PHASE 1: Upload -->
      <template v-if="phase === 'upload'">
        <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Upload Images / Video</h3>

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
          <p class="text-[13px] text-ink-faint">Drop images or video here, or click to browse</p>
        </div>

        <!-- File list -->
        <div v-if="files.length" class="mb-(--spacing-md) max-h-[100px] overflow-y-auto">
          <div v-for="(f, i) in files" :key="f.name + i" class="flex items-center justify-between py-1 text-[12px]">
            <span class="text-ink-mute truncate">{{ f.name }}</span>
            <button @click="removeFile(i)" class="text-ink-faint hover:text-red-400 ml-2">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>
        </div>

        <!-- Frame rate for video -->
        <div class="mb-(--spacing-lg)">
          <label class="block">
            <div class="flex justify-between">
              <span class="text-[12px] text-ink-mute uppercase tracking-wide">Frame Rate (video/RTSP)</span>
              <span class="text-[12px] text-ink font-mono">{{ sampleFps }} fps</span>
            </div>
            <input type="range" v-model.number="sampleFps" min="0.5" max="10" step="0.5" class="w-full mt-1 accent-[#3ecf8e]" />
          </label>
        </div>

        <!-- Upload result -->
        <div v-if="uploadResult" class="mb-(--spacing-md) p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px] text-center">
          {{ uploadResult.uploaded }} images uploaded successfully
        </div>

        <!-- Actions -->
        <div class="flex gap-3 justify-end">
          <button @click="close" class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5">
            Cancel
          </button>
          <button
            v-if="!uploadResult"
            @click="startUpload"
            :disabled="uploading || !files.length"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
          >
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
          <button
            v-else
            @click="goToLabelPhase"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90"
          >
            Next: Auto-Label →
          </button>
        </div>
      </template>

      <!-- PHASE 2: Label -->
      <template v-if="phase === 'label'">
        <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Auto-Label Images</h3>

        <!-- Model status -->
        <div v-if="modelReady" class="mb-(--spacing-md) p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px]">
          Model ready ({{ inferenceStore.inferenceMode }} mode)
        </div>

        <!-- Model loader (shown when no model) -->
        <div v-else class="mb-(--spacing-md) p-4 rounded-(--radius-md) bg-ink/[0.03] border border-hairline">
          <p class="text-[12px] text-ink-mute mb-3">Load a model to start labeling:</p>
          <div class="flex gap-2">
            <button
              @click="loadModel('free')"
              :disabled="loadingModel"
              class="flex-1 flex flex-col items-center p-3 rounded-(--radius-md) border transition-colors cursor-pointer"
              :class="[
                loadingModel ? 'opacity-50' : '',
                selectedMode === 'free' && !loadingModel
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-hairline hover:border-hairline-strong text-ink-mute'
              ]"
              @mouseenter="() => { if (!loadingModel) selectedMode = 'free' }"
            >
              <svg class="w-5 h-5 mb-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <span class="text-[12px] font-medium">Free Inference</span>
              <span class="text-[10px] text-ink-faint">1200+ classes</span>
            </button>
            <button
              @click="loadModel('prompt')"
              :disabled="loadingModel"
              class="flex-1 flex flex-col items-center p-3 rounded-(--radius-md) border transition-colors cursor-pointer"
              :class="[
                loadingModel ? 'opacity-50' : '',
                selectedMode === 'prompt' && !loadingModel
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-hairline hover:border-hairline-strong text-ink-mute'
              ]"
              @mouseenter="() => { if (!loadingModel) selectedMode = 'prompt' }"
            >
              <svg class="w-5 h-5 mb-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="6" />
                <circle cx="12" cy="12" r="2" />
              </svg>
              <span class="text-[12px] font-medium">Prompt Inference</span>
              <span class="text-[10px] text-ink-faint">Text / Visual</span>
            </button>
          </div>
          <!-- Loading indicator -->
          <div v-if="loadingModel" class="mt-3 flex items-center justify-center gap-2">
            <div class="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span class="text-[11px] text-ink-mute">Loading model...</span>
          </div>
          <!-- Error -->
          <p v-if="inferenceStore.modelError && !loadingModel" class="mt-2 text-[11px] text-red-400 text-center">
            {{ inferenceStore.modelError }}
          </p>
        </div>

        <!-- Prompt config (when model loaded in prompt mode) -->
        <div v-if="modelReady && inferenceStore.inferenceMode === 'prompt'" class="mb-(--spacing-md)">
          <div class="p-3 rounded-(--radius-md) bg-ink/[0.03] text-[12px] mb-(--spacing-sm)">
            <span class="text-ink-mute">Current mode:</span>
            <span class="text-ink font-medium">{{ promptMode }}</span>
            <template v-if="promptMode === 'visual'">
              <span class="text-ink-faint ml-1">(uses workspace visual prompt if set)</span>
            </template>
          </div>

          <label v-if="promptMode === 'text'" class="block">
            <span class="text-[12px] text-ink-mute uppercase tracking-wide">Labels (comma-separated)</span>
            <input
              v-model="labels"
              placeholder="defect, scratch, dent"
              class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
            />
          </label>
        </div>

        <!-- Confidence -->
        <div class="mb-(--spacing-lg) p-3 rounded-(--radius-md) bg-ink/[0.03] text-[12px]">
          <span class="text-ink-mute">Confidence threshold:</span>
          <span class="text-ink font-mono">{{ (inferenceStore.confidence * 100).toFixed(0) }}%</span>
          <span class="text-ink-faint">(from workspace settings)</span>
        </div>

        <!-- Label result -->
        <div v-if="labelResult" class="mb-(--spacing-md) p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px] text-center">
          {{ labelResult.labeled }} / {{ labelResult.total_unlabeled }} images labeled
        </div>

        <!-- Actions -->
        <div class="flex gap-3 justify-end">
          <button @click="phase = 'upload'" class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5">
            ← Back
          </button>
          <button
            v-if="!labelResult"
            @click="startLabeling"
            :disabled="labeling || !modelReady"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
          >
            {{ labeling ? 'Labeling...' : 'Start Labeling' }}
          </button>
          <button
            v-else
            @click="close"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90"
          >
            Done
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
