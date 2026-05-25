<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import { useBackendStatus } from '../../shared/composables/useBackendStatus'
import { useTheme } from '../../shared/composables/useTheme'
import { useTrainingStore } from '../../shared/stores/training'
import type { DatasetVersion, ModelVersion, TrainingJob, TrainingMetricPoint } from '../../shared/api/training'

const props = defineProps<{ path: string }>()

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()
const trainingStore = useTrainingStore()
const { yoloeStatus, samStatus } = useBackendStatus()
const { theme, toggle } = useTheme()

const form = reactive(reactiveState())
const versionDeleteError = ref<string | null>(null)
const deleteError = ref<string | null>(null)
const deletingTarget = ref(false)
type DeleteTarget =
  | { kind: 'dataset-version'; id: string; name: string }
  | { kind: 'failed-job'; id: string; name: string }
  | { kind: 'model-version'; id: string; name: string; jobName: string }
const deleteTarget = ref<DeleteTarget | null>(null)
const builderStep = ref(1)

function reactiveState() {
  return {
    sourceType: 'live' as 'live' | 'zip',
    selectedDataset: '',
    zipFile: null as File | null,
    versionName: '',
    splitMode: 'existing' as 'existing' | 'regenerate',
    splitTrain: 70,
    splitVal: 20,
    splitTest: 10,
    autoOrient: true,
    resizeMode: 'keep',
    augmentationProfile: 'baseline' as 'baseline' | 'standard',
    family: 'yolo11' as 'yolo11' | 'yolo26',
    size: 'n' as 'n' | 's' | 'm' | 'l',
    baseCheckpoint: 'yolo11n.pt',
    epochs: 50,
    imgsz: 640,
    batch: 8,
    workers: 2,
    trainingMode: 'standard' as 'standard' | 'high_speed',
    jobName: '',
    localError: null as string | null,
  }
}

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

const routeView = computed(() => {
  if (props.path.startsWith('/train-tune/jobs/')) return 'job'
  if (props.path.startsWith('/train-tune/results/')) return 'result'
  return 'builder'
})
const routeId = computed(() => props.path.split('/').filter(Boolean)[2] ?? null)
const totalSplit = computed(() => form.splitTrain + form.splitVal + form.splitTest)
const builderReady = computed(() => trainingStore.selectedVersion !== null)
const latestMetric = computed(() => trainingStore.selectedJob?.metrics_latest ?? trainingStore.jobMetrics.at(-1) ?? null)
const resultSourceVersion = computed(() => trainingStore.versions.find((version) => version.id === trainingStore.selectedModel?.dataset_version_id) ?? null)
const resultJob = computed(() => trainingStore.selectedJob)
const builderSummary = computed(() => trainingStore.selectedVersion?.summary ?? null)
const liveSourceVersion = computed(() => trainingStore.versions.find((version) => version.id === trainingStore.selectedJob?.dataset_version_id) ?? null)
const sourceReady = computed(() => form.sourceType === 'live' ? Boolean(form.selectedDataset) : Boolean(form.zipFile))
const architectureReady = computed(() => Boolean(form.baseCheckpoint) && form.epochs > 0 && form.imgsz > 0 && form.batch > 0 && form.workers > 0)
const splitReady = computed(() => totalSplit.value === 100)
const splitSegments = computed(() => [
  { label: 'Train', value: form.splitTrain, className: 'is-train' },
  { label: 'Val', value: form.splitVal, className: 'is-val' },
  { label: 'Test', value: form.splitTest, className: 'is-test' },
])
const previewSourceName = computed(() => {
  if (form.sourceType === 'live') return form.selectedDataset || 'Select a dataset project'
  return form.zipFile?.name || 'Select an export zip'
})
const previewVersionName = computed(() => {
  if (form.versionName) return form.versionName
  if (form.sourceType === 'live' && form.selectedDataset) return `${form.selectedDataset}-snapshot`
  if (form.sourceType === 'zip' && form.zipFile) return form.zipFile.name.replace(/\.zip$/i, '')
  return 'Auto-named after source selection'
})
const splitPolicySummary = computed(() => {
  if (form.sourceType === 'zip' && form.splitMode === 'existing') return 'Keep train/val/test folders from the imported zip.'
  return `Create deterministic ${form.splitTrain}/${form.splitVal}/${form.splitTest} train/val/test snapshot folders.`
})
const preprocessingSummary = computed(() => `${form.resizeMode === 'keep' ? 'Keep original image size' : 'Fit images to training resolution'}; ${form.autoOrient ? 'auto orient on' : 'auto orient off'}.`)
const augmentationSummary = computed(() => form.augmentationProfile === 'baseline'
  ? 'Baseline keeps the training recipe conservative for first-pass runs.'
  : 'Standard stores the broader augmentation preset for stronger variation.')
const metricTrends = [
  { key: 'map50', label: 'mAP50', tone: 'is-quality' },
  { key: 'map50_95', label: 'mAP50-95', tone: 'is-quality' },
  { key: 'precision', label: 'Precision', tone: 'is-balance' },
  { key: 'recall', label: 'Recall', tone: 'is-balance' },
  { key: 'train_loss', label: 'Train Loss', tone: 'is-loss' },
  { key: 'val_loss', label: 'Val Loss', tone: 'is-loss' },
] as const
const builderSteps = [
  { title: 'Dataset Source', short: 'Source' },
  { title: 'Select Architecture', short: 'Architecture' },
  { title: 'Split, Prep, Augment', short: 'Policy' },
  { title: 'Snapshot Preview', short: 'Preview' },
  { title: 'Create Dataset Version', short: 'Create' },
]
type MetricTrendKey = typeof metricTrends[number]['key']

function defaultCheckpoint(family: 'yolo11' | 'yolo26', size: 'n' | 's' | 'm' | 'l') {
  return family === 'yolo11' ? `yolo11${size}.pt` : `yolo26${size}.pt`
}

function syncCheckpoint() {
  form.baseCheckpoint = defaultCheckpoint(form.family, form.size)
}

function configText(value: unknown, fallback = 'N/A') {
  if (typeof value === 'string' && value) return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return fallback
}

function versionSplit(version: DatasetVersion | null | undefined) {
  if (!version) return 'N/A'
  return `${version.split_config.train} / ${version.split_config.val} / ${version.split_config.test}`
}

function versionSplitCounts(version: DatasetVersion | null | undefined) {
  if (!version) return 'N/A'
  return `${configText(version.split_counts.train, '0')} / ${configText(version.split_counts.val, '0')} / ${configText(version.split_counts.test, '0')}`
}

function versionResize(version: DatasetVersion | null | undefined) {
  return configText(version?.preprocessing_config.resize_mode, 'keep') === 'fit' ? 'Fit to train size' : 'Keep original'
}

function versionOrient(version: DatasetVersion | null | undefined) {
  return configText(version?.preprocessing_config.auto_orient, 'true') === 'false' ? 'Auto orient disabled' : 'Auto orient enabled'
}

function versionAugment(version: DatasetVersion | null | undefined) {
  return configText(version?.augmentation_config.profile, 'baseline')
}

function metricValue(point: TrainingMetricPoint | null | undefined, key: MetricTrendKey) {
  return point?.[key] ?? null
}

