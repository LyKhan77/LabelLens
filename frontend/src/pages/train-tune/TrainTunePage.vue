<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import { useBackendStatus } from '../../shared/composables/useBackendStatus'
import { useTheme } from '../../shared/composables/useTheme'
import { useTrainingStore } from '../../shared/stores/training'
import type { DatasetVersion, DatasetVersionTrainingConfig, ModelVersion, TrainingJob, TrainingMetricPoint } from '../../shared/api/training'
import { getTrainingGpus } from '../../shared/api/system'
import type { GpuInfo } from '../../shared/types'

const props = defineProps<{ path: string }>()

const emit = defineEmits<{ 'open-settings': [] }>()

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()
const trainingStore = useTrainingStore()
const { yoloeStatus, samStatus } = useBackendStatus()
const { theme, toggle } = useTheme()

const form = reactive(reactiveState())
const detectedGpus = ref<GpuInfo[]>([])
const versionDeleteError = ref<string | null>(null)
const deleteError = ref<string | null>(null)
const deletingTarget = ref(false)
type DeleteTarget =
  | { kind: 'dataset-version'; id: string; name: string }
  | { kind: 'failed-job'; id: string; name: string }
  | { kind: 'model-version'; id: string; name: string; jobName: string }
const deleteTarget = ref<DeleteTarget | null>(null)
const builderStep = ref(1)
const showAugmentMenu = ref(false)
type AugmentKey = 'fliplr' | 'flipud' | 'degrees' | 'translate' | 'scale' | 'shear' | 'hsv_h' | 'hsv_s' | 'hsv_v' | 'exposure' | 'blur' | 'noise' | 'mosaic' | 'mixup' | 'copy_paste' | 'erasing'
type SplitKey = 'train' | 'val' | 'test'
const activeAugmentKey = ref<AugmentKey | null>(null)
const augmentDraft = ref(0)
const augmentPreviewLoading = ref(false)
let suppressCheckpointSync = false

const previewOffsets = [-1, 0, 1] as const
const augmentationSteps = [
  { key: 'degrees', label: 'Rotation', unit: 'deg', min: 0, max: 45, step: 1, defaultValue: 15, help: 'Adds camera roll variation while preserving object geometry.', materialized: true },
  { key: 'fliplr', label: 'Horizontal Flip', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.5, help: 'Mirrors train images left to right when object direction is not fixed.', materialized: true },
  { key: 'flipud', label: 'Vertical Flip', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.2, help: 'Use only when upside-down objects are valid in production.', materialized: true },
  { key: 'noise', label: 'Noise', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.2, help: 'Adds sensor noise and compression-like variation.', materialized: true },
  { key: 'blur', label: 'Blur', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.2, help: 'Helps with motion blur and slight focus errors.', materialized: true },
  { key: 'exposure', label: 'Exposure', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.2, help: 'Varies brightness and contrast for lighting changes.', materialized: true },
  { key: 'hsv_h', label: 'Hue', unit: '', min: 0, max: 0.2, step: 0.005, defaultValue: 0.02, help: 'Small hue shifts for color variation.', materialized: true },
  { key: 'hsv_s', label: 'Saturation', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.3, help: 'Changes color intensity while retaining labels.', materialized: true },
  { key: 'hsv_v', label: 'Brightness', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.25, help: 'Adjusts value channel for darker/brighter scenes.', materialized: true },
  { key: 'translate', label: 'Translate', unit: '%', min: 0, max: 0.5, step: 0.01, defaultValue: 0.08, help: 'Moves objects in frame to reduce center bias.', materialized: true },
  { key: 'scale', label: 'Scale / Zoom', unit: '%', min: 0, max: 0.9, step: 0.05, defaultValue: 0.25, help: 'Zooms in or out so object size varies.', materialized: true },
  { key: 'shear', label: 'Shear', unit: 'deg', min: 0, max: 45, step: 1, defaultValue: 8, help: 'Adds mild perspective-like skew.', materialized: true },
  { key: 'mosaic', label: 'Mosaic', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.5, help: 'Training-only YOLO augmentation combining multiple images.', materialized: false },
  { key: 'mixup', label: 'MixUp', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.1, help: 'Training-only image blending for regularization.', materialized: false },
  { key: 'copy_paste', label: 'Copy Paste', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.1, help: 'Training-only segment augmentation for object composition.', materialized: false },
  { key: 'erasing', label: 'Erasing', unit: '%', min: 0, max: 1, step: 0.05, defaultValue: 0.1, help: 'Training-only random erasing/occlusion regularization.', materialized: false },
] as const satisfies ReadonlyArray<{ key: AugmentKey; label: string; unit: string; min: number; max: number; step: number; defaultValue: number; help: string; materialized: boolean }>

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
      resizeMode: 'keep' as 'keep' | 'letterbox' | 'stretch',
      augmentationMode: 'basic' as 'basic' | 'advanced',
      augmentMultiplier: 1,
    augFlipHorizontal: 0,
    augFlipVertical: 0,
    augRotation: 0,
    augTranslate: 0,
    augScale: 0,
    augShear: 0,
    augHsvHue: 0,
    augHsvSaturation: 0,
    augHsvValue: 0,
    augExposure: 0,
    augBlur: 0,
    augNoise: 0,
    augMosaic: 0,
    augMixup: 0,
    augCopyPaste: 0,
    augErasing: 0,
    taskType: 'detect' as 'detect' | 'segment' | 'pose' | 'classify_single',
    family: 'yolo11' as 'yolo11' | 'yolo26',
    size: 'n' as 'n' | 's' | 'm' | 'l',
    baseCheckpoint: 'yolo11n.pt',
    epochs: 50,
    patience: 30,
    imgsz: 640,
    batch: -1,
    workers: 2,
    trainingMode: 'standard' as 'standard' | 'high_speed',
    trainingDevice: '1' as string,
    trainingDevices: [1] as number[],
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
const splitConfig = computed(() => ({ train: form.splitTrain, val: form.splitVal, test: form.splitTest }))
const splitTrainBoundary = computed({
  get: () => form.splitTrain,
  set: (value: number) => setSplitTrainBoundary(value),
})
const splitTestBoundary = computed({
  get: () => form.splitTrain + form.splitVal,
  set: (value: number) => setSplitTestBoundary(value),
})
const builderReady = computed(() => trainingStore.selectedVersion !== null)
const latestMetric = computed(() => trainingStore.selectedJob?.metrics_latest ?? trainingStore.jobMetrics.at(-1) ?? null)
const resultSourceVersion = computed(() => trainingStore.versions.find((version) => version.id === trainingStore.selectedModel?.dataset_version_id) ?? null)
const resultJob = computed(() => trainingStore.selectedJob)
const builderSummary = computed(() => trainingStore.selectedVersion?.summary ?? null)
const liveSourceVersion = computed(() => trainingStore.versions.find((version) => version.id === trainingStore.selectedJob?.dataset_version_id) ?? null)
const sourceReady = computed(() => form.sourceType === 'live' ? Boolean(form.selectedDataset) : Boolean(form.zipFile))
const architectureReady = computed(() => Boolean(form.baseCheckpoint) && form.epochs > 0 && form.patience >= 0 && form.imgsz > 0 && (form.batch === -1 || form.batch > 0) && form.workers >= 0)
const splitReady = computed(() => totalSplit.value === 100)
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
const resizeStrategyLabel = computed(() => {
  if (form.resizeMode === 'letterbox') return `Letterbox to ${form.imgsz}x${form.imgsz}`
  if (form.resizeMode === 'stretch') return `Stretch to ${form.imgsz}x${form.imgsz}`
  return 'Keep original image size'
})
const preprocessingSummary = computed(() => `${resizeStrategyLabel.value}; ${form.autoOrient ? 'auto orient on' : 'auto orient off'}.`)
const selectedDatasetProject = computed(() => datasetStore.projects.find((project) => project.name === form.selectedDataset) ?? null)
const estimatedSourceImages = computed(() => selectedDatasetProject.value?.stats.accepted || selectedDatasetProject.value?.stats.total_images || 0)
const estimatedTrainOriginal = computed(() => Math.round(estimatedSourceImages.value * (form.splitTrain / 100)))
const estimatedValImages = computed(() => Math.round(estimatedSourceImages.value * (form.splitVal / 100)))
const estimatedTestImages = computed(() => Math.max(0, estimatedSourceImages.value - estimatedTrainOriginal.value - estimatedValImages.value))
const splitEstimateSummary = computed(() => {
  if (!estimatedSourceImages.value) return 'Select a live dataset to estimate images per split.'
  return `${estimatedTrainOriginal.value} train · ${estimatedValImages.value} valid · ${estimatedTestImages.value} test from ${estimatedSourceImages.value} source images`
})
const splitWarning = computed(() => {
  if (!estimatedSourceImages.value) return ''
  if (form.splitVal > 0 && estimatedValImages.value < 1) return 'Valid split may produce 0 images. Increase Valid or add more labeled images.'
  if (form.splitTest > 0 && estimatedTestImages.value < 1) return 'Test split may produce 0 images. Increase Test or add more labeled images.'
  return ''
})
const splitBarStyle = computed(() => ({
  background: `linear-gradient(90deg, #86efac 0 ${form.splitTrain}%, #fde68a ${form.splitTrain}% ${form.splitTrain + form.splitVal}%, #c4b5fd ${form.splitTrain + form.splitVal}% 100%)`,
}))
const advancedAugmentationEnabled = computed(() => form.augmentationMode === 'advanced')
const activeAugmentationSteps = computed(() => advancedAugmentationEnabled.value ? augmentationSteps.filter((step) => augmentValue(step.key) > 0) : [])
const activeMaterializedSteps = computed(() => activeAugmentationSteps.value.filter((step) => step.materialized))
const estimatedGeneratedImages = computed(() => activeMaterializedSteps.value.length ? Math.max(0, estimatedTrainOriginal.value * (form.augmentMultiplier - 1)) : 0)
const estimatedFinalImages = computed(() => estimatedSourceImages.value + estimatedGeneratedImages.value)
const augmentationSummary = computed(() => {
  if (!advancedAugmentationEnabled.value) return 'Basic online augmentation; no generated snapshot images.'
  return activeAugmentationSteps.value.length
    ? `${activeAugmentationSteps.value.length} optional steps; ${form.augmentMultiplier}x train-only cap; ${estimatedGeneratedImages.value} generated train images estimated.`
    : 'Advanced mode with no custom steps. Training uses original dataset images unless steps are added.'
})
const availableAugmentationSteps = computed(() => augmentationSteps.filter((step) => !activeAugmentationSteps.value.some((active) => active.key === step.key)))
const activeAugmentStep = computed(() => augmentationSteps.find((step) => step.key === activeAugmentKey.value) ?? null)
const modalPreviewImage = computed(() => trainingStore.policyPreview?.samples?.[0]?.original.image ?? '')
const modalPreviewFilename = computed(() => trainingStore.policyPreview?.samples?.[0]?.filename ?? '')
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

