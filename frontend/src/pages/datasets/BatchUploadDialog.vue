<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import type { BBoxAnnotation } from '../../shared/types'
import type { DatasetLabelJobItem, DatasetLabelJobStatus } from '../../shared/api/dataset'
import { listModelVersions, type ModelVersion } from '../../shared/api/training'
import BBoxAnnotationCanvas from '../../shared/components/BBoxAnnotation.vue'
import DatasetMediaOverlay from './DatasetMediaOverlay.vue'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

const phase = ref<'upload' | 'configure' | 'progress' | 'done'>('upload')
const sourceMode = ref<'current' | 'upload'>('current')
const files = ref<File[]>([])
const sampleFps = ref(1)
const isDragging = ref(false)
const uploading = ref(false)
const uploadMessage = ref('')
const error = ref('')

const promptType = ref<'free' | 'text' | 'visual'>('free')
const labelsText = ref('')
const confidence = ref(0.5)
const modelPath = ref('')
const referImage = ref<File | null>(null)
const referPreview = ref('')
const visualAnnotations = ref<BBoxAnnotation[]>([])
const loadingModel = ref(false)

const job = ref<DatasetLabelJobStatus | null>(null)
const classColors = computed(() => datasetStore.currentProjectData?.class_colors ?? {})
const taskType = computed(() => datasetStore.currentProjectData?.task_type ?? 'detect')
const isGroundingTask = computed(() => taskType.value === 'detect' || taskType.value === 'segment')
const isPromptClassificationTask = computed(() => taskType.value === 'classify_single')
const usesYoloePromptTask = computed(() => isGroundingTask.value || isPromptClassificationTask.value)
const taskLabel = computed(() => {
  if (taskType.value === 'segment') return 'Segmentation'
  if (taskType.value === 'classify_single') return 'Classification · Single'
  if (taskType.value === 'classify_multi') return 'Classification · Multi'
  if (taskType.value === 'pose') return 'Pose'
  return 'Detection'
})
const highlightedItemIndex = ref(0)
const jobComplete = ref(false)

// Auto-Crop Objects (detect/segment only)
const configMode = ref<'rapid' | 'crop'>('rapid')
const cropSource = ref<'pretrained' | 'trained'>('pretrained')
const cropClassesText = ref('')
const cropConfidence = ref(0.5)
const trainedModels = ref<ModelVersion[]>([])
const selectedTrainedId = ref('')
const cropClassList = computed(() => cropClassesText.value.split(',').map((s) => s.trim()).filter(Boolean))
const selectedTrainedModel = computed(() => trainedModels.value.find((m) => m.id === selectedTrainedId.value) ?? null)
const cropModelReady = computed(() => inferenceStore.modelLoaded && inferenceStore.inferenceMode === 'prompt')
const canStartCrop = computed(() => {
  if (cropSource.value === 'pretrained') return cropModelReady.value && cropClassList.value.length > 0
  return Boolean(selectedTrainedModel.value)
})

async function loadCropModels() {
  try {
    const all = await listModelVersions()
    trainedModels.value = all.filter((m) => m.task_type === 'detect' || m.task_type === 'segment')
  } catch {
    trainedModels.value = []
  }
}

async function loadCropYoloe() {
  loadingModel.value = true
  error.value = ''
  try {
    await inferenceStore.selectMode('prompt')
  } finally {
    loadingModel.value = false
  }
}

