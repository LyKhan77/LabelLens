<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import type { BBoxAnnotation } from '../../shared/types'
import type { DatasetLabelJobStatus } from '../../shared/api/dataset'
import BBoxAnnotationCanvas from '../../shared/components/BBoxAnnotation.vue'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

const phase = ref<'upload' | 'configure' | 'progress' | 'done'>('upload')
const files = ref<File[]>([])
const sampleFps = ref(1)
const isDragging = ref(false)
const uploading = ref(false)
const uploadMessage = ref('')
const error = ref('')

const promptType = ref<'free' | 'text' | 'visual'>('free')
const labelsText = ref('')
const confidence = ref(0.5)
const referImage = ref<File | null>(null)
const referPreview = ref('')
const visualAnnotations = ref<BBoxAnnotation[]>([])
const loadingModel = ref(false)

const job = ref<DatasetLabelJobStatus | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const imageFiles = computed(() => files.value.filter((f) => f.type.startsWith('image/')))
const videoFiles = computed(() => files.value.filter((f) => f.type.startsWith('video/')))
const hasMixedMedia = computed(() => imageFiles.value.length > 0 && videoFiles.value.length > 0)
const hasTooManyVideos = computed(() => videoFiles.value.length > 1)
const labels = computed(() => labelsText.value.split(',').map((s) => s.trim()).filter(Boolean))
const requiredModel = computed(() => promptType.value === 'free' ? 'free' : 'prompt')
const modelReady = computed(() => inferenceStore.modelLoaded && inferenceStore.inferenceMode === requiredModel.value)
const canUpload = computed(() => files.value.length > 0 && !hasMixedMedia.value && !hasTooManyVideos.value)
const canStart = computed(() => {
  if (!modelReady.value) return false
  if (promptType.value === 'text' && labels.value.length === 0) return false
  if (promptType.value === 'visual' && (!referImage.value || visualAnnotations.value.length === 0)) return false
  return true
})
const progressPercent = computed(() => {
  if (!job.value || job.value.total === 0) return job.value?.state === 'done' ? 100 : 0
  return Math.round((job.value.processed / job.value.total) * 100)
})

function close() {
  stopPolling()
  emit('close')
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  if (!e.dataTransfer) return
  files.value = [...files.value, ...Array.from(e.dataTransfer.files)]
  error.value = ''
}

function removeFile(idx: number) {
  files.value.splice(idx, 1)
}

function handleReference(file: File) {
  if (!file.type.startsWith('image/')) return
  referImage.value = file
  visualAnnotations.value = []
  const reader = new FileReader()
  reader.onload = () => { referPreview.value = reader.result as string }
  reader.readAsDataURL(file)
}

async function startUpload() {
  error.value = ''
  if (!canUpload.value) {
    error.value = hasMixedMedia.value
      ? 'Upload either images or one video, not mixed media.'
      : 'Only one video can be uploaded per batch.'
    return
  }
  uploading.value = true
  uploadMessage.value = ''
  try {
    if (videoFiles.value.length === 1) {
      const result = await datasetStore.uploadStream({ file: videoFiles.value[0], sampleFps: sampleFps.value })
      uploadMessage.value = `${result?.uploaded ?? 0} frames uploaded`
    } else {
      const result = await datasetStore.uploadRaw(imageFiles.value)
      uploadMessage.value = `${result?.uploaded ?? 0} images uploaded`
    }
    phase.value = 'configure'
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Upload failed'
  } finally {
    uploading.value = false
  }
}