function taskLabel(taskType: 'detect' | 'segment' | 'pose' | 'classify_single' | string | undefined) {
  if (taskType === 'segment') return 'Segmentation'
  if (taskType === 'pose') return 'Pose'
  if (taskType === 'classify_single') return 'Classification'
  return 'Detection'
}

function defaultCheckpoint(family: 'yolo11' | 'yolo26', size: 'n' | 's' | 'm' | 'l', taskType: 'detect' | 'segment' | 'pose' | 'classify_single') {
  const suffix = taskType === 'segment' ? '-seg' : taskType === 'pose' ? '-pose' : taskType === 'classify_single' ? '-cls' : ''
  return family === 'yolo11' ? `yolo11${size}${suffix}.pt` : `yolo26${size}${suffix}.pt`
}

function checkpointPlaceholder() {
  if (form.taskType === 'segment') return 'yolo26n-seg.pt'
  if (form.taskType === 'pose') return 'yolo26n-pose.pt'
  if (form.taskType === 'classify_single') return 'yolo26n-cls.pt'
  return 'yolo26n.pt'
}

function taskSnapshotNote() {
  if (form.taskType === 'segment') return 'Segmentation snapshots require every accepted object to have a mask from Dataset Workspace/SAM2.1. Segment models output both bbox and mask.'
  if (form.taskType === 'pose') return 'Pose snapshots require accepted pose instances with complete keypoints. Pose models output bbox plus keypoints.'
  if (form.taskType === 'classify_single') return 'Classification snapshots require one accepted image-level label per image and train from class-folder splits.'
  return 'Detection snapshots train bbox-only labels. Segmentation masks are ignored unless the Segmentation task is selected.'
}

function syncCheckpoint() {
  if (suppressCheckpointSync) return
  form.baseCheckpoint = defaultCheckpoint(form.family, form.size, form.taskType)
}

function currentTrainingConfig(): DatasetVersionTrainingConfig {
  return {
    family: form.family,
    size: form.size,
    base_checkpoint: form.baseCheckpoint,
    epochs: form.epochs,
    patience: form.patience,
    imgsz: form.imgsz,
    batch: form.batch,
    workers: form.workers,
    training_mode: form.trainingMode,
  }
}

function applyTrainingConfig(config: DatasetVersion['training_config'] | null | undefined) {
  if (!config) return
  try {
    suppressCheckpointSync = true
    form.family = config.family
    form.size = config.size
    form.baseCheckpoint = config.base_checkpoint
    form.epochs = config.epochs
    form.patience = config.patience
    form.imgsz = config.imgsz
    form.batch = config.batch
    form.workers = config.workers
    form.trainingMode = config.training_mode
  } finally {
    suppressCheckpointSync = false
  }
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
  const mode = configText(version?.preprocessing_config.resize_mode, 'keep')
  const target = configText(version?.preprocessing_config.target_size, 'train')
  if (mode === 'letterbox' || mode === 'fit') return `Letterbox ${target}`
  if (mode === 'stretch') return `Stretch ${target}`
  return 'Keep original'
}

function versionOrient(version: DatasetVersion | null | undefined) {
  return configText(version?.preprocessing_config.auto_orient, 'true') === 'false' ? 'Auto orient disabled' : 'Auto orient enabled'
}

function versionAugment(version: DatasetVersion | null | undefined) {
  const config = version?.augmentation_config ?? {}
  const multiplier = Number(config.multiplier ?? 1)
  const mode = configText(config.mode, configText(config.profile, 'baseline'))
  return multiplier > 1 ? `${mode} · ${multiplier}x train` : mode
}

function batchLabel(batch: number | undefined) {
  return batch === -1 ? 'Auto' : String(batch ?? 'N/A')
}

function clampSplitPercent(value: number, min = 0, max = 100) {
  if (!Number.isFinite(value)) return min
  return Math.min(max, Math.max(min, Math.round(value)))
}

function applySplitBoundaries(trainEnd: number, valEnd: number) {
  const train = clampSplitPercent(trainEnd)
  const valBoundary = clampSplitPercent(valEnd, train, 100)
  form.splitTrain = train
  form.splitVal = valBoundary - train
  form.splitTest = 100 - valBoundary
}

function setSplitTrainBoundary(value: number) {
  applySplitBoundaries(value, form.splitTrain + form.splitVal)
}

function setSplitTestBoundary(value: number) {
  applySplitBoundaries(form.splitTrain, value)
}

function updateSplitPercent(key: SplitKey, event: Event) {
  const value = clampSplitPercent(Number((event.target as HTMLInputElement).value))
  if (key === 'train') {
    applySplitBoundaries(value, Math.min(100, value + form.splitVal))
  } else if (key === 'val') {
    applySplitBoundaries(form.splitTrain, form.splitTrain + value)
  } else {
    applySplitBoundaries(form.splitTrain, 100 - value)
  }
}

function applySplitPreset(train: number, val: number, test: number) {
  const nextTrain = clampSplitPercent(train)
  const nextVal = clampSplitPercent(val, 0, 100 - nextTrain)
  form.splitTrain = nextTrain
  form.splitVal = nextVal
  form.splitTest = 100 - nextTrain - nextVal
  if (test !== form.splitTest) {
    form.splitTest = clampSplitPercent(test, 0, 100)
    form.splitVal = Math.max(0, 100 - form.splitTrain - form.splitTest)
  }
}

function policyPreprocessingConfig() {
  return { auto_orient: form.autoOrient, resize_mode: form.resizeMode, target_size: form.imgsz }
}

function augmentValue(key: AugmentKey) {
  const map: Record<AugmentKey, number> = {
    fliplr: form.augFlipHorizontal,
    flipud: form.augFlipVertical,
    degrees: form.augRotation,
    translate: form.augTranslate,
    scale: form.augScale,
    shear: form.augShear,
    hsv_h: form.augHsvHue,
    hsv_s: form.augHsvSaturation,
    hsv_v: form.augHsvValue,
    exposure: form.augExposure,
    blur: form.augBlur,
    noise: form.augNoise,
    mosaic: form.augMosaic,
    mixup: form.augMixup,
    copy_paste: form.augCopyPaste,
    erasing: form.augErasing,
  }
  return Number(map[key]) || 0
}