function metricLabel(value: number | null) {
  if (value === null || Number.isNaN(value)) return 'N/A'
  return value >= 10 ? value.toFixed(2) : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

function sparklinePoints(points: TrainingMetricPoint[], key: MetricTrendKey) {
  if (!points.length) return ''
  const values = points.map((point) => point[key]).filter((value) => Number.isFinite(value))
  if (!values.length) return ''
  const width = 180
  const height = 54
  const pad = 5
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || Math.max(Math.abs(max), 1)
  return values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : pad + (index / (values.length - 1)) * (width - pad * 2)
    const y = height - pad - ((value - min) / span) * (height - pad * 2)
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ')
}

function resultMetricValue(key: MetricTrendKey) {
  return metricValue(trainingStore.selectedModel?.metrics_best ?? trainingStore.jobMetrics.at(-1), key)
}

function nextBuilderStep() {
  form.localError = null
  if (builderStep.value === 1 && !sourceReady.value) {
    form.localError = form.sourceType === 'live' ? 'Pilih dataset project dulu.' : 'Pilih export zip dulu.'
    return
  }
  if (builderStep.value === 2 && !architectureReady.value) {
    form.localError = 'Lengkapi training configuration dulu.'
    return
  }
  if (builderStep.value === 3 && !splitReady.value) {
    form.localError = 'Split train/val/test harus total 100.'
    return
  }
  builderStep.value = Math.min(builderStep.value + 1, builderSteps.length)
}

function previousBuilderStep() {
  form.localError = null
  builderStep.value = Math.max(builderStep.value - 1, 1)
}

function openBuilderStep(step: number) {
  if (step <= builderStep.value) {
    form.localError = null
    builderStep.value = step
  }
}

function onZipChange(event: Event) {
  const input = event.target as HTMLInputElement
  form.zipFile = input.files?.[0] ?? null
}

function goInference() {
  inferenceStore.switchMode()
  navigate('/')
}

async function hydrate() {
  await Promise.all([datasetStore.fetchProjects(), trainingStore.hydrate()])
  await loadRouteState()
}

async function loadRouteState() {
  if (routeView.value === 'job' && routeId.value) {
    await trainingStore.selectJob(routeId.value)
  } else if (routeView.value === 'result' && routeId.value) {
    await trainingStore.selectModel(routeId.value)
  } else {
    trainingStore.selectedJob = null
    trainingStore.selectedModel = null
    trainingStore.disconnectJob()
  }
}

onMounted(hydrate)

watch(() => props.path, async () => {
  await loadRouteState()
})

watch(() => [form.family, form.size], () => syncCheckpoint(), { immediate: true })

async function buildVersion() {
  form.localError = null
  if (totalSplit.value !== 100) {
    form.localError = 'Split train/val/test harus total 100.'
    return
  }
  try {
    let version: DatasetVersion
    if (form.sourceType === 'live') {
      if (!form.selectedDataset) {
        form.localError = 'Pilih dataset project dulu.'
        return
      }
      version = await trainingStore.createLiveVersion({
        datasetName: form.selectedDataset,
        versionName: form.versionName || `${form.selectedDataset}-snapshot`,
        splitConfig: { train: form.splitTrain, val: form.splitVal, test: form.splitTest },
        preprocessingConfig: { auto_orient: form.autoOrient, resize_mode: form.resizeMode },
        augmentationConfig: { profile: form.augmentationProfile },
        resizeMode: form.resizeMode,
      })
    } else {
      if (!form.zipFile) {
        form.localError = 'Pilih export zip dulu.'
        return
      }
      version = await trainingStore.importVersion({
        file: form.zipFile,
        versionName: form.versionName || form.zipFile.name.replace(/\.zip$/i, ''),
        splitMode: form.splitMode,
        splitConfig: { train: form.splitTrain, val: form.splitVal, test: form.splitTest },
        preprocessingConfig: { auto_orient: form.autoOrient, resize_mode: form.resizeMode },
        augmentationConfig: { profile: form.augmentationProfile },
      })
    }
    if (!form.jobName) {
      form.jobName = `${version.version_name}-${form.family}-${form.size}`
    }
    builderStep.value = builderSteps.length
    await refreshEstimate()
  } catch (err) {
    form.localError = err instanceof Error ? err.message : 'Gagal membuat dataset version'
  }
}

async function refreshEstimate() {
  form.localError = null
  const version = trainingStore.selectedVersion
  if (!version) {
    form.localError = 'Dataset version belum ada.'
    return
  }
  try {
    await trainingStore.estimate({
      dataset_version_id: version.id,
      family: form.family,
      size: form.size,
      epochs: form.epochs,
      imgsz: form.imgsz,
      batch: form.batch,
      workers: form.workers,
      training_mode: form.trainingMode,
    })
  } catch (err) {
    form.localError = err instanceof Error ? err.message : 'Gagal membuat estimasi training'
  }
}

async function submitJob() {
  form.localError = null
  const version = trainingStore.selectedVersion
  if (!version) {
    form.localError = 'Dataset version belum ada.'
    return
  }
  try {
    const job = await trainingStore.createJob({
      job_name: form.jobName || `${version.version_name}-${form.family}-${form.size}`,
      dataset_version_id: version.id,
      family: form.family,
      size: form.size,
      base_checkpoint: form.baseCheckpoint,
      epochs: form.epochs,
      imgsz: form.imgsz,
      batch: form.batch,
      workers: form.workers,
      training_mode: form.trainingMode,
    })
    navigate(`/train-tune/jobs/${job.id}`)
  } catch (err) {
    form.localError = err instanceof Error ? err.message : 'Gagal submit training job'
  }
}

async function openJob(jobId: string) {
  await trainingStore.selectJob(jobId)
  navigate(`/train-tune/jobs/${jobId}`)
}

async function openResult(modelId: string) {
  await trainingStore.selectModel(modelId)
  navigate(`/train-tune/results/${modelId}`)
}

async function pickVersion(version: DatasetVersion) {
  trainingStore.selectedVersion = version
  versionDeleteError.value = null
  await refreshEstimate()
}

function errorMessage(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string') return detail
  return err instanceof Error ? err.message : fallback
}

function requestDatasetVersionDelete(version: DatasetVersion) {
  deleteError.value = null
  deleteTarget.value = { kind: 'dataset-version', id: version.id, name: version.version_name }
}

function requestFailedJobDelete(job: TrainingJob) {
  deleteError.value = null
  deleteTarget.value = { kind: 'failed-job', id: job.id, name: job.job_name }
}

function requestModelDelete(model: ModelVersion) {
  deleteError.value = null
  deleteTarget.value = { kind: 'model-version', id: model.id, name: model.model_name, jobName: model.version_name }
}

function closeDeleteDialog() {
  if (deletingTarget.value) return
  deleteTarget.value = null
  deleteError.value = null
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return
  form.localError = null
  versionDeleteError.value = null
  deleteError.value = null
  deletingTarget.value = true
  try {
    if (target.kind === 'dataset-version') {
      await trainingStore.deleteVersion(target.id)
    } else if (target.kind === 'failed-job') {
      await trainingStore.deleteJob(target.id)
      if (routeView.value === 'job' && routeId.value === target.id) navigate('/train-tune')
    } else {
      await trainingStore.deleteModel(target.id)
      if (routeView.value === 'result' && routeId.value === target.id) navigate('/train-tune')
    }
    deleteTarget.value = null
  } catch (err) {
    const message = errorMessage(err, 'Gagal menghapus data Train Tune')
    deleteError.value = message
    if (target.kind === 'dataset-version') versionDeleteError.value = message
  } finally {
    deletingTarget.value = false
  }
}

function openResultFromJob(job: TrainingJob | null) {
  if (!job) return
  const model = trainingStore.findModelByJobId(job.id)
  if (model) openResult(model.id)
}

async function recomputeFailedJob(jobId: string) {
  const job = await trainingStore.recomputeJob(jobId)
  navigate(`/train-tune/jobs/${job.id}`)
}
</script>

<template>
  <div class="h-screen bg-canvas text-ink flex flex-col">
    <header class="flex items-center justify-between px-(--spacing-lg) h-14 border-b border-hairline bg-canvas shrink-0">
      <button class="flex items-center gap-2 cursor-pointer" @click="goInference">
        <img src="/favicon.png" alt="LabelLens" class="w-7 h-7 rounded-(--radius-sm)" />
        <span class="font-bold text-lg tracking-tight">
          <span class="text-ink">Label</span><span class="text-primary">Lens</span>
        </span>
      </button>

      <div class="flex items-center gap-3">
        <button class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink" @click="goInference">
          Switch Mode
        </button>
        <button class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink" @click="navigate('/datasets')">
          Datasets
        </button>

        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="yoloeStatus === 'loaded' ? 'bg-primary' : yoloeStatus === 'no-model' ? 'bg-yellow-500' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ yoloeStatus === 'loaded' ? 'YOLOE Ready' : yoloeStatus === 'no-model' ? 'YOLOE Idle' : 'Offline' }}</span>
        </div>
        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="samStatus === 'loaded' ? 'bg-primary' : samStatus === 'available' ? 'bg-yellow-500' : samStatus === 'disabled' ? 'bg-gray-400' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ samStatus === 'loaded' ? 'SAM Ready' : samStatus === 'available' ? 'SAM Idle' : samStatus === 'disabled' ? 'SAM Off' : 'Offline' }}</span>
        </div>

        <button class="p-1.5 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer" :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'" @click="toggle()">
          <svg v-if="theme === 'dark'" class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5" />
            <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
          <svg v-else class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </button>
      </div>
    </header>

    <main class="flex-1 min-h-0 overflow-auto bg-canvas-soft">
      <div v-if="routeView === 'builder'" class="max-w-[1340px] mx-auto px-(--spacing-xl) py-(--spacing-xl)">
        <section class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-(--spacing-lg) items-start">
          <div class="space-y-(--spacing-lg)">
            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
              <div class="flex flex-col gap-(--spacing-xs) mb-(--spacing-xl)">
                <span class="text-[12px] uppercase tracking-[0.16em] text-primary font-medium">Train Tune</span>
                <h1 class="text-[32px] leading-[1.1] tracking-[-0.72px] font-medium text-ink">Build Training Run</h1>
                <p class="max-w-[720px] text-[14px] leading-[1.55] text-ink-mute">
                  Snapshot a live dataset or imported export zip, prepare a deterministic training version, then queue a YOLO fine-tune run with explicit GPU policy and artifact history.
                </p>
              </div>

              <div class="train-stepper mb-(--spacing-xxl)">
                <button
                  v-for="(stepItem, index) in builderSteps"
                  :key="stepItem.title"
                  type="button"
                  class="train-step"
                  :class="{ 'is-active': builderStep === index + 1, 'is-complete': builderStep > index + 1 }"
                  :disabled="index + 1 > builderStep"
                  @click="openBuilderStep(index + 1)"
                >
                  <span>{{ index + 1 }}</span>
                  <strong>{{ stepItem.short }}</strong>
                </button>
              </div>

              <div class="space-y-(--spacing-xxl)">
                <section v-if="builderStep === 1" class="space-y-(--spacing-md)">
                  <div class="flex items-center justify-between gap-(--spacing-md)">
                    <div>
                      <h2 class="text-[18px] font-medium text-ink">Dataset Source</h2>
                      <p class="text-[13px] text-ink-mute leading-[1.45]">Choose whether this run starts from a managed project or a previously exported zip.</p>
                    </div>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-md)">
                    <button type="button" class="train-choice" :class="form.sourceType === 'live' ? 'is-active' : ''" @click="form.sourceType = 'live'">
                      <strong>Live Dataset</strong>
                      <span>Use accepted annotations from an existing Dataset Manager project.</span>
                    </button>
                    <button type="button" class="train-choice" :class="form.sourceType === 'zip' ? 'is-active' : ''" @click="form.sourceType = 'zip'">
                      <strong>Export ZIP</strong>
                      <span>Import a YOLO export package and preserve its file naming and split metadata.</span>
                    </button>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-md)">
                    <label class="train-field">
                      <span>Version Name</span>
                      <input v-model="form.versionName" placeholder="bolt-dataset-v1" />
                    </label>
                    <label v-if="form.sourceType === 'live'" class="train-field">
                      <span>Dataset Project</span>
                      <select v-model="form.selectedDataset">
                        <option value="" disabled>Select dataset...</option>
                        <option v-for="project in datasetStore.projects" :key="project.name" :value="project.name">{{ project.name }}</option>
                      </select>
                    </label>
                    <label v-else class="train-field">
                      <span>Export ZIP</span>
                      <input type="file" accept=".zip" @change="onZipChange" />
                    </label>
                  </div>
                </section>

                <section v-else-if="builderStep === 3" class="space-y-(--spacing-md)">
                  <div>
                    <h2 class="text-[18px] font-medium text-ink">Versioning, Split, and Prep</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Deterministic split, preprocessing profile, and augmentation preset are stored inside the immutable dataset version.</p>
                  </div>
                  <div class="train-version-flow">
                    <div class="train-version-lane train-version-split">
                      <div class="train-version-title">
                        <strong class="train-label-with-info">Train / Val / Test <span class="train-param-help" tabindex="0" aria-label="Train/Val/Test controls how images are split for learning, validation, and final holdout evaluation." data-tip="Train learns model weights, Val checks each epoch, Test is held out for final evaluation.">?</span></strong>
                        <span>{{ splitPolicySummary }}</span>
                      </div>
                      <div class="train-split-bar" aria-label="Dataset split preview">
                        <span
                          v-for="segment in splitSegments"
                          :key="segment.label"
                          :class="['train-split-segment', segment.className]"
                          :style="{ flexBasis: `${Math.max(0, segment.value)}%` }"
                        >{{ segment.label }} {{ segment.value }}%</span>
                      </div>
                      <div class="train-version-fields is-split">
                        <label v-if="form.sourceType === 'zip'" class="train-field">
                          <span class="train-label-with-info">Split Mode <span class="train-param-help" tabindex="0" aria-label="Use existing zip folders or regenerate deterministic train validation test folders." data-tip="Use existing zip folders, or regenerate a deterministic split from all labeled images.">?</span></span>
                          <select v-model="form.splitMode">
                            <option value="existing">Use existing split</option>
                            <option value="regenerate">Regenerate split</option>
                          </select>
                        </label>
                        <label class="train-field"><span class="train-label-with-info">Train % <span class="train-param-help" tabindex="0" aria-label="Training image percentage." data-tip="Images used to update model weights during training.">?</span></span><input v-model.number="form.splitTrain" type="number" min="0" max="100" /></label>
                        <label class="train-field"><span class="train-label-with-info">Val % <span class="train-param-help" tabindex="0" aria-label="Validation image percentage." data-tip="Images used to measure each epoch and choose the best checkpoint.">?</span></span><input v-model.number="form.splitVal" type="number" min="0" max="100" /></label>
                        <label class="train-field"><span class="train-label-with-info">Test % <span class="train-param-help" tabindex="0" aria-label="Test image percentage." data-tip="Held-out images reserved for final evaluation after training.">?</span></span><input v-model.number="form.splitTest" type="number" min="0" max="100" /></label>
                      </div>
                      <div :class="['train-version-status', totalSplit === 100 ? 'is-valid' : 'is-invalid']">
                        <span>Split total</span>
                        <strong>{{ totalSplit }}%</strong>
                        <small>{{ totalSplit === 100 ? 'Ready for snapshot' : 'Train, val, and test must total 100%' }}</small>
                      </div>
                    </div>

                    <div class="train-version-lane">
                      <div class="train-version-title">
                        <strong class="train-label-with-info">Preprocessing <span class="train-param-help" tabindex="0" aria-label="Preprocessing controls image normalization before snapshot training." data-tip="Controls image orientation and resize handling before the immutable snapshot is trained.">?</span></strong>
                        <span>Stored with the snapshot before the run is queued.</span>
                      </div>
                      <div class="train-version-fields">
                        <label class="train-field"><span class="train-label-with-info">Resize Mode <span class="train-param-help" tabindex="0" aria-label="Resize behavior before training." data-tip="Keep original dimensions or fit images to the selected training resolution.">?</span></span><select v-model="form.resizeMode"><option value="keep">Keep original size</option><option value="fit">Fit to train resolution</option></select></label>
                        <label class="train-field"><span class="train-label-with-info">Auto Orient <span class="train-param-help" tabindex="0" aria-label="Apply EXIF orientation before training." data-tip="Applies EXIF orientation so images train in the same direction users see them.">?</span></span><select v-model="form.autoOrient"><option :value="true">Enabled</option><option :value="false">Disabled</option></select></label>
                      </div>
                      <p class="train-version-note">{{ preprocessingSummary }}</p>
                    </div>

                    <div class="train-version-lane">
                      <div class="train-version-title">
                        <strong class="train-label-with-info">Augmentation <span class="train-param-help" tabindex="0" aria-label="Augmentation expands training variation." data-tip="Adds controlled visual variation so the detector generalizes better.">?</span></strong>
                        <span>Preset kept in version metadata for repeatable run setup.</span>
                      </div>
                      <label class="train-field"><span class="train-label-with-info">Profile <span class="train-param-help" tabindex="0" aria-label="Augmentation profile." data-tip="Baseline is conservative; Standard applies broader variation for stronger robustness.">?</span></span><select v-model="form.augmentationProfile"><option value="baseline">Baseline</option><option value="standard">Standard</option></select></label>
                      <p class="train-version-note">{{ augmentationSummary }}</p>
                    </div>
                  </div>
                </section>

                <section v-else-if="builderStep === 2" class="space-y-(--spacing-md)">
                  <div>
                    <h2 class="text-[18px] font-medium text-ink">Training Configuration</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Pick the YOLO family, detection checkpoint, and GPU mode used to schedule this bbox training run.</p>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
                    <label class="train-field"><span class="train-label-with-info">Family <span class="train-param-help" tabindex="0" aria-label="YOLO architecture family." data-tip="Selects the YOLO detector family used as the base architecture.">?</span></span><select v-model="form.family"><option value="yolo11">YOLO11</option><option value="yolo26">YOLO26</option></select></label>
                    <label class="train-field"><span class="train-label-with-info">Size <span class="train-param-help" tabindex="0" aria-label="Model size tier." data-tip="Larger sizes can improve accuracy but use more VRAM and train slower.">?</span></span><select v-model="form.size"><option value="n">n</option><option value="s">s</option><option value="m">m</option><option value="l">l</option></select></label>
                    <label class="train-field train-field-span"><span class="train-label-with-info">Base Detection Checkpoint <span class="train-param-help" tabindex="0" aria-label="Starting model weights." data-tip="Detection checkpoint used as starting weights. Segmentation checkpoints are rejected for bbox-only training.">?</span></span><input v-model="form.baseCheckpoint" placeholder="yolo26n.pt" /></label>
                    <label class="train-field"><span class="train-label-with-info">Job Name <span class="train-param-help" tabindex="0" aria-label="Human-readable run name." data-tip="Name used to identify this run and its output artifact folder.">?</span></span><input v-model="form.jobName" placeholder="bolt-detector" /></label>
                    <label class="train-field"><span class="train-label-with-info">Training Mode <span class="train-param-help" tabindex="0" aria-label="GPU scheduling mode." data-tip="Standard uses one GPU; High-Speed uses both GPUs and waits until inference is idle.">?</span></span><select v-model="form.trainingMode"><option value="standard">Standard · 1x RTX 5080</option><option value="high_speed">High-Speed · 2x RTX 5080</option></select></label>
                    <label class="train-field"><span class="train-label-with-info">Epochs <span class="train-param-help" tabindex="0" aria-label="Number of full training passes." data-tip="How many full passes through the training split the worker runs.">?</span></span><input v-model.number="form.epochs" type="number" min="1" /></label>
                    <label class="train-field"><span class="train-label-with-info">Image Size <span class="train-param-help" tabindex="0" aria-label="Training image resolution." data-tip="Input resolution in pixels. Higher values keep detail but cost more VRAM.">?</span></span><input v-model.number="form.imgsz" type="number" min="320" step="32" /></label>
                    <label class="train-field"><span class="train-label-with-info">Batch <span class="train-param-help" tabindex="0" aria-label="Images per training step." data-tip="Number of images processed per step. Higher batch can be faster but uses more VRAM.">?</span></span><input v-model.number="form.batch" type="number" min="1" /></label>
                    <label class="train-field"><span class="train-label-with-info">Workers <span class="train-param-help" tabindex="0" aria-label="Data loader worker count." data-tip="Parallel workers used to load and prepare training images.">?</span></span><input v-model.number="form.workers" type="number" min="1" /></label>
                  </div>
                  <p class="train-version-note">Train Tune versions currently store bbox labels. Use a detection checkpoint here; segmentation checkpoints require mask labels and are rejected by the worker.</p>
                </section>

                <section v-else-if="builderStep === 4" class="space-y-(--spacing-md)">
                  <div>
                    <h2 class="text-[18px] font-medium text-ink">Snapshot Preview</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Confirm the immutable Dataset Version policy before storing this snapshot.</p>
                  </div>
                  <div class="train-version-preview">
                    <div class="train-preview-title">
                      <span>Snapshot Draft</span>
                      <strong>{{ previewVersionName }}</strong>
                    </div>
                    <div class="train-preview-grid">
                      <div><span>Source</span><strong>{{ previewSourceName }}</strong></div>
                      <div><span>Architecture</span><strong>{{ form.family }} {{ form.size }} / {{ form.baseCheckpoint }}</strong></div>
                      <div><span>Split</span><strong>{{ form.splitTrain }} / {{ form.splitVal }} / {{ form.splitTest }}</strong></div>
                      <div><span>Prep</span><strong>{{ form.resizeMode === 'keep' ? 'Keep size' : 'Fit size' }} / {{ form.autoOrient ? 'Orient' : 'Raw orient' }}</strong></div>
                      <div><span>Augment</span><strong>{{ form.augmentationProfile }}</strong></div>
                    </div>
                  </div>
                </section>

                <section v-else class="space-y-(--spacing-md)">
                  <div class="train-create-panel">
                    <div>
                      <span>Create immutable snapshot</span>
                      <strong>{{ previewVersionName }}</strong>
                      <p>Split, preprocessing, and augmentation cannot be edited after creation. Delete and create a new version for a changed policy.</p>
                    </div>
                    <button class="dataset-primary-button" @click="buildVersion">Create Dataset Version</button>
                  </div>
                </section>

                <section class="space-y-(--spacing-md) border-t border-hairline pt-(--spacing-xl)">
                  <div class="flex flex-wrap items-center gap-(--spacing-md)">
                    <button v-if="builderStep > 1" class="dataset-secondary-button" @click="previousBuilderStep">Back</button>
                    <button v-if="builderStep < builderSteps.length" class="dataset-primary-button" @click="nextBuilderStep">Continue</button>
                  </div>
                  <p v-if="form.trainingMode === 'high_speed'" class="train-warning">High-Speed Mode uses both RTX 5080 devices. The job only starts when inference is idle, and new inference requests remain blocked until the run finishes.</p>
                  <p v-if="form.localError || trainingStore.error" class="train-error">{{ form.localError || trainingStore.error }}</p>
                </section>
              </div>
            </div>

            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
              <div class="flex items-center justify-between gap-(--spacing-md) mb-(--spacing-lg)">
                <div>
                  <span class="text-[12px] uppercase tracking-[0.16em] text-primary font-medium">Summary</span>
                  <h2 class="text-[24px] tracking-[-0.42px] font-medium text-ink mt-(--spacing-xs)">Training Preview</h2>
                </div>
                <div class="flex flex-wrap justify-end gap-(--spacing-sm)">
                  <button class="dataset-secondary-button" :disabled="!builderReady" @click="refreshEstimate">Refresh Estimate</button>
                  <button class="dataset-primary-button" :disabled="!trainingStore.currentEstimate" @click="submitJob">Start Training Job</button>
                </div>
              </div>

              <div v-if="builderSummary" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
                <div class="train-stat train-stat-wide"><span>Dataset Version</span><strong>{{ trainingStore.selectedVersion?.version_name }}</strong><small>{{ trainingStore.selectedVersion?.source_name }}</small></div>
                <div class="train-stat"><span>Usable Images</span><strong>{{ builderSummary.usable_labeled_images }}</strong><small>{{ builderSummary.original_file_count }} original files</small></div>
                <div class="train-stat"><span>Annotations</span><strong>{{ builderSummary.total_annotations }}</strong><small>{{ builderSummary.average_annotations_per_image }} avg / image</small></div>
                <div class="train-stat"><span>Classes</span><strong>{{ builderSummary.class_count }}</strong><small>{{ builderSummary.classes.join(', ') }}</small></div>
                <div class="train-stat"><span>Split Policy</span><strong>{{ versionSplit(trainingStore.selectedVersion) }}</strong><small>{{ versionSplitCounts(trainingStore.selectedVersion) }} images train / val / test</small></div>
                <div class="train-stat"><span>Preprocessing</span><strong>{{ versionResize(trainingStore.selectedVersion) }}</strong><small>{{ versionOrient(trainingStore.selectedVersion) }}</small></div>
                <div class="train-stat"><span>Augmentation</span><strong>{{ versionAugment(trainingStore.selectedVersion) }}</strong><small>Locked in Dataset Version</small></div>
                <div class="train-stat"><span>Training Config</span><strong>{{ form.family }} {{ form.size }} / {{ form.epochs }} epochs</strong><small>{{ form.trainingMode === 'high_speed' ? '2x RTX 5080' : '1x RTX 5080' }} · batch {{ form.batch }}</small></div>
                <div class="train-stat" v-if="trainingStore.currentEstimate"><span>Estimate</span><strong>{{ trainingStore.currentEstimate.estimated_time_range_minutes[0] }}-{{ trainingStore.currentEstimate.estimated_time_range_minutes[1] }} min</strong><small>{{ trainingStore.currentEstimate.estimated_disk_usage_mb }} MB · {{ trainingStore.currentEstimate.estimated_vram_tier }} VRAM tier</small></div>
              </div>
              <div v-else class="text-[13px] text-ink-mute">Create or select a Dataset Version first. Split, preprocessing, and augmentation stay locked after the snapshot is stored.</div>
            </div>
          </div>

          <aside class="space-y-(--spacing-lg) xl:sticky xl:top-(--spacing-lg)">
            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
              <div class="flex items-center justify-between mb-(--spacing-md)">
                <h3 class="text-[16px] font-medium text-ink">Training Jobs</h3>
                <button class="dataset-secondary-button !px-2 !py-1" @click="trainingStore.refreshJobs()">Refresh</button>
              </div>
              <div class="train-list">
                <div v-for="job in trainingStore.jobs" :key="job.id" class="train-row-shell">
                  <button class="train-list-row train-list-row-main" @click="openJob(job.id)">
                    <div>
                      <strong>{{ job.job_name }}</strong>
                      <span>{{ job.architecture_family }} / {{ job.architecture_size }} / {{ job.training_mode }}</span>
                    </div>
                    <span :class="['dataset-status-pill', `is-${job.status}`]">{{ job.status }}</span>
                  </button>
                  <div v-if="job.status === 'failed'" class="train-list-actions">
                    <button class="train-mini-action" @click.stop="recomputeFailedJob(job.id)">Re-compute</button>
                    <button class="train-mini-action is-danger" @click.stop="requestFailedJobDelete(job)">Delete</button>
                  </div>
                </div>
                <div v-if="!trainingStore.jobs.length" class="train-empty">No training jobs yet.</div>
              </div>
            </div>

            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
              <div class="flex items-center justify-between mb-(--spacing-md)">
                <h3 class="text-[16px] font-medium text-ink">Dataset Versions</h3>
                <button class="dataset-secondary-button !px-2 !py-1" @click="trainingStore.refreshVersions()">Refresh</button>
              </div>
              <div class="train-list">
                <div v-for="version in trainingStore.versions" :key="version.id" class="train-version-card" :class="trainingStore.selectedVersion?.id === version.id ? 'is-selected' : ''">
                  <button class="train-version-select" @click="pickVersion(version)">
                    <div>
                      <strong>{{ version.version_name }}</strong>
                      <span>{{ version.source_type }} / {{ version.summary.usable_labeled_images }} images</span>
                    </div>
                  </button>
                  <button class="train-mini-action is-danger train-version-delete" @click.stop="requestDatasetVersionDelete(version)">Delete</button>
                </div>
                <div v-if="!trainingStore.versions.length" class="train-empty">No dataset versions yet.</div>
              </div>
              <p v-if="versionDeleteError" class="train-error mt-(--spacing-md)">{{ versionDeleteError }}</p>
            </div>

            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
              <div class="flex items-center justify-between mb-(--spacing-md)">
                <h3 class="text-[16px] font-medium text-ink">Model Versions</h3>
                <button class="dataset-secondary-button !px-2 !py-1" @click="trainingStore.refreshModels()">Refresh</button>
              </div>
              <div class="train-list">
                <div v-for="model in trainingStore.models" :key="model.id" class="train-model-card">
                  <button class="train-list-row train-model-open" @click="openResult(model.id)">
                    <div>
                      <strong>{{ model.model_name }}</strong>
                      <span>{{ model.family }} / {{ model.size }}</span>
                    </div>
                  </button>
                  <div class="train-model-meta">
                    <span class="dataset-status-pill is-completed">{{ model.status }}</span>
                    <button class="train-mini-action is-danger" @click.stop="requestModelDelete(model)">Delete</button>
                  </div>
                </div>
                <div v-if="!trainingStore.models.length" class="train-empty">No trained models yet.</div>
              </div>
            </div>
          </aside>
        </section>
      </div>

      <div v-else-if="routeView === 'job' && trainingStore.selectedJob" class="max-w-[1340px] mx-auto px-(--spacing-xl) py-(--spacing-xl)">
        <section class="space-y-(--spacing-lg)">
          <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
            <div class="flex flex-wrap items-start justify-between gap-(--spacing-lg)">
              <div>
                <button class="train-link train-link-inline" @click="navigate('/train-tune')"><svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6" /></svg><span>Back to Train Tune Builder</span></button>
                <h1 class="text-[32px] leading-[1.1] tracking-[-0.72px] font-medium text-ink mt-(--spacing-sm)">Live Progress Training</h1>
                <p class="text-[14px] text-ink-mute leading-[1.55] max-w-[780px]">Monitor the active training run, watch epoch metrics stream in live, inspect checkpoints, and jump into the final registered result when the job completes.</p>
              </div>
              <div class="flex items-center gap-(--spacing-md) flex-wrap">
                <span :class="['dataset-status-pill', `is-${trainingStore.selectedJob.status}`]">{{ trainingStore.selectedJob.status }}</span>
                <button v-if="trainingStore.selectedJob.status === 'completed'" class="dataset-primary-button" @click="openResultFromJob(trainingStore.selectedJob)">Open Result</button>
                <template v-else-if="trainingStore.selectedJob.status === 'failed'">
                  <button class="dataset-primary-button" @click="recomputeFailedJob(trainingStore.selectedJob.id)">Re-compute</button>
                  <button class="dataset-secondary-button" @click="requestFailedJobDelete(trainingStore.selectedJob)">Delete</button>
                </template>
                <button v-else-if="!['failed', 'cancelled'].includes(trainingStore.selectedJob.status)" class="dataset-secondary-button" @click="trainingStore.cancelJob(trainingStore.selectedJob.id)">Cancel Job</button>
              </div>
            </div>
          </div>

          <div v-if="trainingStore.selectedJob.failure_reason" class="train-error">{{ trainingStore.selectedJob.failure_reason }}</div>

          <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-(--spacing-lg)">
            <div class="space-y-(--spacing-lg)">
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
                <div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-(--spacing-md)">
                  <div class="train-stat"><span>Job</span><strong>{{ trainingStore.selectedJob.job_name }}</strong><small>{{ trainingStore.selectedJob.architecture_family }} / {{ trainingStore.selectedJob.architecture_size }}</small></div>
                  <div class="train-stat"><span>Dataset Version</span><strong>{{ trainingStore.selectedJob.dataset_version_name }}</strong><small>{{ trainingStore.selectedJob.class_names.join(', ') }}</small></div>
                  <div class="train-stat"><span>Epoch</span><strong>{{ latestMetric ? `${latestMetric.epoch}/${latestMetric.total_epochs ?? trainingStore.selectedJob.epochs}` : `0/${trainingStore.selectedJob.epochs}` }}</strong><small>{{ trainingStore.selectedJob.training_mode }}</small></div>
                  <div class="train-stat"><span>ETA</span><strong>{{ latestMetric?.eta_sec ?? 0 }} sec</strong><small>{{ latestMetric?.elapsed_sec ?? 0 }} sec elapsed</small></div>
                  <div class="train-stat"><span>mAP50</span><strong>{{ latestMetric?.map50 ?? 0 }}</strong><small>mAP50-95 {{ latestMetric?.map50_95 ?? 0 }}</small></div>
                  <div class="train-stat"><span>Precision / Recall</span><strong>{{ latestMetric?.precision ?? 0 }} / {{ latestMetric?.recall ?? 0 }}</strong><small>lr {{ latestMetric?.lr ?? 0 }}</small></div>
                </div>
              </div>

              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
                <div class="flex items-center justify-between gap-(--spacing-md) mb-(--spacing-lg)">
                  <div>
                    <h2 class="text-[20px] font-medium text-ink">Metric Trends</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Compact evaluation and loss curves from the live epoch stream.</p>
                  </div>
                  <span class="text-[12px] text-ink-mute">{{ trainingStore.jobMetrics.length }} points</span>
                </div>
                <div class="train-trend-grid">
                  <div v-for="trend in metricTrends" :key="trend.key" :class="['train-trend-card', trend.tone]">
                    <div class="train-trend-head"><span>{{ trend.label }}</span><strong>{{ metricLabel(metricValue(latestMetric, trend.key)) }}</strong></div>
                    <svg v-if="trainingStore.jobMetrics.length" class="train-sparkline" viewBox="0 0 180 54" preserveAspectRatio="none" aria-hidden="true">
                      <path d="M5 49 H175" />
                      <polyline :points="sparklinePoints(trainingStore.jobMetrics, trend.key)" />
                    </svg>
                    <div v-else class="train-trend-empty">Waiting for epochs</div>
                  </div>
                </div>
              </div>

              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
                <div class="flex items-center justify-between gap-(--spacing-md) mb-(--spacing-lg)">
                  <div>
                    <h2 class="text-[20px] font-medium text-ink">Epoch History</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Append-only epoch history for the current training run.</p>
                  </div>
                  <span class="text-[12px] text-ink-mute">{{ trainingStore.jobMetrics.length }} epochs captured</span>
                </div>
                <div class="train-metric-table train-metric-scroll">
                  <div class="train-metric-head"><span>Epoch</span><span>Train Loss</span><span>Val Loss</span><span>mAP50</span><span>mAP50-95</span><span>Precision</span><span>Recall</span></div>
                  <div v-for="point in trainingStore.jobMetrics" :key="point.epoch" class="train-metric-row">
                    <span>{{ point.epoch }}</span><span>{{ point.train_loss }}</span><span>{{ point.val_loss }}</span><span>{{ point.map50 }}</span><span>{{ point.map50_95 }}</span><span>{{ point.precision }}</span><span>{{ point.recall }}</span>
                  </div>
                  <div v-if="!trainingStore.jobMetrics.length" class="train-empty">No metrics yet.</div>
                </div>
              </div>
            </div>

            <aside class="space-y-(--spacing-lg)">
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <div class="flex items-center justify-between mb-(--spacing-md)">
                  <h3 class="text-[16px] font-medium text-ink">Live Event Log</h3>
                  <span class="text-[12px] text-ink-mute">{{ trainingStore.liveConnected ? 'streaming' : 'idle' }}</span>
                </div>
                <div class="train-log-block">
                  <div v-for="event in trainingStore.liveEvents" :key="`${event.timestamp}-${event.event}`" class="train-log-row">
                    <strong>{{ event.event }}</strong>
                    <span v-if="event.event === 'metric_update'">Epoch {{ event.epoch }} · mAP50 {{ event.map50 }} · ETA {{ event.eta_sec }} sec</span>
                    <span v-else-if="event.event === 'checkpoint_saved'">{{ event.path }}</span>
                    <span v-else-if="event.event === 'job_failed'">{{ event.error }}</span>
                    <span v-else-if="event.event === 'log_line'">{{ event.line }}</span>
                    <span v-else>{{ event.phase || event.best_model_path || 'state update' }}</span>
                  </div>
                  <div v-if="!trainingStore.liveEvents.length" class="train-empty">No live events yet.</div>
                </div>
              </div>
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Dataset + Training Configuration</h3>
                <div class="train-policy-grid">
                  <div><span>Dataset Version</span><strong>{{ liveSourceVersion?.version_name || trainingStore.selectedJob.dataset_version_name }}</strong><small>{{ liveSourceVersion?.source_name || 'linked snapshot' }}</small></div>
                  <div><span>Split</span><strong>{{ versionSplit(liveSourceVersion) }}</strong><small>{{ versionSplitCounts(liveSourceVersion) }} images</small></div>
                  <div><span>Preprocessing</span><strong>{{ versionResize(liveSourceVersion) }}</strong><small>{{ versionOrient(liveSourceVersion) }}</small></div>
                  <div><span>Augmentation</span><strong>{{ versionAugment(liveSourceVersion) }}</strong><small>immutable profile</small></div>
                  <div><span>Checkpoint</span><strong>{{ trainingStore.selectedJob.base_checkpoint }}</strong><small>{{ trainingStore.selectedJob.architecture_family }} {{ trainingStore.selectedJob.architecture_size }}</small></div>
                  <div><span>Run Settings</span><strong>{{ trainingStore.selectedJob.epochs }} epochs / {{ trainingStore.selectedJob.imgsz }} px</strong><small>batch {{ trainingStore.selectedJob.batch }} / workers {{ trainingStore.selectedJob.workers }} / {{ trainingStore.selectedJob.training_mode }}</small></div>
                </div>
              </div>
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Artifacts</h3>
                <div class="space-y-(--spacing-sm) text-[13px] text-ink-mute">
                  <div><strong class="text-ink">Output</strong><br />{{ trainingStore.selectedJob.output_dir }}</div>
                  <div><strong class="text-ink">Latest checkpoint</strong><br />{{ trainingStore.selectedJob.last_checkpoint_path || 'Waiting for first checkpoint...' }}</div>
                  <div><strong class="text-ink">Best model</strong><br />{{ trainingStore.selectedJob.best_model_path || 'Available after completion' }}</div>
                </div>
              </div>
            </aside>
          </div>
        </section>
      </div>

      <div v-else-if="routeView === 'result' && trainingStore.selectedModel" class="max-w-[1340px] mx-auto px-(--spacing-xl) py-(--spacing-xl)">
        <section class="space-y-(--spacing-lg)">
          <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
            <button class="train-link train-link-inline" @click="navigate('/train-tune')"><svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6" /></svg><span>Back to Train Tune Builder</span></button>
            <div class="flex flex-wrap items-start justify-between gap-(--spacing-lg) mt-(--spacing-sm)">
              <div>
                <h1 class="text-[32px] leading-[1.1] tracking-[-0.72px] font-medium text-ink">Train Tune Result</h1>
                <p class="text-[14px] text-ink-mute leading-[1.55] max-w-[760px]">Registered model artifact, linked dataset version, and best metrics from the completed training job.</p>
              </div>
              <div class="flex items-center gap-(--spacing-sm)">
                <span class="dataset-status-pill is-completed">{{ trainingStore.selectedModel.status }}</span>
                <button class="dataset-secondary-button" @click="requestModelDelete(trainingStore.selectedModel)">Delete Model</button>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-(--spacing-lg)">
            <div class="space-y-(--spacing-lg)">
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-(--spacing-md)">
                  <div class="train-stat"><span>Model Name</span><strong>{{ trainingStore.selectedModel.model_name }}</strong><small>{{ trainingStore.selectedModel.version_name }}</small></div>
                  <div class="train-stat"><span>Family</span><strong>{{ trainingStore.selectedModel.family }}</strong><small>size {{ trainingStore.selectedModel.size }}</small></div>
                  <div class="train-stat"><span>Classes</span><strong>{{ trainingStore.selectedModel.class_names.length }}</strong><small>{{ trainingStore.selectedModel.class_names.join(', ') }}</small></div>
                  <div class="train-stat"><span>Best Artifact</span><strong>{{ trainingStore.selectedModel.best_model_path }}</strong><small>registered output</small></div>
                  <div class="train-stat"><span>Source Dataset Version</span><strong>{{ resultSourceVersion?.version_name || trainingStore.selectedModel.dataset_version_id }}</strong><small>{{ resultSourceVersion?.source_name || 'linked snapshot' }}</small></div>
                  <div class="train-stat"><span>Training Job</span><strong>{{ resultJob?.job_name || trainingStore.selectedModel.job_id }}</strong><small>{{ resultJob?.training_mode || 'completed run' }}</small></div>
                </div>
              </div>

              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
                <div class="flex items-center justify-between gap-(--spacing-md) mb-(--spacing-lg)">
                  <div>
                    <h2 class="text-[20px] font-medium text-ink">Best Metrics</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Final best-known values registered alongside the exported model version.</p>
                  </div>
                  <button v-if="resultJob" class="dataset-secondary-button" @click="openJob(resultJob.id)">Open Training Timeline</button>
                </div>
                <div v-if="trainingStore.selectedModel.metrics_best" class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-(--spacing-md)">
                  <div class="train-stat"><span>mAP50</span><strong>{{ trainingStore.selectedModel.metrics_best.map50 }}</strong></div>
                  <div class="train-stat"><span>mAP50-95</span><strong>{{ trainingStore.selectedModel.metrics_best.map50_95 }}</strong></div>
                  <div class="train-stat"><span>Precision</span><strong>{{ trainingStore.selectedModel.metrics_best.precision }}</strong></div>
                  <div class="train-stat"><span>Recall</span><strong>{{ trainingStore.selectedModel.metrics_best.recall }}</strong></div>
                  <div class="train-stat"><span>Train Loss</span><strong>{{ trainingStore.selectedModel.metrics_best.train_loss }}</strong></div>
                  <div class="train-stat"><span>Val Loss</span><strong>{{ trainingStore.selectedModel.metrics_best.val_loss }}</strong></div>
                </div>
                <div v-else class="train-empty">No best metrics recorded yet.</div>
                <div class="train-trend-grid mt-(--spacing-lg)">
                  <div v-for="trend in metricTrends" :key="trend.key" :class="['train-trend-card', trend.tone]">
                    <div class="train-trend-head"><span>{{ trend.label }}</span><strong>{{ metricLabel(resultMetricValue(trend.key)) }}</strong></div>
                    <svg v-if="trainingStore.jobMetrics.length" class="train-sparkline" viewBox="0 0 180 54" preserveAspectRatio="none" aria-hidden="true">
                      <path d="M5 49 H175" />
                      <polyline :points="sparklinePoints(trainingStore.jobMetrics, trend.key)" />
                    </svg>
                    <div v-else class="train-trend-empty">No epoch trend recorded</div>
                  </div>
                </div>
              </div>
            </div>

            <aside class="space-y-(--spacing-lg)">
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Result Context</h3>
                <div class="space-y-(--spacing-sm) text-[13px] text-ink-mute">
                  <div><strong class="text-ink">Created</strong><br />{{ trainingStore.selectedModel.created_at }}</div>
                  <div class="train-path-row"><strong class="text-ink">Dataset Version Path</strong><span>{{ resultSourceVersion?.storage_path || 'N/A' }}</span></div>
                  <div class="train-path-row"><strong class="text-ink">Job Output Path</strong><span>{{ resultJob?.output_dir || 'N/A' }}</span></div>
                </div>
              </div>

              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Dataset Version Configuration</h3>
                <div class="train-policy-grid">
                  <div><span>Version</span><strong>{{ resultSourceVersion?.version_name || trainingStore.selectedModel.dataset_version_id }}</strong><small>{{ resultSourceVersion?.source_name || 'linked snapshot' }}</small></div>
                  <div><span>Split</span><strong>{{ versionSplit(resultSourceVersion) }}</strong><small>{{ versionSplitCounts(resultSourceVersion) }} images</small></div>
                  <div><span>Preprocessing</span><strong>{{ versionResize(resultSourceVersion) }}</strong><small>{{ versionOrient(resultSourceVersion) }}</small></div>
                  <div><span>Augmentation</span><strong>{{ versionAugment(resultSourceVersion) }}</strong><small>immutable profile</small></div>
                </div>
              </div>

              <div v-if="resultJob" class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Training Configuration</h3>
                <div class="train-policy-grid">
                  <div><span>Checkpoint</span><strong>{{ resultJob.base_checkpoint }}</strong><small>{{ resultJob.architecture_family }} {{ resultJob.architecture_size }}</small></div>
                  <div><span>Run Settings</span><strong>{{ resultJob.epochs }} epochs / {{ resultJob.imgsz }} px</strong><small>batch {{ resultJob.batch }} / workers {{ resultJob.workers }}</small></div>
                  <div><span>Compute</span><strong>{{ resultJob.training_mode }}</strong><small>{{ resultJob.device_policy }}</small></div>
                </div>
              </div>

              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Other Model Versions</h3>
                <div class="train-list">
                  <button v-for="model in trainingStore.models" :key="model.id" class="train-list-row" @click="openResult(model.id)">
                    <div>
                      <strong>{{ model.model_name }}</strong>
                      <span>{{ model.family }} / {{ model.size }}</span>
                    </div>
                  </button>
                </div>
              </div>
            </aside>
          </div>
        </section>
      </div>
    </main>

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 scale-[0.98]"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-to-class="opacity-0 scale-[0.98]"
    >
      <div v-if="deleteTarget" class="dataset-dialog-backdrop" @click.self="closeDeleteDialog">
        <section class="dataset-delete-dialog">
          <header class="dataset-modal-header">
            <div>
              <h3 class="dataset-modal-title">{{ deleteTarget.kind === 'model-version' ? 'Delete Model Version' : deleteTarget.kind === 'failed-job' ? 'Delete Training Job' : 'Delete Dataset Version' }}</h3>
              <p class="dataset-modal-copy">This action cannot be undone.</p>
            </div>
            <button class="dataset-modal-close" :disabled="deletingTarget" @click="closeDeleteDialog" aria-label="Close Train Tune delete dialog">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </header>
          <div class="dataset-modal-body dataset-form-stack">
            <p v-if="deleteTarget.kind === 'dataset-version'" class="text-[13px] text-ink-mute leading-relaxed">
              Delete Dataset Version <span class="font-medium text-ink">{{ deleteTarget.name }}</span> and its immutable snapshot? Versions used by job or model history stay protected.
            </p>
            <p v-else-if="deleteTarget.kind === 'failed-job'" class="text-[13px] text-ink-mute leading-relaxed">
              Delete failed Training Job <span class="font-medium text-ink">{{ deleteTarget.name }}</span>, its metric history, and its output folder?
            </p>
            <p v-else class="text-[13px] text-ink-mute leading-relaxed">
              Delete Model Version <span class="font-medium text-ink">{{ deleteTarget.name }}</span>? Its linked Training Job <span class="font-medium text-ink">{{ deleteTarget.jobName }}</span>, metrics, and output folder will also be removed.
            </p>
            <p v-if="deleteError" class="train-error">{{ deleteError }}</p>
          </div>
          <footer class="dataset-modal-footer">
            <button class="dataset-secondary-button" :disabled="deletingTarget" @click="closeDeleteDialog">Cancel</button>
            <button class="dataset-primary-button" :disabled="deletingTarget" @click="confirmDelete">{{ deletingTarget ? 'Deleting...' : 'Delete' }}</button>
          </footer>
        </section>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.train-stepper { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.train-step { min-width: 0; min-height: 58px; display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); color: var(--color-ink-mute); background: var(--color-canvas); text-align: left; cursor: pointer; transition: border-color 160ms ease, background-color 160ms ease, color 160ms ease; }