async function loadSelectedModel() {
  loadingModel.value = true
  error.value = ''
  try {
    await inferenceStore.selectMode(requiredModel.value)
  } finally {
    loadingModel.value = false
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollJob(jobId: string) {
  const status = await datasetStore.getLabelJob(jobId)
  if (!status) return
  job.value = status
  if (status.state === 'done' || status.state === 'failed') {
    stopPolling()
    phase.value = status.state === 'done' ? 'done' : 'progress'
    if (status.error) error.value = status.error
  }
}

async function startLabeling() {
  if (!canStart.value) return
  error.value = ''
  phase.value = 'progress'
  try {
    const created = await datasetStore.createLabelJob({
      promptType: promptType.value,
      labels: labels.value,
      confidence: confidence.value,
      referImage: referImage.value ?? undefined,
      bboxes: visualAnnotations.value.map((a) => a.bbox),
      vcls: visualAnnotations.value.map((a) => a.label),
    })
    if (!created) return
    job.value = created
    pollTimer = setInterval(() => pollJob(created.job_id), 900)
    await pollJob(created.job_id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Label job failed'
  }
}

watch(promptType, () => { error.value = '' })
onUnmounted(stopPolling)
</script>

<template>
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition ease-in duration-150"
    leave-to-class="opacity-0"
  >
    <div class="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" @click.self="close">
    <section class="bg-canvas rounded-(--radius-xl) w-full max-w-[760px] border border-hairline shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)] max-h-[92vh] overflow-hidden flex flex-col">
      <header class="px-6 py-5 border-b border-hairline flex items-center justify-between shrink-0">
        <div>
          <h3 class="text-[18px] font-medium text-ink tracking-[-0.3px]">Upload + Auto-Label</h3>
          <p class="text-[12px] text-ink-mute">Upload data, configure YOLOE grounding, then review results.</p>
        </div>
        <button class="w-8 h-8 rounded-(--radius-sm) flex items-center justify-center text-ink-faint hover:bg-canvas-soft hover:text-ink transition-colors cursor-pointer" @click="close">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </button>
      </header>

      <div class="px-6 py-3 border-b border-hairline flex items-center gap-2 text-[11px] text-ink-mute shrink-0 overflow-x-auto">
        <span class="px-3 py-1.5 rounded-(--radius-sm)" :class="phase === 'upload' ? 'bg-primary text-on-primary' : 'bg-canvas-soft'">1 Upload</span>
        <span class="h-px w-6 bg-hairline" />
        <span class="px-3 py-1.5 rounded-(--radius-sm)" :class="phase === 'configure' ? 'bg-primary text-on-primary' : 'bg-canvas-soft'">2 Auto-Label</span>
        <span class="h-px w-6 bg-hairline" />
        <span class="px-3 py-1.5 rounded-(--radius-sm)" :class="phase === 'progress' ? 'bg-primary text-on-primary' : 'bg-canvas-soft'">3 Batch Inference</span>
        <span class="h-px w-6 bg-hairline" />
        <span class="px-3 py-1.5 rounded-(--radius-sm)" :class="phase === 'done' ? 'bg-primary text-on-primary' : 'bg-canvas-soft'">4 Review</span>
      </div>

      <div class="min-h-0 overflow-y-auto p-6">
        <template v-if="phase === 'upload'">
          <div
            class="border-2 border-dashed rounded-(--radius-lg) p-8 text-center transition-colors cursor-pointer"
            :class="isDragging ? 'border-primary bg-primary/5' : 'border-hairline hover:border-hairline-strong'"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="onDrop"
            @click="($refs.fileInput as HTMLInputElement)?.click()"
          >
            <input ref="fileInput" type="file" multiple accept="image/*,video/*" class="hidden" @change="(e) => files.push(...Array.from((e.target as HTMLInputElement).files ?? []))" />
            <svg class="w-9 h-9 mx-auto mb-3 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
            <p class="text-[14px] text-ink font-medium">Drop images or one video here</p>
            <p class="text-[12px] text-ink-mute mt-1">Images are stored raw first. Video is sampled once until EOF.</p>
          </div>

          <div v-if="files.length" class="mt-4 border border-hairline rounded-(--radius-md) divide-y divide-hairline max-h-[180px] overflow-y-auto">
            <div v-for="(f, i) in files" :key="f.name + i" class="flex items-center justify-between px-3 py-2 text-[12px]">
              <span class="text-ink-mute truncate">{{ f.name }}</span>
              <button class="text-ink-faint hover:text-red-500 cursor-pointer" @click="removeFile(i)">Remove</button>
            </div>
          </div>

          <label v-if="videoFiles.length" class="block mt-4">
            <div class="flex justify-between text-[12px] mb-1">
              <span class="text-ink-mute uppercase tracking-wide">Frame sampling</span>
              <span class="font-mono text-ink">{{ sampleFps }} fps</span>
            </div>
            <input v-model.number="sampleFps" type="range" min="0.5" max="10" step="0.5" class="w-full accent-[#3ecf8e]" />
          </label>
        </template>

        <template v-else-if="phase === 'configure'">
          <div class="grid grid-cols-3 gap-2 mb-4">
            <button v-for="mode in ['free', 'text', 'visual']" :key="mode" class="px-3 py-2 rounded-(--radius-sm) border text-[13px] font-medium capitalize cursor-pointer transition-colors" :class="promptType === mode ? 'border-primary bg-primary text-on-primary' : 'border-hairline text-ink-mute hover:text-ink'" @click="promptType = mode as 'free' | 'text' | 'visual'">
              {{ mode }}
            </button>
          </div>

          <label v-if="promptType === 'text'" class="block mb-4">
            <span class="text-[12px] text-ink-mute uppercase tracking-wide">Labels</span>
            <input v-model="labelsText" class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-sm) text-ink focus:outline-none focus:border-primary" placeholder="person, vehicle, defect" />
          </label>

          <div v-if="promptType === 'visual'" class="mb-4">
            <div v-if="!referPreview" class="border-2 border-dashed border-hairline rounded-(--radius-lg) p-5 text-center">
              <p class="text-[13px] text-ink-mute mb-2">Upload reference image for SAVPE visual prompt.</p>
              <label class="inline-flex px-3 py-2 rounded-(--radius-sm) bg-primary text-on-primary text-[13px] font-medium cursor-pointer hover:bg-primary-deep transition-colors">
                Browse Reference
                <input type="file" accept="image/*" class="hidden" @change="(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) handleReference(f) }" />
              </label>
            </div>
            <div v-else class="flex gap-4 items-start">
              <BBoxAnnotationCanvas :image-src="referPreview" :annotations="visualAnnotations" :max-width="480" @add="visualAnnotations.push($event)" @remove="visualAnnotations.splice($event, 1)" />
              <div class="flex-1 min-w-[180px] bg-canvas border border-hairline rounded-(--radius-md) p-4">
                <p class="text-[11px] uppercase tracking-wide text-ink-faint mb-2.5">Annotations ({{ visualAnnotations.length }})</p>
                <div v-if="!visualAnnotations.length" class="text-[12px] text-ink-faint py-2">Draw bboxes on the image to add annotations.</div>
                <div v-for="(ann, idx) in visualAnnotations" :key="idx" class="flex items-center gap-2 py-2 border-b border-hairline/50 last:border-b-0">
                  <span class="w-2.5 h-2.5 rounded-full bg-primary shrink-0" />
                  <span class="text-[12px] font-medium text-ink flex-1">{{ ann.label }}</span>
                  <button class="text-[11px] text-red-400 hover:text-red-500 bg-none border-none cursor-pointer" @click="visualAnnotations.splice(idx, 1)">✕</button>
                </div>
                <label class="mt-3 pt-3 border-t border-hairline/50 inline-flex text-[12px] text-primary hover:text-primary-deep cursor-pointer font-medium">
                  Change reference
                  <input type="file" accept="image/*" class="hidden" @change="(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) handleReference(f) }" />
                </label>
              </div>
            </div>
          </div>

          <label class="block mb-4">
            <div class="flex justify-between text-[12px] mb-1">
              <span class="text-ink-mute uppercase tracking-wide">Confidence</span>
              <span class="font-mono text-ink">{{ Math.round(confidence * 100) }}%</span>
            </div>
            <input v-model.number="confidence" type="range" min="0.05" max="0.95" step="0.05" class="w-full accent-[#3ecf8e]" />
          </label>

          <div class="rounded-(--radius-md) border border-hairline bg-canvas-soft p-3 text-[12px] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <span class="text-ink-mute">Required model: <span class="text-ink font-medium">{{ requiredModel }}</span></span>
            <button class="px-3 py-1.5 rounded-(--radius-sm) text-[12px] font-medium cursor-pointer transition-colors" :class="modelReady ? 'bg-primary/15 text-primary' : 'bg-primary text-on-primary hover:bg-primary-deep'" :disabled="loadingModel" @click="loadSelectedModel">
              {{ modelReady ? 'Model Ready' : loadingModel ? 'Loading...' : 'Load Model' }}
            </button>
          </div>
        </template>

        <template v-else>
          <div class="rounded-(--radius-lg) border border-hairline overflow-hidden bg-canvas-soft">
            <div class="aspect-video bg-black flex items-center justify-center overflow-hidden">
              <img v-if="job?.current_image_url" :src="job.current_image_url" :alt="job.current_filename || 'Current image'" class="w-full h-full object-contain" />
              <span v-else class="text-[12px] text-white/50">Waiting for first frame</span>
            </div>
            <div class="p-4">
              <div class="h-2 rounded-full bg-ink/10 overflow-hidden mb-3">
                <div class="h-full bg-primary transition-all" :style="{ width: `${progressPercent}%` }" />
              </div>
              <div class="flex flex-wrap items-center justify-between gap-2 text-[12px]">
                <span class="text-ink-mute">{{ job?.state || 'queued' }} · {{ job?.processed ?? 0 }} / {{ job?.total ?? 0 }} images</span>
                <span class="font-mono text-ink">{{ job?.detections_count ?? 0 }} detections</span>
              </div>
              <p v-if="job?.current_filename" class="mt-2 text-[12px] text-ink-faint truncate">{{ job.current_filename }}</p>
            </div>
          </div>
        </template>

        <p v-if="uploadMessage && phase !== 'upload'" class="mt-4 text-[12px] text-primary">{{ uploadMessage }}</p>
        <p v-if="error || inferenceStore.modelError" class="mt-4 text-[12px] text-red-500">{{ error || inferenceStore.modelError }}</p>
      </div>

      <footer class="px-6 py-5 border-t border-hairline flex items-center justify-between shrink-0">
        <button class="px-3 py-2 text-[13px] text-ink-mute rounded-(--radius-sm) hover:bg-canvas-soft cursor-pointer" @click="phase === 'upload' || phase === 'done' ? close() : phase = 'upload'">
          {{ phase === 'upload' || phase === 'done' ? 'Close' : 'Back' }}
        </button>
        <div class="flex gap-2">
          <button v-if="phase === 'upload'" class="px-4 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep disabled:opacity-50 cursor-pointer" :disabled="uploading || !files.length" @click="startUpload">
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
          <button v-else-if="phase === 'configure'" class="px-4 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep disabled:opacity-50 cursor-pointer" :disabled="!canStart" @click="startLabeling">
            Start Labeling
          </button>
          <button v-else-if="phase === 'done'" class="px-4 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep cursor-pointer" @click="close">
            Review Gallery
          </button>
        </div>
      </footer>
    </section>
  </div>
  </Transition>
</template>