function setAugmentValue(key: AugmentKey, value: number) {
  const next = Number(value) || 0
  if (key === 'fliplr') form.augFlipHorizontal = next
  else if (key === 'flipud') form.augFlipVertical = next
  else if (key === 'degrees') form.augRotation = next
  else if (key === 'translate') form.augTranslate = next
  else if (key === 'scale') form.augScale = next
  else if (key === 'shear') form.augShear = next
  else if (key === 'hsv_h') form.augHsvHue = next
  else if (key === 'hsv_s') form.augHsvSaturation = next
  else if (key === 'hsv_v') form.augHsvValue = next
  else if (key === 'exposure') form.augExposure = next
  else if (key === 'blur') form.augBlur = next
  else if (key === 'noise') form.augNoise = next
  else if (key === 'mosaic') form.augMosaic = next
  else if (key === 'mixup') form.augMixup = next
  else if (key === 'copy_paste') form.augCopyPaste = next
  else if (key === 'erasing') form.augErasing = next
}

function formatAugmentValue(key: AugmentKey, value = augmentValue(key)) {
  const step = augmentationSteps.find((item) => item.key === key)
  if (!step) return String(value)
  if (step.unit === '%') return `${Math.round(value * 100)}%`
  if (step.unit === 'deg') return `${value}deg`
  return value.toString()
}

async function openAugmentModal(key: AugmentKey) {
  const step = augmentationSteps.find((item) => item.key === key)
  if (!step) return
  activeAugmentKey.value = key
  augmentDraft.value = augmentValue(key) || step.defaultValue
  showAugmentMenu.value = false
  if (!modalPreviewImage.value && sourceReady.value) {
    augmentPreviewLoading.value = true
    try {
      await requestPolicyPreview(false)
    } finally {
      augmentPreviewLoading.value = false
    }
  }
}

function closeAugmentModal() {
  activeAugmentKey.value = null
}

function applyAugmentStep() {
  if (!activeAugmentKey.value) return
  setAugmentValue(activeAugmentKey.value, augmentDraft.value)
  closeAugmentModal()
}

function removeAugmentStep(key: AugmentKey) {
  setAugmentValue(key, 0)
}

function modalPreviewStyle(offset: -1 | 0 | 1) {
  const key = activeAugmentKey.value
  const value = offset === 0 ? 0 : augmentDraft.value * offset
  const transforms: string[] = []
  const filters: string[] = []
  if (key === 'degrees') transforms.push(`rotate(${value}deg)`)
  if (key === 'scale') transforms.push(`scale(${1 + value})`)
  if (key === 'shear') transforms.push(`skewX(${value}deg)`)
  if (key === 'translate') transforms.push(`translateX(${value * 42}px)`)
  if (key === 'fliplr' && offset !== 0) transforms.push('scaleX(-1)')
  if (key === 'flipud' && offset !== 0) transforms.push('scaleY(-1)')
  if (key === 'blur' && offset !== 0) filters.push(`blur(${Math.max(1, augmentDraft.value * 6)}px)`)
  if ((key === 'hsv_v' || key === 'exposure') && offset !== 0) filters.push(`brightness(${1 + value})`)
  if (key === 'hsv_s' && offset !== 0) filters.push(`saturate(${1 + value})`)
  if (key === 'hsv_h' && offset !== 0) filters.push(`hue-rotate(${value * 180}deg)`)
  if (key === 'noise' && offset !== 0) filters.push(`contrast(${1 + augmentDraft.value})`)
  return { transform: transforms.join(' ') || 'none', filter: filters.join(' ') || 'none' }
}

function modalPreviewLabel(offset: -1 | 0 | 1) {
  if (offset === 0) return 'Original'
  return offset < 0 ? `-${formatAugmentValue(activeAugmentKey.value || 'degrees', augmentDraft.value)}` : formatAugmentValue(activeAugmentKey.value || 'degrees', augmentDraft.value)
}

function activeOfflineConfig() {
  const offline: Record<string, number> = {}
  for (const step of augmentationSteps) {
    if (!step.materialized) continue
    const value = augmentValue(step.key)
    if (value > 0) offline[step.key] = value
  }
  return offline
}

function activeOnlineConfig() {
  const online: Record<string, number> = {}
  for (const step of augmentationSteps) {
    const value = augmentValue(step.key)
    if (value > 0 && step.key !== 'exposure' && step.key !== 'blur' && step.key !== 'noise') online[step.key] = value
  }
  return online
}

function policyAugmentationConfig() {
  if (form.augmentationMode === 'basic') {
    return {
      mode: 'basic',
      profile: 'basic',
      multiplier: 1,
      apply_to: 'train',
      offline: {},
      online: {
        fliplr: 0.5,
        hsv_s: 0.3,
        hsv_v: 0.25,
        translate: 0.05,
        scale: 0.25,
        mosaic: 0.5,
        close_mosaic: 10,
      },
    }
  }
  return {
    mode: 'advanced',
    profile: activeAugmentationSteps.value.length ? 'custom' : 'none',
    multiplier: activeMaterializedSteps.value.length ? Math.min(Math.max(Number(form.augmentMultiplier) || 1, 1), 5) : 1,
    apply_to: 'train',
    offline: activeOfflineConfig(),
    online: activeOnlineConfig(),
  }
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

async function loadTrainingGpus() {
  try {
    const res = await getTrainingGpus()
    detectedGpus.value = res.gpus
    form.trainingMode = res.training_config.training_mode
  } catch {
    detectedGpus.value = []
  }
}

function onTrainingModeChange() {
  if (form.trainingMode === 'standard') {
    form.trainingDevices = form.trainingDevices.slice(0, 1)
    form.trainingDevice = String(form.trainingDevices[0] ?? 0)
  }
}

function toggleTrainingGpu(index: number) {
  const i = form.trainingDevices.indexOf(index)
  if (i >= 0) form.trainingDevices.splice(i, 1)
  else form.trainingDevices.push(index)
}

function isGpuSelected(index: number): boolean {
  if (form.trainingMode === 'standard') return form.trainingDevice === String(index)
  return form.trainingDevices.includes(index)
}

function selectGpu(index: number) {
  if (form.trainingMode === 'standard') {
    form.trainingDevice = String(index)
    form.trainingDevices = [index]
  } else {
    toggleTrainingGpu(index)
  }
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

onMounted(() => { hydrate(); loadTrainingGpus() })

watch(() => props.path, async () => {
  await loadRouteState()
})

watch(() => [form.family, form.size, form.taskType], () => syncCheckpoint(), { immediate: true })

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
        splitConfig: splitConfig.value,
        preprocessingConfig: policyPreprocessingConfig(),
        augmentationConfig: policyAugmentationConfig(),
        trainingConfig: currentTrainingConfig(),
        resizeMode: form.resizeMode,
        taskType: form.taskType,
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
        splitConfig: splitConfig.value,
        preprocessingConfig: policyPreprocessingConfig(),
        augmentationConfig: policyAugmentationConfig(),
        trainingConfig: currentTrainingConfig(),
        taskType: form.taskType,
      })
    }
    if (!form.jobName) {
      form.jobName = `${version.version_name}-${form.family}-${form.size}`
    }
    builderStep.value = builderSteps.length
    await refreshEstimate()
    await refreshRecommendation()
  } catch (err) {
    const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
    if (detail && typeof detail === 'object' && (detail as { code?: string }).code === 'missing_segmentation_masks') {
      const missing = ((detail as { missing?: Array<{ image?: string; label?: string }> }).missing ?? [])
        .slice(0, 6)
        .map((item) => `${item.image || 'image'} / ${item.label || 'object'}`)
        .join(', ')
      form.localError = `${(detail as { message?: string }).message || 'Segmentation masks are incomplete'}. Fix in Dataset Workspace: ${missing}`
      return
    }
    form.localError = err instanceof Error ? err.message : 'Gagal membuat dataset version'
  }
}

async function requestPolicyPreview(showValidation = true) {
  if (showValidation) form.localError = null
  if (form.sourceType === 'live' && !form.selectedDataset) {
    if (showValidation) form.localError = 'Pilih dataset project dulu untuk preview policy.'
    return null
  }
  if (form.sourceType === 'zip' && !form.zipFile) {
    if (showValidation) form.localError = 'Pilih export zip dulu untuk preview policy.'
    return null
  }
  return trainingStore.previewPolicy({
    sourceType: form.sourceType,
    datasetName: form.sourceType === 'live' ? form.selectedDataset : undefined,
    file: form.sourceType === 'zip' ? form.zipFile : null,
    splitConfig: splitConfig.value,
    preprocessingConfig: policyPreprocessingConfig(),
    augmentationConfig: policyAugmentationConfig(),
    taskType: form.taskType,
  })
}