async function startCrop() {
  if (!canStartCrop.value) return
  error.value = ''
  highlightedItemIndex.value = 0
  jobComplete.value = false
  stopDisplayPlayback()
  phase.value = 'progress'
  try {
    const created = await datasetStore.createCropJob({
      source: cropSource.value,
      labels: cropClassList.value,
      confidence: cropConfidence.value,
      modelPath: cropSource.value === 'trained' ? selectedTrainedModel.value?.best_model_path : undefined,
      modelTask: cropSource.value === 'trained' ? selectedTrainedModel.value?.task_type : undefined,
    })
    if (!created) return
    job.value = created
    pollTimer = setInterval(() => pollJob(created.job_id), 300)
    await pollJob(created.job_id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Auto-crop job failed'
  }
}
let pollTimer: ReturnType<typeof setInterval> | null = null
let displayTimer: ReturnType<typeof setInterval> | null = null

const VALID_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.mp4', '.avi', '.mov'])

function isValidMediaFile(name: string): boolean {
  const dot = name.lastIndexOf('.')
  return dot >= 0 && VALID_EXTENSIONS.has(name.slice(dot).toLowerCase())
}

async function scanEntries(entries: FileSystemEntry[]): Promise<File[]> {
  const results: File[] = []

  async function processEntry(entry: FileSystemEntry): Promise<void> {
    if (entry.isFile) {
      const fileEntry = entry as FileSystemFileEntry
      const file: File = await new Promise((resolve, reject) => fileEntry.file(resolve, reject))
      if (isValidMediaFile(file.name)) results.push(file)
    } else if (entry.isDirectory) {
      const dirReader = (entry as FileSystemDirectoryEntry).createReader()
      const batch: FileSystemEntry[] = await new Promise((resolve, reject) => {
        dirReader.readEntries(resolve, reject)
      })
      for (const child of batch) {
        await processEntry(child)
      }
    }
  }

  await Promise.all(entries.map(processEntry))
  return results
}

function onFolderSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files) return
  const valid = Array.from(input.files).filter((f) => isValidMediaFile(f.name))
  files.value = [...files.value, ...valid]
  error.value = ''
  input.value = ''
}

const imageFiles = computed(() => files.value.filter((f) => f.type.startsWith('image/')))
const videoFiles = computed(() => files.value.filter((f) => f.type.startsWith('video/')))
const hasMixedMedia = computed(() => imageFiles.value.length > 0 && videoFiles.value.length > 0)
const labels = computed(() => labelsText.value.split(',').map((s) => s.trim()).filter(Boolean))
const defaultTaskModelPath = computed(() => {
  if (taskType.value === 'pose') return 'yolo26n-pose.pt'
  if (taskType.value === 'classify_single') return 'yolo26n-cls.pt'
  return ''
})
const activeTaskModelPath = computed(() => modelPath.value.trim() || defaultTaskModelPath.value)
const requiredGroundingModel = computed<'free' | 'prompt'>(() => isPromptClassificationTask.value || promptType.value !== 'free' ? 'prompt' : 'free')
const requiredModel = computed(() => usesYoloePromptTask.value ? requiredGroundingModel.value : activeTaskModelPath.value)
const taskModelSupported = computed(() => taskType.value === 'pose')
const modelReady = computed(() => usesYoloePromptTask.value && inferenceStore.modelLoaded && inferenceStore.inferenceMode === requiredGroundingModel.value)
const canUpload = computed(() => sourceMode.value === 'current' || (files.value.length > 0 && !hasMixedMedia.value))
const canStart = computed(() => {
  if (isPromptClassificationTask.value) return modelReady.value && labels.value.length > 0
  if (!isGroundingTask.value) return taskModelSupported.value && activeTaskModelPath.value.length > 0
  if (!modelReady.value) return false
  if (promptType.value === 'text' && labels.value.length === 0) return false
  if (promptType.value === 'visual' && (!referImage.value || visualAnnotations.value.length === 0)) return false
  return true
})
const progressPercent = computed(() => {
  if (!job.value || job.value.total === 0) return job.value?.state === 'done' ? 100 : 0
  return Math.round((job.value.processed / job.value.total) * 100)
})
const progressItems = computed(() => job.value?.items ?? [])
const maxVisibleItemIndex = computed(() => {
  if (!progressItems.value.length) return -1
  if (jobComplete.value) return progressItems.value.length - 1
  const runningIndex = progressItems.value.findIndex((item) => item.state === 'running')
  return runningIndex >= 0 ? runningIndex : progressItems.value.length - 1
})
const previewItem = computed<DatasetLabelJobItem | null>(() => {
  if (!progressItems.value.length) return null
  const safeIndex = Math.min(highlightedItemIndex.value, progressItems.value.length - 1)
  return progressItems.value[safeIndex] ?? null
})
const previewImageUrl = computed(() => previewItem.value?.image_url ?? job.value?.current_image_url ?? '')
const previewFilename = computed(() => previewItem.value?.filename ?? job.value?.current_filename ?? '')
const previewDetections = computed(() => previewItem.value?.detections ?? [])
const doneItems = computed(() => progressItems.value.filter((item) => item.state === 'done').length)
const failedItems = computed(() => progressItems.value.filter((item) => item.state === 'failed').length)
const displayFrameNumber = computed(() => previewItem.value ? highlightedItemIndex.value + 1 : 0)
const displayFrameTotal = computed(() => job.value?.total || progressItems.value.length || 0)