.train-step:disabled { cursor: default; opacity: 0.55; }
.train-step span { width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; border-radius: 999px; border: 1px solid var(--color-hairline-strong); font-size: 12px; }
.train-step strong { min-width: 0; font-size: 12px; font-weight: 500; line-height: 1.25; color: inherit; }
.train-step.is-active { border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-hairline)); color: var(--color-ink); background: color-mix(in srgb, var(--color-primary) 10%, var(--color-canvas)); }
.train-step.is-active span, .train-step.is-complete span { border-color: color-mix(in srgb, var(--color-primary) 54%, var(--color-hairline)); color: var(--color-primary-deep); background: color-mix(in srgb, var(--color-primary) 14%, var(--color-canvas)); }
.train-create-panel { min-height: 142px; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 20px; border: 1px solid color-mix(in srgb, var(--color-primary) 28%, var(--color-hairline)); border-radius: var(--radius-md); background: color-mix(in srgb, var(--color-primary) 8%, var(--color-canvas)); }
.train-create-panel div { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.train-create-panel span { color: var(--color-primary-deep); font-size: 12px; font-weight: 500; text-transform: uppercase; }
.train-create-panel strong { color: var(--color-ink); font-size: 20px; font-weight: 500; word-break: break-word; }
.train-create-panel p { max-width: 560px; margin: 0; color: var(--color-ink-mute); font-size: 13px; line-height: 1.5; }
.train-choice {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
  padding: 16px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
  cursor: pointer;
  transition: border-color 160ms ease, background-color 160ms ease;
}
.train-choice strong { font-size: 14px; color: var(--color-ink); }
.train-choice span { font-size: 12px; line-height: 1.45; color: var(--color-ink-mute); }
.train-choice.is-active { border-color: color-mix(in srgb, var(--color-primary) 42%, var(--color-hairline)); background: color-mix(in srgb, var(--color-primary) 10%, var(--color-canvas-soft)); }

.train-field { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--color-ink-mute); }
.train-field-span { grid-column: span 2; }
.train-field input, .train-field select {
  min-height: 40px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  color: var(--color-ink);
  padding: 0 12px;
}
.train-field input[type='file'] { padding: 10px 12px; }
.train-label-with-info { display: inline-flex !important; align-items: center; gap: 5px; min-width: 0; }
.train-param-help { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; flex: 0 0 auto; border: 1px solid var(--color-hairline-strong); border-radius: 999px; color: var(--color-ink-mute); background: var(--color-canvas); cursor: help; font-size: 10px; font-weight: 700; line-height: 1; text-transform: none; }
.train-param-help::after { content: attr(data-tip); position: absolute; left: 50%; bottom: calc(100% + 7px); z-index: 30; width: 250px; max-width: calc(100vw - 32px); padding: 8px 10px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); color: var(--color-ink); box-shadow: 0 12px 32px rgba(0, 0, 0, 0.16); font-size: 11px; font-weight: 500; line-height: 1.45; text-transform: none; letter-spacing: 0; transform: translateX(-50%) translateY(4px); opacity: 0; pointer-events: none; transition: opacity 140ms ease, transform 140ms ease; }
.train-param-help:hover::after, .train-param-help:focus-visible::after { opacity: 1; transform: translateX(-50%) translateY(0); }
.train-param-help:hover, .train-param-help:focus-visible { border-color: color-mix(in srgb, var(--color-primary) 45%, var(--color-hairline)); color: var(--color-primary-deep); }
.train-version-flow { display: grid; grid-template-columns: minmax(0, 1.4fr) repeat(2, minmax(0, 1fr)); border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas-soft); overflow: hidden; }
.train-version-lane { min-width: 0; display: flex; flex-direction: column; gap: 14px; padding: 16px; border-left: 1px solid var(--color-hairline); }
.train-version-lane:first-child { border-left: 0; }
.train-version-title { display: flex; flex-direction: column; gap: 4px; }
.train-version-title strong, .train-preview-title strong { color: var(--color-ink); font-size: 14px; font-weight: 500; }
.train-version-title span, .train-preview-title span { color: var(--color-ink-mute); font-size: 12px; line-height: 1.45; }
.train-version-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.train-version-fields.is-split { grid-template-columns: repeat(auto-fit, minmax(92px, 1fr)); }
.train-split-bar { display: flex; align-items: stretch; min-height: 42px; border: 1px solid var(--color-hairline-strong); border-radius: var(--radius-sm); background: var(--color-canvas); overflow: hidden; }
.train-split-segment { min-width: 0; display: flex; align-items: center; padding: 0 10px; color: #171717; font-size: 11px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.train-split-segment.is-train { background: #bbf7d0; }
.train-split-segment.is-val { background: #fde68a; }
.train-split-segment.is-test { background: #ddd6fe; }
.train-version-status { display: grid; grid-template-columns: auto auto minmax(0, 1fr); align-items: center; gap: 8px; min-height: 32px; color: var(--color-ink-mute); font-size: 12px; }
.train-version-status strong { color: var(--color-ink); font-size: 13px; }
.train-version-status small { min-width: 0; font-size: 12px; line-height: 1.4; }
.train-version-status.is-valid small { color: var(--color-primary-deep); }
.train-version-status.is-invalid small { color: #b91c1c; }
.train-version-note { margin: 0; min-height: 38px; padding: 10px 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); color: var(--color-ink-mute); background: var(--color-canvas); font-size: 12px; line-height: 1.5; }
.train-version-preview { display: flex; align-items: stretch; gap: 16px; padding: 14px 16px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas); }
.train-preview-title { width: min(180px, 100%); display: flex; flex-direction: column; justify-content: center; gap: 4px; padding-right: 16px; border-right: 1px solid var(--color-hairline); }
.train-preview-grid { flex: 1; min-width: 0; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.train-preview-grid div { min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: 4px; }
.train-preview-grid span { color: var(--color-ink-mute); font-size: 11px; text-transform: uppercase; }
.train-preview-grid strong { color: var(--color-ink); font-size: 13px; font-weight: 500; line-height: 1.4; word-break: break-word; }
.train-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
}
.train-stat-wide { grid-column: span 2; }
.train-stat span { font-size: 12px; color: var(--color-ink-mute); }
.train-stat strong { font-size: 14px; color: var(--color-ink); word-break: break-word; }
.train-stat small { font-size: 12px; line-height: 1.45; color: var(--color-ink-mute); }
.train-warning, .train-error { padding: 12px 14px; border-radius: var(--radius-md); font-size: 12px; line-height: 1.45; }
.train-warning { background: #fffbeb; border: 1px solid #fcd34d; color: #92400e; }
.train-error { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
.train-list { display: flex; flex-direction: column; gap: 8px; max-height: 260px; overflow: auto; }
.train-list-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 12px; text-align: left; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas); cursor: pointer; transition: border-color 160ms ease, background-color 160ms ease; }
.train-list-row:hover { border-color: var(--color-hairline-strong); background: var(--color-canvas-soft); }
.train-list-row strong { display: block; font-size: 13px; color: var(--color-ink); }
.train-list-row span { display: block; font-size: 12px; line-height: 1.45; color: var(--color-ink-mute); }
.train-empty { font-size: 12px; color: var(--color-ink-mute); padding: 4px 0; }
.train-version-card { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 6px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas); transition: border-color 160ms ease, background-color 160ms ease; }
.train-version-card:hover, .train-version-card.is-selected { border-color: var(--color-hairline-strong); background: var(--color-canvas-soft); }
.train-version-card.is-selected { border-color: color-mix(in srgb, var(--color-primary) 48%, var(--color-hairline)); }
.train-version-select { min-width: 0; padding: 6px; border: 0; background: transparent; text-align: left; cursor: pointer; }
.train-version-select strong { display: block; color: var(--color-ink); font-size: 13px; line-height: 1.35; word-break: break-word; }
.train-version-select span { display: block; color: var(--color-ink-mute); font-size: 12px; line-height: 1.45; }
.train-version-delete { align-self: stretch; }
.train-link { background: transparent; border: 0; padding: 0; font-size: 12px; color: var(--color-primary-deep); cursor: pointer; }
.train-link-inline { display: inline-flex; align-items: center; gap: 6px; font-weight: 500; }
.train-row-shell { display: flex; flex-direction: column; gap: 6px; }
.train-list-row-main { width: 100%; }
.train-list-actions { display: flex; gap: 6px; justify-content: flex-end; }
.train-model-card { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 6px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas); transition: border-color 160ms ease, background-color 160ms ease; }
.train-model-card:hover { border-color: var(--color-hairline-strong); background: var(--color-canvas-soft); }
.train-model-open { min-width: 0; padding: 6px; border: 0; background: transparent; }
.train-model-meta { display: inline-flex; align-items: center; gap: 6px; }
.train-mini-action { min-height: 24px; padding: 0 8px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); color: var(--color-ink-mute); font-size: 10px; cursor: pointer; transition: border-color 160ms ease, color 160ms ease, background-color 160ms ease; }
.train-mini-action:hover { border-color: var(--color-hairline-strong); color: var(--color-ink); background: var(--color-canvas-soft); }
.train-mini-action.is-danger { color: #991b1b; }
.train-metric-table { display: flex; flex-direction: column; gap: 0; }
.train-metric-scroll { max-height: 430px; overflow: auto; border-top: 1px solid var(--color-hairline); }
.train-metric-head, .train-metric-row { display: grid; grid-template-columns: 72px repeat(6, minmax(0, 1fr)); gap: 12px; }
.train-metric-head { position: sticky; top: 0; z-index: 1; padding: 10px 0; border-bottom: 1px solid var(--color-hairline); font-size: 12px; color: var(--color-ink-mute); background: var(--color-canvas); font-weight: 500; }
.train-metric-row { padding: 12px 0; border-bottom: 1px solid var(--color-hairline-cool); font-size: 13px; color: var(--color-ink); }
.train-trend-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.train-trend-card { min-width: 0; display: flex; flex-direction: column; gap: 10px; min-height: 112px; padding: 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas-soft); }
.train-trend-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.train-trend-head span { color: var(--color-ink-mute); font-size: 12px; }
.train-trend-head strong { color: var(--color-ink); font-size: 16px; font-weight: 500; }
.train-sparkline { width: 100%; height: 54px; overflow: visible; }
.train-sparkline path { fill: none; stroke: var(--color-hairline-strong); stroke-width: 1; stroke-dasharray: 2 4; }
.train-sparkline polyline { fill: none; stroke: #059669; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.train-trend-card.is-balance .train-sparkline polyline { stroke: #2563eb; }
.train-trend-card.is-loss .train-sparkline polyline { stroke: #d97706; }
.train-trend-empty { min-height: 54px; display: flex; align-items: center; color: var(--color-ink-mute); font-size: 12px; }
.train-path-row { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.train-path-row span { min-width: 0; overflow-wrap: anywhere; word-break: break-word; line-height: 1.45; }
.train-policy-grid { display: grid; gap: 10px; }
.train-policy-grid div { min-width: 0; display: flex; flex-direction: column; gap: 3px; padding: 10px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas-soft); }
.train-policy-grid span { color: var(--color-ink-mute); font-size: 11px; text-transform: uppercase; }
.train-policy-grid strong { color: var(--color-ink); font-size: 13px; font-weight: 500; word-break: break-word; }
.train-policy-grid small { color: var(--color-ink-mute); font-size: 12px; line-height: 1.4; word-break: break-word; }
.train-log-block { display: flex; flex-direction: column; gap: 8px; max-height: 540px; overflow: auto; }
.train-log-row { display: flex; flex-direction: column; gap: 4px; padding: 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas-soft); }
.train-log-row strong { font-size: 12px; color: var(--color-ink); }
.train-log-row span { font-size: 12px; line-height: 1.45; color: var(--color-ink-mute); word-break: break-word; }
.dataset-status-pill { display: inline-flex; align-items: center; justify-content: center; min-height: 20px; padding: 0 7px; border-radius: 999px; font-size: 10px; line-height: 1; text-transform: capitalize; white-space: nowrap; background: var(--color-canvas-soft); color: var(--color-ink-mute); border: 1px solid var(--color-hairline); }
.dataset-status-pill.is-running, .dataset-status-pill.is-preparing { color: var(--color-primary-deep); background: color-mix(in srgb, var(--color-primary) 10%, white); border-color: color-mix(in srgb, var(--color-primary) 35%, white); }
.dataset-status-pill.is-completed { color: #14532d; background: #dcfce7; border-color: #86efac; }
.dataset-status-pill.is-failed, .dataset-status-pill.is-cancelled { color: #991b1b; background: #fee2e2; border-color: #fecaca; }

@media (max-width: 1024px) {
  .train-stepper { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .train-create-panel { flex-direction: column; align-items: flex-start; }
  .train-trend-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .train-field-span { grid-column: span 1; }
  .train-stat-wide { grid-column: span 1; }
  .train-version-flow { grid-template-columns: 1fr; }
  .train-version-lane { border-left: 0; border-top: 1px solid var(--color-hairline); }
  .train-version-lane:first-child { border-top: 0; }
  .train-version-preview { flex-direction: column; }
  .train-preview-title { width: 100%; padding-right: 0; padding-bottom: 12px; border-right: 0; border-bottom: 1px solid var(--color-hairline); }
  .train-preview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .train-metric-head, .train-metric-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .train-stepper, .train-trend-grid { grid-template-columns: 1fr; }
  .train-version-delete { align-self: center; }
  .train-model-card { grid-template-columns: 1fr; align-items: stretch; }
  .train-model-meta { justify-content: space-between; }
}
</style>