async function previewPolicy() {
  try {
    await requestPolicyPreview(true)
  } catch (err) {
    form.localError = err instanceof Error ? err.message : 'Gagal membuat preview policy'
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
      patience: form.patience,
      imgsz: form.imgsz,
      batch: form.batch,
      workers: form.workers,
      training_mode: form.trainingMode,
      task_type: form.taskType,
    })
  } catch (err) {
    form.localError = err instanceof Error ? err.message : 'Gagal membuat estimasi training'
  }
}

async function refreshRecommendation() {
  const version = trainingStore.selectedVersion
  if (!version) return null
  try {
    return await trainingStore.recommend({
      dataset_version_id: version.id,
      family: form.family,
      size: form.size,
      imgsz: form.imgsz,
      task_type: version.task_type,
    })
  } catch (err) {
    form.localError = err instanceof Error ? err.message : 'Gagal membuat rekomendasi training'
    return null
  }
}

async function applyRecommendedSettings() {
  const recommendation = trainingStore.currentRecommendation ?? await refreshRecommendation()
  if (!recommendation) return
  form.epochs = recommendation.epochs
  form.patience = recommendation.patience
  form.batch = recommendation.batch
  form.imgsz = recommendation.imgsz
  form.augmentationMode = recommendation.augmentation_mode
  await refreshEstimate()
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
      patience: form.patience,
      imgsz: form.imgsz,
      batch: form.batch,
      workers: form.workers,
      training_mode: form.trainingMode,
      task_type: form.taskType,
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
  if (version.task_type) {
    form.taskType = version.task_type as typeof form.taskType
  }
  if (version.training_config) {
    applyTrainingConfig(version.training_config)
  } else {
    syncCheckpoint()
  }
  versionDeleteError.value = null
  await refreshRecommendation()
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

async function resumeJob(jobId: string) {
  const job = await trainingStore.resumeJob(jobId)
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

        <button
          class="p-1.5 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer"
          title="GPU Settings"
          @click="$emit('open-settings')"
        >
          <svg class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
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
                    <h2 class="text-[18px] font-medium text-ink">Policy</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Resize strategy is deterministic; augmentation is optional and added as explicit steps before the immutable Dataset Version is created.</p>
                  </div>
                  <div class="train-policy-sections">
                    <div class="train-policy-section">
                      <div class="train-version-title">
                        <strong>1. Dataset Split</strong>
                        <span>{{ splitEstimateSummary }}</span>
                      </div>
                      <div class="train-split-composer">
                        <div class="train-split-track" :style="splitBarStyle" aria-hidden="true">
                          <span class="train-split-name is-train" :style="{ width: `${form.splitTrain}%` }">Train {{ form.splitTrain }}%</span>
                          <span class="train-split-name is-val" :style="{ width: `${form.splitVal}%` }">Valid {{ form.splitVal }}%</span>
                          <span class="train-split-name is-test" :style="{ width: `${form.splitTest}%` }">Test {{ form.splitTest }}%</span>
                          <span class="train-split-handle" :style="{ left: `${form.splitTrain}%` }" />
                          <span class="train-split-handle" :style="{ left: `${form.splitTrain + form.splitVal}%` }" />
                        </div>
                        <div class="train-split-range-layer">
                          <input v-model.number="splitTrainBoundary" class="train-split-range is-train" type="range" min="0" :max="splitTestBoundary" step="1" aria-label="Train split percent" />
                          <input v-model.number="splitTestBoundary" class="train-split-range is-test" type="range" :min="splitTrainBoundary" max="100" step="1" aria-label="Valid and test split boundary" />
                        </div>
                      </div>
                      <div class="train-split-inputs">
                        <label><span>Train</span><input type="number" min="0" max="100" :value="form.splitTrain" @input="updateSplitPercent('train', $event)" /><strong>%</strong></label>
                        <label><span>Valid</span><input type="number" min="0" max="100" :value="form.splitVal" @input="updateSplitPercent('val', $event)" /><strong>%</strong></label>
                        <label><span>Test</span><input type="number" min="0" max="100" :value="form.splitTest" @input="updateSplitPercent('test', $event)" /><strong>%</strong></label>
                      </div>
                      <div class="train-split-presets" aria-label="Dataset split presets">
                        <button type="button" @click="applySplitPreset(70, 20, 10)">70/20/10</button>
                        <button type="button" @click="applySplitPreset(80, 10, 10)">80/10/10</button>
                        <button type="button" @click="applySplitPreset(90, 10, 0)">90/10/0</button>
                      </div>
                      <p class="train-version-note" :class="splitWarning ? 'is-warning' : ''">{{ splitWarning || 'Roboflow-style split policy is locked into the immutable Dataset Version snapshot.' }}</p>
                    </div>

                    <div class="train-policy-section">
                      <div class="train-version-title">
                        <strong>2. Preprocessing</strong>
                        <span>{{ preprocessingSummary }}</span>
                      </div>
                      <div class="train-version-fields">
                        <label class="train-field"><span>Resize Strategy</span><select v-model="form.resizeMode"><option value="keep">Keep original size</option><option value="letterbox">Letterbox to image size</option><option value="stretch">Stretch to image size</option></select></label>
                        <label class="train-field"><span>Target Size</span><input :value="`${form.imgsz} x ${form.imgsz}`" disabled /></label>
                        <label class="train-field"><span>Auto Orient</span><select v-model="form.autoOrient"><option :value="true">Enabled</option><option :value="false">Disabled</option></select></label>
                      </div>
                      <p class="train-version-note">Best practice: keep original or Letterbox. Stretch is available for Roboflow-style exports but can distort object shape.</p>
                    </div>

                      <div class="train-policy-section">
                        <div class="train-version-title">
                          <strong>3. Augmentation</strong>
                          <span>{{ augmentationSummary }}</span>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-sm)">
                          <button type="button" class="train-choice" :class="form.augmentationMode === 'basic' ? 'is-active' : ''" @click="form.augmentationMode = 'basic'">
                            <strong>Basic</strong>
                            <span>Safe online YOLO augmentation only; no extra snapshot files.</span>
                          </button>
                          <button type="button" class="train-choice" :class="form.augmentationMode === 'advanced' ? 'is-active' : ''" @click="form.augmentationMode = 'advanced'">
                            <strong>Advanced</strong>
                            <span>Custom steps, backend preview, and optional train-only generated images.</span>
                          </button>
                        </div>
                        <div v-if="!advancedAugmentationEnabled" class="train-augment-empty">
                          <strong>Basic online preset</strong>
                          <span>Horizontal flip, color jitter, translate, scale, mosaic, and close mosaic are applied by Ultralytics during training.</span>
                        </div>
                        <template v-else>
                          <div v-if="!activeAugmentationSteps.length" class="train-augment-empty">
                            <strong>No augmentation steps</strong>
                            <span>Add steps only when your dataset needs extra visual variation.</span>
                          </div>
                          <div v-else class="train-augment-step-list">
                            <div v-for="step in activeAugmentationSteps" :key="step.key" class="train-augment-step-row">
                              <button class="train-augment-step-main" @click="openAugmentModal(step.key)">
                                <strong>{{ step.label }}</strong>
                                <span>{{ formatAugmentValue(step.key) }} · {{ step.materialized ? 'materialized preview' : 'training-only' }}</span>
                              </button>
                              <button class="train-mini-action" @click="openAugmentModal(step.key)">Edit</button>
                              <button class="train-mini-action is-danger" @click="removeAugmentStep(step.key)">Delete</button>
                            </div>
                          </div>
                          <div class="train-add-augment">
                            <button class="dataset-secondary-button" :aria-expanded="showAugmentMenu" @click="showAugmentMenu = !showAugmentMenu">Add Augmentation Step</button>
                            <div v-if="showAugmentMenu" class="train-augment-menu">
                              <button v-for="step in availableAugmentationSteps" :key="step.key" @click="openAugmentModal(step.key)">
                                <strong>{{ step.label }}</strong>
                                <span>{{ step.materialized ? 'Preview + snapshot' : 'Training-only' }} · Recommended {{ formatAugmentValue(step.key, step.defaultValue) }}</span>
                              </button>
                              <span v-if="!availableAugmentationSteps.length" class="train-empty">All augmentation steps are already added.</span>
                            </div>
                          </div>
                        </template>
                      </div>

                      <div v-if="advancedAugmentationEnabled" class="train-policy-section">
                        <div class="train-version-title">
                          <strong>4. Generate Size</strong>
                        <span>Maximum Version Size multiplies only train images and only when materialized augmentation steps exist.</span>
                      </div>
                      <div class="train-version-fields">
                        <label class="train-field"><span>Maximum Version Size</span><select v-model.number="form.augmentMultiplier" :disabled="!activeMaterializedSteps.length"><option :value="1">1x original</option><option :value="2">2x train</option><option :value="3">3x train</option><option :value="4">4x train</option><option :value="5">5x train</option></select></label>
                        <div class="train-version-status is-valid">
                          <span>Estimated final</span>
                          <strong>{{ estimatedFinalImages }} images</strong>
                          <small>{{ estimatedTrainOriginal }} train originals + {{ estimatedGeneratedImages }} generated train images</small>
                        </div>
                      </div>
                    </div>

                      <div class="train-policy-section">
                        <div class="train-version-title">
                          <strong>{{ advancedAugmentationEnabled ? '5' : '4' }}. Preview</strong>
                          <span>Backend renders 3 samples with transformed bbox/mask overlays before snapshot creation.</span>
                      </div>
                      <div class="flex flex-wrap gap-(--spacing-sm)">
                        <button class="dataset-secondary-button" :disabled="trainingStore.policyPreviewLoading" @click="previewPolicy">{{ trainingStore.policyPreviewLoading ? 'Generating...' : 'Generate Preview' }}</button>
                      </div>
                      <div v-if="trainingStore.policyPreview?.samples.length" class="train-policy-preview-grid">
                        <div v-for="sample in trainingStore.policyPreview.samples" :key="sample.filename" class="train-policy-preview-card">
                          <strong>{{ sample.filename }}</strong>
                          <div class="train-policy-preview-stages">
                            <figure><img :src="sample.original.image" alt="Original policy preview" /><figcaption>Original</figcaption></figure>
                            <figure><img :src="sample.preprocessed.image" alt="Preprocessed policy preview" /><figcaption>Preprocessed</figcaption></figure>
                            <figure><img :src="sample.augmented.image" alt="Augmented policy preview" /><figcaption>Augmented</figcaption></figure>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section v-else-if="builderStep === 2" class="space-y-(--spacing-md)">
                  <div>
                    <h2 class="text-[18px] font-medium text-ink">Training Configuration</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Pick the YOLO task, family, checkpoint, and GPU mode used to schedule this training run.</p>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
                    <label class="train-field"><span class="train-label-with-info">Task <span class="train-param-help" tabindex="0" aria-label="Training task." data-tip="Detection trains boxes, Segmentation trains masks, Pose trains keypoints, Classification trains one image-level class.">?</span></span><select v-model="form.taskType"><option value="detect">Detection · BBox</option><option value="segment">Segmentation · BBox + Mask</option><option value="pose">Pose · BBox + Keypoints</option><option value="classify_single">Classification · Single Label</option></select></label>
                    <label class="train-field"><span class="train-label-with-info">Family <span class="train-param-help" tabindex="0" aria-label="YOLO architecture family." data-tip="Selects the YOLO family used as the base architecture.">?</span></span><select v-model="form.family"><option value="yolo11">YOLO11</option><option value="yolo26">YOLO26</option></select></label>
                    <label class="train-field"><span class="train-label-with-info">Size <span class="train-param-help" tabindex="0" aria-label="Model size tier." data-tip="Larger sizes can improve accuracy but use more VRAM and train slower.">?</span></span><select v-model="form.size"><option value="n">n</option><option value="s">s</option><option value="m">m</option><option value="l">l</option></select></label>
                    <label class="train-field train-field-span"><span class="train-label-with-info">Base Checkpoint <span class="train-param-help" tabindex="0" aria-label="Starting model weights." data-tip="Must match the selected task: plain, -seg, -pose, or -cls checkpoint.">?</span></span><input v-model="form.baseCheckpoint" :placeholder="checkpointPlaceholder()" /></label>
                    <label class="train-field"><span class="train-label-with-info">Job Name <span class="train-param-help" tabindex="0" aria-label="Human-readable run name." data-tip="Name used to identify this run and its output artifact folder.">?</span></span><input v-model="form.jobName" placeholder="bolt-detector" /></label>
                    <div class="train-field train-field-span">
                      <span class="train-label-with-info">Training Mode <span class="train-param-help" tabindex="0" aria-label="GPU scheduling mode." data-tip="Standard uses one GPU; High-Speed uses all selected GPUs and waits until inference is idle.">?</span></span>
                      <div class="grid grid-cols-2 gap-(--spacing-md)">
                        <button type="button" class="train-choice" :class="form.trainingMode === 'standard' ? 'is-active' : ''" @click="form.trainingMode = 'standard'; onTrainingModeChange()">
                          <strong>Standard</strong>
                          <span>1 GPU, starts immediately</span>
                        </button>
                        <button type="button" class="train-choice" :class="form.trainingMode === 'high_speed' ? 'is-active' : ''" @click="form.trainingMode = 'high_speed'">
                          <strong>High-Speed</strong>
                          <span>2+ GPUs, waits for idle inference</span>
                        </button>
                      </div>
                    </div>
                    <div v-if="detectedGpus.length > 0" class="train-field train-field-span">
                      <span class="train-label-with-info">Training GPU <span class="train-param-help" tabindex="0" aria-label="Training GPU device." data-tip="Select which detected GPU(s) to use for training.">?</span></span>
                      <div class="flex flex-wrap gap-(--spacing-sm)">
                        <button v-for="gpu in detectedGpus" :key="gpu.index" type="button" class="train-gpu-chip" :class="isGpuSelected(gpu.index) ? 'is-active' : ''" @click="selectGpu(gpu.index)">
                          <strong>GPU {{ gpu.index }}</strong>
                          <span>{{ gpu.name }}</span>
                          <span class="train-gpu-vram">{{ Math.round(gpu.vram_total_mb / 1024) }} GB</span>
                        </button>
                      </div>
                    </div>
                    <label class="train-field"><span class="train-label-with-info">Epochs <span class="train-param-help" tabindex="0" aria-label="Number of full training passes." data-tip="How many full passes through the training split the worker runs.">?</span></span><input v-model.number="form.epochs" type="number" min="1" /></label>
                    <label class="train-field"><span class="train-label-with-info">Patience <span class="train-param-help" tabindex="0" aria-label="Early stopping patience." data-tip="Stops training after this many epochs without validation improvement.">?</span></span><input v-model.number="form.patience" type="number" min="0" max="100" /></label>
                    <label class="train-field"><span class="train-label-with-info">Image Size <span class="train-param-help" tabindex="0" aria-label="Training image resolution." data-tip="Input resolution in pixels. Higher values keep detail but cost more VRAM.">?</span></span><input v-model.number="form.imgsz" type="number" min="320" step="32" /></label>
                    <label class="train-field"><span class="train-label-with-info">Batch <span class="train-param-help" tabindex="0" aria-label="Images per training step." data-tip="Auto lets Ultralytics choose a batch size based on available GPU memory.">?</span></span><select v-model.number="form.batch"><option :value="-1">Auto</option><option :value="4">4</option><option :value="8">8</option><option :value="16">16</option><option :value="32">32</option></select></label>
                    <label class="train-field"><span class="train-label-with-info">Workers <span class="train-param-help" tabindex="0" aria-label="Data loader worker count." data-tip="Parallel workers used to load and prepare training images.">?</span></span><input v-model.number="form.workers" type="number" min="1" /></label>
                  </div>
                  <p class="train-version-note">{{ taskSnapshotNote() }}</p>
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
                      <div><span>Task</span><strong>{{ taskLabel(form.taskType) }}</strong></div>
                      <div><span>Architecture</span><strong>{{ form.family }} {{ form.size }} / {{ form.baseCheckpoint }}</strong></div>
                      <div><span>Split</span><strong>{{ form.splitTrain }} / {{ form.splitVal }} / {{ form.splitTest }}</strong></div>
                      <div><span>Prep</span><strong>{{ resizeStrategyLabel }} / {{ form.autoOrient ? 'Orient' : 'Raw orient' }}</strong></div>
                        <div><span>Augment</span><strong>{{ form.augmentationMode === 'basic' ? 'Basic online' : `${form.augmentMultiplier}x advanced` }}</strong></div>
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
                  <p v-if="form.trainingMode === 'high_speed'" class="train-warning">High-Speed Mode uses {{ form.trainingDevices.length }} GPU(s). The job only starts when inference is idle, and new inference requests remain blocked until the run finishes.</p>
                  <div v-if="form.localError || trainingStore.error" class="space-y-(--spacing-sm)">
                    <p class="train-error">{{ form.localError || trainingStore.error }}</p>
                    <button v-if="['segment', 'pose', 'classify_single'].includes(form.taskType) && form.selectedDataset" class="dataset-secondary-button" @click="navigate('/datasets')">Open Dataset Workspace</button>
                  </div>
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
	                  <button class="dataset-secondary-button" :disabled="!builderReady" @click="refreshRecommendation">Refresh Recommendation</button>
	                  <button class="dataset-secondary-button" :disabled="!builderReady" @click="refreshEstimate">Refresh Estimate</button>
	                  <button class="dataset-primary-button" :disabled="!trainingStore.currentEstimate" @click="submitJob">Start Training Job</button>
	                </div>
	              </div>

	              <div v-if="trainingStore.currentRecommendation" class="train-version-preview mb-(--spacing-md)">
	                <div class="train-preview-title">
	                  <span>Recommended Settings</span>
	                  <strong>{{ trainingStore.currentRecommendation.epochs }} epochs · patience {{ trainingStore.currentRecommendation.patience }}</strong>
	                </div>
	                <div class="train-preview-grid">
	                  <div><span>Dataset Size</span><strong>{{ trainingStore.currentRecommendation.image_count }} images</strong></div>
	                  <div><span>Batch</span><strong>{{ batchLabel(trainingStore.currentRecommendation.batch) }}</strong></div>
	                  <div><span>Image Size</span><strong>{{ trainingStore.currentRecommendation.imgsz }} px</strong></div>
	                  <div><span>Augment</span><strong>{{ trainingStore.currentRecommendation.augmentation_mode }}</strong></div>
	                  <div class="train-stat-wide"><span>Reason</span><strong>{{ trainingStore.currentRecommendation.reason }}</strong></div>
	                </div>
	                <button class="dataset-primary-button" @click="applyRecommendedSettings">Apply Recommended Settings</button>
	              </div>

	              <div v-if="builderSummary" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
	                <div class="train-stat train-stat-wide"><span>Dataset Version</span><strong>{{ trainingStore.selectedVersion?.version_name }}</strong><small>{{ trainingStore.selectedVersion?.source_name }}</small></div>
                <div class="train-stat"><span>Usable Images</span><strong>{{ builderSummary.usable_labeled_images }}</strong><small>{{ builderSummary.original_file_count }} original files</small></div>
                <div class="train-stat"><span>Annotations</span><strong>{{ builderSummary.total_annotations }}</strong><small>{{ builderSummary.average_annotations_per_image }} avg / image</small></div>
                <div class="train-stat"><span>Classes</span><strong>{{ builderSummary.class_count }}</strong><small>{{ builderSummary.classes.join(', ') }}</small></div>
                <div class="train-stat"><span>Split Policy</span><strong>{{ versionSplit(trainingStore.selectedVersion) }}</strong><small>{{ versionSplitCounts(trainingStore.selectedVersion) }} images train / val / test</small></div>
                <div class="train-stat"><span>Preprocessing</span><strong>{{ versionResize(trainingStore.selectedVersion) }}</strong><small>{{ versionOrient(trainingStore.selectedVersion) }}</small></div>
                <div class="train-stat"><span>Augmentation</span><strong>{{ versionAugment(trainingStore.selectedVersion) }}</strong><small>Locked in Dataset Version</small></div>
                <div class="train-stat"><span>Training Config</span><strong>{{ taskLabel(trainingStore.selectedVersion?.task_type || form.taskType) }} / {{ form.family }} {{ form.size }}</strong><small>{{ form.epochs }} epochs · patience {{ form.patience }} · batch {{ batchLabel(form.batch) }}</small></div>
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
                      <span>{{ taskLabel(job.task_type) }} / {{ job.architecture_family }} / {{ job.architecture_size }} / {{ job.training_mode }}</span>
                    </div>
                    <span :class="['dataset-status-pill', `is-${job.status}`]">{{ job.status }}</span>
                  </button>
                    <div v-if="job.status === 'failed' || job.status === 'cancelled'" class="train-list-actions">
                      <button v-if="job.last_checkpoint_path" class="train-mini-action" @click.stop="resumeJob(job.id)">Resume</button>
                      <button v-if="job.status === 'failed'" class="train-mini-action" @click.stop="recomputeFailedJob(job.id)">Re-compute</button>
                      <button v-if="job.status === 'failed'" class="train-mini-action is-danger" @click.stop="requestFailedJobDelete(job)">Delete</button>
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
                      <span>{{ taskLabel(version.task_type) }} / {{ version.training_config?.family || 'yolo11' }} {{ version.training_config?.size || 'n' }} / {{ version.source_type }} / {{ version.summary.usable_labeled_images }} images</span>
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
                      <span>{{ taskLabel(model.task_type) }} / {{ model.family }} / {{ model.size }}</span>
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
                  <template v-else-if="trainingStore.selectedJob.status === 'failed' || trainingStore.selectedJob.status === 'cancelled'">
                    <button v-if="trainingStore.selectedJob.last_checkpoint_path" class="dataset-primary-button" @click="resumeJob(trainingStore.selectedJob.id)">Resume</button>
                    <button v-if="trainingStore.selectedJob.status === 'failed'" class="dataset-primary-button" @click="recomputeFailedJob(trainingStore.selectedJob.id)">Re-compute</button>
                    <button v-if="trainingStore.selectedJob.status === 'failed'" class="dataset-secondary-button" @click="requestFailedJobDelete(trainingStore.selectedJob)">Delete</button>
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
                  <div class="train-stat"><span>Job</span><strong>{{ trainingStore.selectedJob.job_name }}</strong><small>{{ taskLabel(trainingStore.selectedJob.task_type) }} / {{ trainingStore.selectedJob.architecture_family }} / {{ trainingStore.selectedJob.architecture_size }}</small></div>
                  <div class="train-stat"><span>Dataset Version</span><strong>{{ trainingStore.selectedJob.dataset_version_name }}</strong><small>{{ trainingStore.selectedJob.class_names.join(', ') }}</small></div>
                  <div class="train-stat"><span>Epoch</span><strong>{{ latestMetric ? `${latestMetric.epoch}/${latestMetric.total_epochs ?? trainingStore.selectedJob.epochs}` : `0/${trainingStore.selectedJob.epochs}` }}</strong><small>patience {{ trainingStore.selectedJob.patience ?? 30 }} · {{ trainingStore.selectedJob.training_mode }}</small></div>
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
                  <div><span>Checkpoint</span><strong>{{ trainingStore.selectedJob.base_checkpoint }}</strong><small>{{ taskLabel(trainingStore.selectedJob.task_type) }} / {{ trainingStore.selectedJob.architecture_family }} {{ trainingStore.selectedJob.architecture_size }}</small></div>
                    <div><span>Run Settings</span><strong>{{ trainingStore.selectedJob.epochs }} epochs / {{ trainingStore.selectedJob.imgsz }} px</strong><small>patience {{ trainingStore.selectedJob.patience ?? 30 }} / batch {{ batchLabel(trainingStore.selectedJob.batch) }} / workers {{ trainingStore.selectedJob.workers }}</small></div>
                    <div><span>Compute</span><strong>{{ trainingStore.selectedJob.cuda_visible_devices || trainingStore.selectedJob.device_policy }}</strong><small>device {{ trainingStore.selectedJob.train_device || 'pending' }} / AMP {{ trainingStore.selectedJob.amp === null || trainingStore.selectedJob.amp === undefined ? 'pending' : trainingStore.selectedJob.amp ? 'on' : 'off' }}</small></div>
                  </div>
              </div>
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Artifacts</h3>
                <div class="space-y-(--spacing-sm) text-[13px] text-ink-mute">
                  <div><strong class="text-ink">Output</strong><br />{{ trainingStore.selectedJob.output_dir }}</div>
                    <div><strong class="text-ink">Latest checkpoint</strong><br />{{ trainingStore.selectedJob.last_checkpoint_path || 'Waiting for first checkpoint...' }}</div>
                    <div><strong class="text-ink">Best model</strong><br />{{ trainingStore.selectedJob.best_model_path || 'Available after completion' }}</div>
                    <div><strong class="text-ink">Train log</strong><br />{{ trainingStore.selectedJob.train_log_path || 'Pending worker start' }}</div>
                    <div><strong class="text-ink">Results CSV</strong><br />{{ trainingStore.selectedJob.raw_results_csv_path || 'Pending first epoch' }}</div>
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
                <button class="dataset-primary-button" @click="navigate(`/train-tune/test/${trainingStore.selectedModel.id}`)">Test Model</button>
                <button class="dataset-secondary-button" @click="requestModelDelete(trainingStore.selectedModel)">Delete Model</button>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-(--spacing-lg)">
            <div class="space-y-(--spacing-lg)">
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-xxl) py-(--spacing-xxl)">
                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-(--spacing-md)">
                  <div class="train-stat"><span>Model Name</span><strong>{{ trainingStore.selectedModel.model_name }}</strong><small>{{ trainingStore.selectedModel.version_name }}</small></div>
                  <div class="train-stat"><span>Task</span><strong>{{ taskLabel(trainingStore.selectedModel.task_type) }}</strong><small>{{ trainingStore.selectedModel.task_type === 'segment' ? 'BBox + mask output' : trainingStore.selectedModel.task_type === 'pose' ? 'BBox + keypoint output' : trainingStore.selectedModel.task_type === 'classify_single' ? 'Single-label class output' : 'BBox output' }}</small></div>
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
                  <div><span>Checkpoint</span><strong>{{ resultJob.base_checkpoint }}</strong><small>{{ taskLabel(resultJob.task_type) }} / {{ resultJob.architecture_family }} {{ resultJob.architecture_size }}</small></div>
                  <div><span>Run Settings</span><strong>{{ resultJob.epochs }} epochs / {{ resultJob.imgsz }} px</strong><small>patience {{ resultJob.patience ?? 30 }} / batch {{ batchLabel(resultJob.batch) }} / workers {{ resultJob.workers }}</small></div>
                  <div><span>Compute</span><strong>{{ resultJob.training_mode }}</strong><small>{{ resultJob.device_policy }}</small></div>
                </div>
              </div>

              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Other Model Versions</h3>
                <div class="train-list">
                  <button v-for="model in trainingStore.models" :key="model.id" class="train-list-row" @click="openResult(model.id)">
                    <div>
                      <strong>{{ model.model_name }}</strong>
                      <span>{{ taskLabel(model.task_type) }} / {{ model.family }} / {{ model.size }}</span>
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
      <div v-if="activeAugmentStep" class="dataset-dialog-backdrop" @click.self="closeAugmentModal">
        <section class="train-augment-dialog" role="dialog" aria-modal="true" :aria-label="`${activeAugmentStep.label} augmentation`">
          <header class="dataset-modal-header">
            <div>
              <h3 class="dataset-modal-title">{{ activeAugmentStep.label }}</h3>
              <p class="dataset-modal-copy">{{ activeAugmentStep.help }}</p>
            </div>
            <button class="dataset-modal-close" @click="closeAugmentModal" :aria-label="`Close ${activeAugmentStep.label} augmentation dialog`">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </header>
          <div class="train-augment-modal-body">
            <div class="train-augment-modal-preview">
              <div v-if="augmentPreviewLoading" class="train-augment-preview-loading">Loading dataset sample...</div>
              <div v-else-if="modalPreviewFilename" class="train-augment-preview-source">Sample: {{ modalPreviewFilename }}</div>
              <figure v-for="offset in previewOffsets" :key="offset" :class="['train-augment-preview-frame', offset === 0 ? 'is-primary' : '']">
                <div class="train-augment-preview-canvas">
                  <img v-if="modalPreviewImage" :src="modalPreviewImage" alt="Augmentation preview sample" :style="modalPreviewStyle(offset)" />
                  <div v-else class="train-augment-preview-placeholder" :style="modalPreviewStyle(offset)">
                    <span></span>
                    <i></i>
                  </div>
                </div>
                <figcaption>{{ modalPreviewLabel(offset) }}</figcaption>
              </figure>
            </div>
            <div class="train-augment-modal-controls">
              <p>{{ activeAugmentStep.materialized ? 'This step is previewed and materialized into generated train images.' : 'This step is applied by YOLO during training and is not materialized into snapshot files.' }}</p>
              <div class="train-recommended-row">
                <span>Recommended value</span>
                <button type="button" @click="augmentDraft = activeAugmentStep.defaultValue">{{ formatAugmentValue(activeAugmentStep.key, activeAugmentStep.defaultValue) }}</button>
              </div>
              <div class="train-slider-shell">
                <div class="train-slider-labels">
                  <span>{{ formatAugmentValue(activeAugmentStep.key, activeAugmentStep.min) }}</span>
                  <strong>{{ formatAugmentValue(activeAugmentStep.key, augmentDraft) }}</strong>
                  <span>{{ formatAugmentValue(activeAugmentStep.key, activeAugmentStep.max) }}</span>
                </div>
                <input v-model.number="augmentDraft" type="range" :min="activeAugmentStep.min" :max="activeAugmentStep.max" :step="activeAugmentStep.step" />
              </div>
              <div class="train-augment-help-box">
                <strong>Why use {{ activeAugmentStep.label }}?</strong>
                <span>{{ activeAugmentStep.help }}</span>
              </div>
            </div>
          </div>
          <footer class="dataset-modal-footer">
            <button class="dataset-secondary-button" @click="closeAugmentModal">Go Back</button>
            <button class="dataset-primary-button" @click="applyAugmentStep">Apply</button>
          </footer>
        </section>
      </div>
    </Transition>

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