function close() {
  stopPolling()
  stopDisplayPlayback()
  emit('close')
}

async function onDrop(e: DragEvent) {
  isDragging.value = false
  if (!e.dataTransfer) return
  error.value = ''
  const items = e.dataTransfer.items
  if (items && items.length > 0) {
    const entries: FileSystemEntry[] = []
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.()
      if (entry) entries.push(entry)
    }
    if (entries.length > 0) {
      uploading.value = true
      try {
        const scanned = await scanEntries(entries)
        files.value = [...files.value, ...scanned]
      } finally {
        uploading.value = false
      }
      return
    }
  }
  files.value = [...files.value, ...Array.from(e.dataTransfer.files)]
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
  if (sourceMode.value === 'current') {
    phase.value = 'configure'
    uploadMessage.value = 'Using current unlabeled dataset images'
    return
  }
  if (!canUpload.value) {
    error.value = 'Upload either images or videos, not mixed media.'
    return
  }
  uploading.value = true
  uploadMessage.value = ''
  try {
    if (videoFiles.value.length > 0) {
      let totalFrames = 0
      for (const video of videoFiles.value) {
        const result = await datasetStore.uploadStream({ file: video, sampleFps: sampleFps.value })
        totalFrames += result?.uploaded ?? 0
      }
      uploadMessage.value = `${totalFrames} frames uploaded from ${videoFiles.value.length} video(s)`
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
  if (!usesYoloePromptTask.value) return
  loadingModel.value = true
  error.value = ''
  try {
    await inferenceStore.selectMode(requiredGroundingModel.value)
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

function stopDisplayPlayback() {
  if (displayTimer) {
    clearInterval(displayTimer)
    displayTimer = null
  }
}

function advanceDisplayFrame() {
  if (maxVisibleItemIndex.value < 0) return
  if (highlightedItemIndex.value < maxVisibleItemIndex.value) {
    highlightedItemIndex.value += 1
    return
  }
  if (jobComplete.value) {
    stopDisplayPlayback()
    phase.value = 'done'
  }
}

function ensureDisplayPlayback() {
  if (!displayTimer) {
    displayTimer = setInterval(advanceDisplayFrame, 750)
  }
  advanceDisplayFrame()
}

async function pollJob(jobId: string) {
  const status = await datasetStore.getLabelJob(jobId)
  if (!status) return
  job.value = status
  ensureDisplayPlayback()
  if (status.state === 'done' || status.state === 'failed') {
    stopPolling()
    jobComplete.value = true
    if (status.error) error.value = status.error
    if (!status.items.length || highlightedItemIndex.value >= status.items.length - 1) {
      stopDisplayPlayback()
      phase.value = status.state === 'done' ? 'done' : 'progress'
    }
  }
}

async function startLabeling() {
  if (!canStart.value) return
  error.value = ''
  highlightedItemIndex.value = 0
  jobComplete.value = false
  stopDisplayPlayback()
  phase.value = 'progress'
  try {
    const created = await datasetStore.createLabelJob({
      promptType: usesYoloePromptTask.value ? (isPromptClassificationTask.value ? 'text' : promptType.value) : 'task_model',
      labels: labels.value,
      confidence: confidence.value,
      referImage: referImage.value ?? undefined,
      bboxes: visualAnnotations.value.map((a) => a.bbox),
      vcls: visualAnnotations.value.map((a) => a.label),
      modelPath: usesYoloePromptTask.value ? undefined : activeTaskModelPath.value,
    })
    if (!created) return
    job.value = created
    pollTimer = setInterval(() => pollJob(created.job_id), 300)
    await pollJob(created.job_id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Label job failed'
  }
}

watch(promptType, () => { error.value = '' })
onMounted(() => { loadCropModels() })
onUnmounted(() => {
  stopPolling()
  stopDisplayPlayback()
})
</script>

<template>
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0 scale-[0.98]"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition ease-in duration-150"
    leave-to-class="opacity-0 scale-[0.98]"
  >
    <div class="dataset-dialog-backdrop" @click.self="close">
      <section class="dataset-upload-dialog">
        <header class="dataset-modal-header">
          <div>
            <h3 class="dataset-modal-title">Rapid Inference</h3>
            <p class="dataset-modal-copy">Upload data, configure YOLOE grounding, then review results.</p>
          </div>
          <button class="dataset-modal-close" @click="close" aria-label="Close upload dialog">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </header>

        <nav class="dataset-upload-steps" aria-label="Rapid inference workflow">
          <span :class="['dataset-upload-step', { 'is-active': phase === 'upload', 'is-done': phase !== 'upload' }]">1 Upload</span>
          <span :class="['dataset-upload-step', { 'is-active': phase === 'configure', 'is-done': phase === 'progress' || phase === 'done' }]">2 Method</span>
          <span :class="['dataset-upload-step', { 'is-active': phase === 'progress', 'is-done': phase === 'done' }]">3 Inference</span>
          <span :class="['dataset-upload-step', { 'is-active': phase === 'done' }]">4 Review</span>
        </nav>

        <div class="dataset-modal-body dataset-upload-body">
          <template v-if="phase === 'upload'">
            <div class="dataset-mode-tabs">
              <button :class="{ 'is-active': sourceMode === 'current' }" @click="sourceMode = 'current'">
                <strong>Current Dataset</strong>
                <small>Use unlabeled images already in this dataset</small>
              </button>
              <button :class="{ 'is-active': sourceMode === 'upload' }" @click="sourceMode = 'upload'">
                <strong>Upload New</strong>
                <small>Add images, videos, or folders first</small>
              </button>
            </div>

            <div
              v-if="sourceMode === 'upload'"
              class="dataset-dropzone"
              :class="{ 'is-active': isDragging }"
              @dragover.prevent="isDragging = true"
              @dragleave="isDragging = false"
              @drop.prevent="onDrop"
            >
              <input ref="fileInput" type="file" multiple accept="image/*,video/*" class="hidden" @change="(e) => { files.push(...Array.from((e.target as HTMLInputElement).files ?? [])); error = '' }" />
              <input ref="folderInput" type="file" webkitdirectory directory multiple class="hidden" @change="onFolderSelect" />
              <svg class="w-9 h-9 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
              <div>
                <p>Drop images, videos, or a folder here</p>
                <small>Images are stored raw first. Video is sampled once until EOF. Folders are scanned recursively.</small>
              </div>
              <div class="dataset-upload-actions">
                <button class="dataset-secondary-button" @click.stop="($refs.fileInput as HTMLInputElement)?.click()">Select Files</button>
                <button class="dataset-secondary-button" @click.stop="($refs.folderInput as HTMLInputElement)?.click()">Select Folder</button>
              </div>
            </div>

            <div v-if="sourceMode === 'upload' && files.length" class="dataset-upload-files">
              <div class="dataset-upload-files-header">
                <span>{{ files.length }} selected</span>
                <small v-if="hasMixedMedia">Mixed image and video batches are not supported.</small>
                <small v-else>Ready to upload.</small>
              </div>
              <div class="dataset-file-list">
                <div v-for="(f, i) in files" :key="f.name + i" class="dataset-file-row">
                  <span>{{ f.name }}</span>
                  <button @click="removeFile(i)">Remove</button>
                </div>
              </div>
            </div>

            <div v-if="sourceMode === 'upload' && videoFiles.length" class="dataset-panel-block">
              <div class="dataset-field-row">
                <span class="dataset-field-label">Frame Sampling</span>
                <span class="dataset-field-value">{{ sampleFps }} fps</span>
              </div>
              <input v-model.number="sampleFps" type="range" min="0.5" max="10" step="0.5" class="dataset-range" />
            </div>
          </template>

          <template v-else-if="phase === 'configure'">
            <div class="dataset-panel-block">
              <div class="dataset-field-row">
                <span class="dataset-field-label">Dataset Task</span>
                <span class="dataset-field-value">{{ taskLabel }}</span>
              </div>
            </div>

            <div class="dataset-mode-tabs">
              <button :class="{ 'is-active': configMode === 'rapid' }" @click="configMode = 'rapid'">
                <strong>Rapid Inference</strong>
                <small>Auto-label images</small>
              </button>
              <button :class="{ 'is-active': configMode === 'crop' }" @click="configMode = 'crop'">
                <strong>Auto-Crop Objects</strong>
                <small>Crop detections only</small>
              </button>
            </div>

            <template v-if="configMode === 'crop'">
              <div class="dataset-mode-tabs">
                <button :class="{ 'is-active': cropSource === 'pretrained' }" @click="cropSource = 'pretrained'">
                  <strong>Pre-trained</strong>
                  <small>YOLOE + class names</small>
                </button>
                <button :class="{ 'is-active': cropSource === 'trained' }" @click="cropSource = 'trained'">
                  <strong>Trained Model</strong>
                  <small>From Train Tune</small>
                </button>
              </div>

              <template v-if="cropSource === 'pretrained'">
                <label class="dataset-field-block">
                  <span class="dataset-field-label">Class Names</span>
                  <input v-model="cropClassesText" class="dataset-text-input" placeholder="bolt, scratch, crack" />
                </label>
                <div class="dataset-model-row">
                  <div>
                    <span class="dataset-field-label">Required Model</span>
                    <strong>yoloe-26l-seg.pt</strong>
                  </div>
                  <button class="dataset-secondary-button" :class="{ 'is-ready': cropModelReady }" :disabled="loadingModel" @click="loadCropYoloe">
                    {{ cropModelReady ? 'Model Ready' : loadingModel ? 'Loading...' : 'Load Model' }}
                  </button>
                </div>
              </template>

              <template v-else>
                <label class="dataset-field-block">
                  <span class="dataset-field-label">Trained Model (Detection / Segmentation)</span>
                  <select v-model="selectedTrainedId" class="dataset-text-input">
                    <option value="" disabled>Select a model version...</option>
                    <option v-for="m in trainedModels" :key="m.id" :value="m.id">
                      {{ m.version_name }} · {{ m.task_type === 'segment' ? 'SEG' : 'DET' }} · {{ m.family }}{{ m.size }}
                    </option>
                  </select>
                </label>
                <p v-if="trainedModels.length === 0" class="text-[12px] text-ink-mute">No detection/segmentation model versions found. Train one in Train Tune.</p>
              </template>

              <div class="dataset-panel-block">
                <div class="dataset-field-row">
                  <span class="dataset-field-label">Confidence</span>
                  <span class="dataset-field-value">{{ Math.round(cropConfidence * 100) }}%</span>
                </div>
                <input v-model.number="cropConfidence" type="range" min="0.05" max="0.95" step="0.05" class="dataset-range" />
              </div>

              <p class="text-[12px] text-ink-mute leading-relaxed">
                Each uploaded image is inferred, detected objects are cropped (HD PNG), and only the crops are kept — original images are removed. Use the resulting dataset for classification (e.g. OK/NG) annotation.
              </p>
            </template>

            <template v-else>
            <template v-if="usesYoloePromptTask">
            <div v-if="isGroundingTask" class="dataset-mode-tabs">
              <button :class="{ 'is-active': promptType === 'free' }" @click="promptType = 'free'">
                <strong>Free</strong>
                <small>LRPC vocabulary</small>
              </button>
              <button :class="{ 'is-active': promptType === 'text' }" @click="promptType = 'text'">
                <strong>Text</strong>
                <small>Comma labels</small>
              </button>
              <button :class="{ 'is-active': promptType === 'visual' }" @click="promptType = 'visual'">
                <strong>Visual</strong>
                <small>Reference bbox</small>
              </button>
            </div>

            <label v-if="promptType === 'text' || isPromptClassificationTask" class="dataset-field-block">
              <span class="dataset-field-label">Labels</span>
              <input v-model="labelsText" class="dataset-text-input" :placeholder="isPromptClassificationTask ? 'good part, scratched part, missing screw' : 'person, vehicle, defect'" />
            </label>

            <div v-if="promptType === 'visual'" class="dataset-visual-prompt">
              <div v-if="!referPreview" class="dataset-reference-empty">
                <p>Upload a reference image for SAVPE visual prompt.</p>
                <label class="dataset-primary-button">
                  Browse Reference
                  <input type="file" accept="image/*" class="hidden" @change="(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) handleReference(f) }" />
                </label>
              </div>
              <div v-else class="dataset-reference-editor">
                <BBoxAnnotationCanvas :image-src="referPreview" :annotations="visualAnnotations" :max-width="480" @add="visualAnnotations.push($event)" @remove="visualAnnotations.splice($event, 1)" />
                <aside class="dataset-reference-panel">
                  <div class="dataset-field-row">
                    <span class="dataset-field-label">Annotations</span>
                    <span class="dataset-field-value">{{ visualAnnotations.length }}</span>
                  </div>
                  <div v-if="!visualAnnotations.length" class="dataset-empty-note">Draw bboxes on the image to add annotations.</div>
                  <div v-for="(ann, idx) in visualAnnotations" :key="idx" class="dataset-reference-row">
                    <span class="dataset-reference-dot" />
                    <strong>{{ ann.label }}</strong>
                    <button @click="visualAnnotations.splice(idx, 1)">Remove</button>
                  </div>
                  <label class="dataset-reference-change">
                    Change reference
                    <input type="file" accept="image/*" class="hidden" @change="(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) handleReference(f) }" />
                  </label>
                </aside>
              </div>
            </div>

            <div class="dataset-panel-block">
              <div class="dataset-field-row">
                <span class="dataset-field-label">Confidence</span>
                <span class="dataset-field-value">{{ Math.round(confidence * 100) }}%</span>
              </div>
              <input v-model.number="confidence" type="range" min="0.05" max="0.95" step="0.05" class="dataset-range" />
            </div>

            <div class="dataset-model-row">
              <div>
                <span class="dataset-field-label">Required Model</span>
                <strong>{{ requiredModel }}</strong>
              </div>
              <button class="dataset-secondary-button" :class="{ 'is-ready': modelReady }" :disabled="loadingModel" @click="loadSelectedModel">
                {{ modelReady ? 'Model Ready' : loadingModel ? 'Loading...' : 'Load Model' }}
              </button>
            </div>
            </template>

            <div v-else class="dataset-panel-block">
              <div class="dataset-field-row">
                <span class="dataset-field-label">Required Method</span>
                <span class="dataset-field-value">Task model</span>
              </div>
              <label v-if="taskModelSupported" class="dataset-field-block">
                <span class="dataset-field-label">Model Path</span>
                <input v-model="modelPath" class="dataset-text-input" :placeholder="defaultTaskModelPath" />
              </label>
              <p class="text-[12px] text-ink-mute leading-relaxed">
                {{ taskModelSupported ? `${taskLabel} Rapid Inference uses a task-compatible Ultralytics model. Pretrained models work only when their class list or keypoint template matches this dataset.` : 'Multi-label classification needs a dedicated multi-label model pipeline and is not supported by standard YOLO classification inference.' }}
              </p>
            </div>
            </template>
          </template>

          <template v-else>
            <div class="dataset-progress-card">
              <div class="dataset-progress-preview">
                <div v-if="previewItem" class="dataset-progress-frame-badge">
                  Frame {{ displayFrameNumber }} / {{ displayFrameTotal }}
                </div>
                <DatasetMediaOverlay
                  v-if="previewImageUrl"
                  :image-src="previewImageUrl"
                  :alt="previewFilename || 'Current image'"
                  :width="previewItem?.width"
                  :height="previewItem?.height"
                  :detections="previewDetections"
                  :show-bbox="true"
                  :show-labels="true"
                  :show-masks="true"
                  :class-colors="classColors"
                />
                <span v-else>Waiting for first frame</span>
              </div>
              <div class="dataset-progress-meta">
                <div class="dataset-progress-header">
                  <div>
                    <strong>Frame {{ displayFrameNumber }} / {{ displayFrameTotal }}</strong>
                    <span>{{ job?.state || 'queued' }} · {{ job?.processed ?? 0 }} / {{ job?.total ?? 0 }} images · {{ progressPercent }}%</span>
                  </div>
                  <div>
                    <strong>{{ job?.detections_count ?? 0 }}</strong>
                    <span>detections</span>
                  </div>
                </div>
                <div class="dataset-progress-bar">
                  <div :style="{ width: `${progressPercent}%` }" />
                </div>
                <div class="dataset-progress-stats">
                  <span>{{ doneItems }} done · {{ failedItems }} failed</span>
                  <strong v-if="previewFilename">{{ previewFilename }}</strong>
                </div>
                <div v-if="progressItems.length" class="dataset-progress-log">
                  <div
                    v-for="item in progressItems"
                    :key="item.img_id"
                    class="dataset-progress-log-row"
                    :class="[`is-${item.state}`, { 'is-active': previewItem?.img_id === item.img_id }]"
                  >
                    <span class="dataset-progress-log-dot" />
                    <div>
                      <strong>{{ item.filename }}</strong>
                      <small v-if="item.error">{{ item.error }}</small>
                      <small v-else>{{ item.detections_count }} bbox</small>
                    </div>
                    <em>{{ item.state }}</em>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <p v-if="uploadMessage && phase !== 'upload'" class="dataset-success-message">{{ uploadMessage }}</p>
          <p v-if="error || inferenceStore.modelError" class="dataset-error-message">{{ error || inferenceStore.modelError }}</p>
        </div>

        <footer class="dataset-modal-footer is-split">
          <button class="dataset-secondary-button" @click="phase === 'upload' || phase === 'done' ? close() : phase = 'upload'">
            {{ phase === 'upload' || phase === 'done' ? 'Close' : 'Back' }}
          </button>
          <div class="dataset-footer-actions">
            <button v-if="phase === 'upload'" class="dataset-primary-button" :disabled="uploading || !canUpload" @click="startUpload">
              {{ sourceMode === 'current' ? 'Continue' : uploading ? 'Uploading...' : 'Upload' }}
            </button>
            <button v-else-if="phase === 'configure' && configMode === 'crop'" class="dataset-primary-button" :disabled="!canStartCrop" @click="startCrop">
              Start Auto-Crop
            </button>
            <button v-else-if="phase === 'configure'" class="dataset-primary-button" :disabled="!canStart" @click="startLabeling">
              Start Inference
            </button>
            <button v-else-if="phase === 'done'" class="dataset-primary-button" @click="close">
              Review Gallery
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Transition>
</template>