.train-gpu-chip {
  display: flex; flex-direction: column; gap: 2px; padding: 10px 14px;
  border: 1px solid var(--color-hairline); border-radius: var(--radius-md);
  background: var(--color-canvas); cursor: pointer; min-width: 140px;
  transition: border-color 160ms ease, background-color 160ms ease;
}
.train-gpu-chip strong { font-size: 13px; color: var(--color-ink); }
.train-gpu-chip span { font-size: 11px; color: var(--color-ink-mute); line-height: 1.35; }
.train-gpu-chip .train-gpu-vram { color: var(--color-primary-deep); font-weight: 600; font-size: 11px; }
.train-gpu-chip.is-active { border-color: color-mix(in srgb, var(--color-primary) 42%, var(--color-hairline)); background: color-mix(in srgb, var(--color-primary) 10%, var(--color-canvas-soft)); }
.train-gpu-chip.is-active .train-gpu-vram { color: var(--color-primary); }

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
.train-version-flow { display: grid; grid-template-columns: minmax(0, 1.4fr) repeat(2, minmax(0, 1fr)); border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas-soft); overflow: visible; }
.train-policy-sections { display: flex; flex-direction: column; gap: 12px; }
.train-policy-section { display: flex; flex-direction: column; gap: 14px; padding: 16px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas-soft); }
.train-augment-empty { display: flex; flex-direction: column; gap: 4px; min-height: 78px; justify-content: center; padding: 14px; border: 1px dashed var(--color-hairline-strong); border-radius: var(--radius-sm); background: var(--color-canvas); }
.train-augment-empty strong { color: var(--color-ink); font-size: 13px; font-weight: 500; }
.train-augment-empty span { color: var(--color-ink-mute); font-size: 12px; }
.train-augment-step-list { display: flex; flex-direction: column; gap: 8px; }
.train-augment-step-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 8px; align-items: center; padding: 8px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); }
.train-augment-step-main { min-width: 0; display: flex; flex-direction: column; gap: 3px; border: 0; background: transparent; text-align: left; cursor: pointer; }
.train-augment-step-main strong { color: var(--color-ink); font-size: 13px; font-weight: 500; }
.train-augment-step-main span { color: var(--color-ink-mute); font-size: 12px; }
.train-add-augment { position: relative; display: inline-flex; align-self: flex-start; }
.train-augment-menu { position: absolute; top: calc(100% + 8px); left: 0; z-index: 20; width: min(360px, calc(100vw - 40px)); max-height: 360px; overflow: auto; display: grid; gap: 6px; padding: 8px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas); box-shadow: 0 18px 46px rgba(0, 0, 0, 0.16); }
.train-augment-menu button { display: flex; flex-direction: column; gap: 3px; padding: 10px; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; text-align: left; cursor: pointer; transition: border-color 160ms ease, background-color 160ms ease; }
.train-augment-menu button:hover, .train-augment-menu button:focus-visible { border-color: var(--color-hairline-strong); background: var(--color-canvas-soft); }
.train-augment-menu strong { color: var(--color-ink); font-size: 13px; font-weight: 500; }
.train-augment-menu span { color: var(--color-ink-mute); font-size: 12px; }
.train-augment-dialog { width: min(920px, calc(100vw - 32px)); max-height: min(760px, calc(100vh - 32px)); display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--color-hairline); border-radius: var(--radius-lg); background: var(--color-canvas); box-shadow: 0 24px 70px rgba(0, 0, 0, 0.26); }
.train-augment-modal-body { min-height: 0; display: grid; grid-template-columns: minmax(0, 1.12fr) minmax(280px, 0.88fr); overflow: auto; border-top: 1px solid var(--color-hairline); border-bottom: 1px solid var(--color-hairline); }
.train-augment-modal-preview { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-content: center; padding: 24px; background: #d8d8d8; }
.train-augment-preview-loading, .train-augment-preview-source { grid-column: 1 / -1; justify-self: start; min-height: 22px; padding: 3px 8px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.72); color: #374151; font-size: 12px; }
.train-augment-preview-frame { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.train-augment-preview-frame.is-primary { grid-column: 1 / -1; }
.train-augment-preview-canvas { width: min(210px, 100%); aspect-ratio: 1 / 1; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #f8fafc; }
.train-augment-preview-canvas img { width: 78%; height: 78%; object-fit: cover; transition: transform 180ms ease, filter 180ms ease; }
.train-augment-preview-placeholder { position: relative; width: 78%; height: 78%; border: 1px solid rgba(15, 23, 42, 0.22); background: linear-gradient(135deg, #f8fafc 0%, #c7d2fe 48%, #a7f3d0 100%); transition: transform 180ms ease, filter 180ms ease; }
.train-augment-preview-placeholder span { position: absolute; left: 18%; top: 18%; width: 42%; height: 30%; border-radius: 4px; background: rgba(15, 23, 42, 0.72); }
.train-augment-preview-placeholder i { position: absolute; right: 18%; bottom: 18%; width: 28%; height: 38%; border: 2px solid #2563eb; border-radius: 3px; }
.train-augment-preview-frame figcaption { color: #374151; font-size: 12px; }
.train-augment-modal-controls { display: flex; flex-direction: column; gap: 18px; padding: 22px; background: var(--color-canvas-soft); }
.train-augment-modal-controls p { margin: 0; color: var(--color-ink-mute); font-size: 13px; line-height: 1.55; }
.train-recommended-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); }
.train-recommended-row span { color: var(--color-ink-mute); font-size: 12px; }
.train-recommended-row button { min-height: 28px; padding: 0 10px; border: 1px solid color-mix(in srgb, var(--color-primary) 36%, var(--color-hairline)); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--color-primary) 10%, var(--color-canvas)); color: var(--color-primary-deep); font-size: 12px; font-weight: 600; cursor: pointer; }
.train-recommended-row button:hover, .train-recommended-row button:focus-visible { border-color: var(--color-primary); background: color-mix(in srgb, var(--color-primary) 16%, var(--color-canvas)); }
.train-slider-shell { display: flex; flex-direction: column; gap: 8px; }
.train-slider-labels { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 8px; color: var(--color-ink-mute); font-size: 12px; }
.train-slider-labels strong { justify-self: center; padding: 2px 7px; border-radius: var(--radius-sm); background: var(--color-primary); color: white; font-size: 13px; font-weight: 600; }
.train-slider-labels span:last-child { justify-self: end; }
.train-slider-shell input[type='range'] { width: 100%; accent-color: var(--color-primary); cursor: pointer; }
.train-augment-help-box { display: flex; flex-direction: column; gap: 8px; margin-top: auto; padding: 14px; border-radius: var(--radius-md); background: #d8f3fb; color: #334155; }
.train-augment-help-box strong { font-size: 14px; font-weight: 600; }
.train-augment-help-box span { font-size: 12px; line-height: 1.6; }
.train-augment-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.train-augment-advanced { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; padding-top: 12px; border-top: 1px solid var(--color-hairline); }
.train-policy-preview-grid { display: flex; flex-direction: column; gap: 12px; }
.train-policy-preview-card { display: flex; flex-direction: column; gap: 8px; padding: 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); }
.train-policy-preview-card strong { color: var(--color-ink); font-size: 13px; font-weight: 500; }
.train-policy-preview-stages { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.train-policy-preview-stages figure { min-width: 0; margin: 0; }
.train-policy-preview-stages img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: #0b0f14; }
.train-policy-preview-stages figcaption { margin-top: 5px; color: var(--color-ink-mute); font-size: 11px; text-transform: uppercase; }
.train-version-flow .train-param-help::after { left: 0; top: calc(100% + 7px); bottom: auto; width: min(230px, calc(100vw - 32px)); transform: translateY(-4px); }
.train-version-flow .train-param-help:hover::after, .train-version-flow .train-param-help:focus-visible::after { transform: translateY(0); }
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
.train-version-note.is-warning { border-color: #f59e0b; color: #92400e; background: #fffbeb; }
.train-version-preview { display: flex; align-items: stretch; gap: 16px; padding: 14px 16px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas); }
.train-preview-title { width: min(180px, 100%); display: flex; flex-direction: column; justify-content: center; gap: 4px; padding-right: 16px; border-right: 1px solid var(--color-hairline); }
.train-preview-grid { flex: 1; min-width: 0; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.train-preview-grid div { min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: 4px; }
.train-preview-grid span { color: var(--color-ink-mute); font-size: 11px; text-transform: uppercase; }
.train-preview-grid strong { color: var(--color-ink); font-size: 13px; font-weight: 500; line-height: 1.4; word-break: break-word; }
.train-split-composer { position: relative; min-height: 48px; display: flex; align-items: center; }
.train-split-track { position: relative; width: 100%; min-height: 44px; display: flex; align-items: stretch; border: 1px solid var(--color-hairline-strong); border-radius: var(--radius-sm); background: var(--color-canvas); overflow: hidden; }
.train-split-name { min-width: 0; display: flex; align-items: center; padding: 0 10px; color: #171717; font-size: 11px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.train-split-name.is-val { justify-content: center; }
.train-split-name.is-test { justify-content: flex-end; }
.train-split-handle { position: absolute; top: 5px; bottom: 5px; width: 2px; transform: translateX(-1px); border-radius: 999px; background: rgba(23, 23, 23, 0.62); box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.42); pointer-events: none; }
.train-split-range-layer { position: absolute; inset: 0; }
.train-split-range { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; pointer-events: none; cursor: ew-resize; }
.train-split-range::-webkit-slider-thumb { width: 28px; height: 48px; pointer-events: auto; cursor: ew-resize; -webkit-appearance: none; appearance: none; }
.train-split-range::-moz-range-thumb { width: 28px; height: 48px; border: 0; background: transparent; pointer-events: auto; cursor: ew-resize; }
.train-split-range.is-train { z-index: 2; }
.train-split-range.is-test { z-index: 3; }
.train-split-inputs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.train-split-inputs label { min-width: 0; display: grid; grid-template-columns: 1fr minmax(58px, 74px) auto; align-items: center; gap: 8px; padding: 9px 10px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); color: var(--color-ink-mute); font-size: 12px; }
.train-split-inputs input { min-width: 0; height: 30px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas-soft); color: var(--color-ink); text-align: right; padding: 0 8px; }
.train-split-inputs strong { color: var(--color-ink); font-size: 12px; font-weight: 600; }
.train-split-presets { display: flex; flex-wrap: wrap; gap: 8px; }
.train-split-presets button { min-height: 30px; padding: 0 10px; border: 1px solid var(--color-hairline); border-radius: var(--radius-sm); background: var(--color-canvas); color: var(--color-ink); font-size: 12px; font-weight: 600; cursor: pointer; }
.train-split-presets button:hover, .train-split-presets button:focus-visible { border-color: color-mix(in srgb, var(--color-primary) 50%, var(--color-hairline)); color: var(--color-primary-deep); }
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
  .train-augment-grid, .train-augment-advanced { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .train-policy-preview-stages { grid-template-columns: 1fr; }
  .train-augment-modal-body { grid-template-columns: 1fr; }
  .train-augment-modal-preview { grid-template-columns: 1fr; }
  .train-preview-title { width: 100%; padding-right: 0; padding-bottom: 12px; border-right: 0; border-bottom: 1px solid var(--color-hairline); }
  .train-preview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .train-metric-head, .train-metric-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .train-stepper, .train-trend-grid { grid-template-columns: 1fr; }
  .train-version-delete { align-self: center; }
  .train-model-card { grid-template-columns: 1fr; align-items: stretch; }
  .train-model-meta { justify-content: space-between; }
  .train-augment-grid, .train-augment-advanced, .train-version-fields, .train-split-inputs { grid-template-columns: 1fr; }
  .train-augment-step-row { grid-template-columns: 1fr; }
  .train-augment-dialog { width: calc(100vw - 16px); max-height: calc(100vh - 16px); }
}
</style>
