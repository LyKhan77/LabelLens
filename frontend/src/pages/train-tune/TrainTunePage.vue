<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import { useBackendStatus } from '../../shared/composables/useBackendStatus'
import { useTheme } from '../../shared/composables/useTheme'
import { useTrainingStore } from '../../shared/stores/training'
import type { DatasetVersion, TrainingJob } from '../../shared/api/training'

const props = defineProps<{ path: string }>()

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()
const trainingStore = useTrainingStore()
const { connected } = useBackendStatus()
const { theme, toggle } = useTheme()

const form = reactive(reactiveState())

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

function defaultCheckpoint(family: 'yolo11' | 'yolo26', size: 'n' | 's' | 'm' | 'l') {
  return family === 'yolo11' ? `yolo11${size}.pt` : `models/yoloe-26${size}-seg.pt`
}

function syncCheckpoint() {
  form.baseCheckpoint = defaultCheckpoint(form.family, form.size)
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

function pickVersion(version: DatasetVersion) {
  trainingStore.selectedVersion = version
}

function openResultFromJob(job: TrainingJob | null) {
  if (!job) return
  const model = trainingStore.findModelByJobId(job.id)
  if (model) openResult(model.id)
}

const trainingSteps = [
  { title: 'Source', text: 'Live dataset project atau export zip.' },
  { title: 'Versioning', text: 'Snapshot immutable + split train/val/test.' },
  { title: 'Prep', text: 'Preprocessing dan augmentation preset.' },
  { title: 'Run Config', text: 'Family YOLO, checkpoint, GPU mode, batch.' },
]
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
        <button class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink" @click="navigate('/')">
          Mode Select
        </button>
        <button class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink" @click="navigate('/datasets')">
          Datasets
        </button>
        <button class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink" :disabled="!inferenceStore.modelLoaded" @click="navigate('/workspace')">
          Workspace
        </button>

        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="connected ? 'bg-primary' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ connected ? 'Backend Connected' : 'Backend Offline' }}</span>
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

              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md) mb-(--spacing-xxl)">
                <div v-for="stepItem in trainingSteps" :key="stepItem.title" class="border border-hairline rounded-(--radius-md) px-(--spacing-lg) py-(--spacing-lg)">
                  <div class="text-[12px] font-medium text-primary mb-(--spacing-xs)">{{ stepItem.title }}</div>
                  <p class="text-[12px] leading-[1.45] text-ink-mute">{{ stepItem.text }}</p>
                </div>
              </div>

              <div class="space-y-(--spacing-xxl)">
                <section class="space-y-(--spacing-md)">
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

                <section class="space-y-(--spacing-md)">
                  <div>
                    <h2 class="text-[18px] font-medium text-ink">Versioning, Split, and Prep</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Deterministic split, preprocessing profile, and augmentation preset are stored inside the immutable dataset version.</p>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
                    <label v-if="form.sourceType === 'zip'" class="train-field">
                      <span>Split Mode</span>
                      <select v-model="form.splitMode">
                        <option value="existing">Use existing split</option>
                        <option value="regenerate">Regenerate split</option>
                      </select>
                    </label>
                    <label class="train-field"><span>Train %</span><input v-model.number="form.splitTrain" type="number" min="0" max="100" /></label>
                    <label class="train-field"><span>Val %</span><input v-model.number="form.splitVal" type="number" min="0" max="100" /></label>
                    <label class="train-field"><span>Test %</span><input v-model.number="form.splitTest" type="number" min="0" max="100" /></label>
                    <label class="train-field"><span>Resize Mode</span><select v-model="form.resizeMode"><option value="keep">Keep original size</option><option value="fit">Fit to train resolution</option></select></label>
                    <label class="train-field"><span>Auto Orient</span><select v-model="form.autoOrient"><option :value="true">Enabled</option><option :value="false">Disabled</option></select></label>
                    <label class="train-field"><span>Augmentation</span><select v-model="form.augmentationProfile"><option value="baseline">Baseline</option><option value="standard">Standard</option></select></label>
                    <div class="train-stat">
                      <span>Split Total</span>
                      <strong>{{ totalSplit }}%</strong>
                      <small :class="totalSplit === 100 ? 'text-primary' : 'text-red-500'">{{ totalSplit === 100 ? 'Valid' : 'Must total 100' }}</small>
                    </div>
                  </div>
                </section>

                <section class="space-y-(--spacing-md)">
                  <div>
                    <h2 class="text-[18px] font-medium text-ink">Training Configuration</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Pick the YOLO family, checkpoint, and GPU mode used to schedule this run.</p>
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
                    <label class="train-field"><span>Family</span><select v-model="form.family"><option value="yolo11">YOLO11</option><option value="yolo26">YOLO26</option></select></label>
                    <label class="train-field"><span>Size</span><select v-model="form.size"><option value="n">n</option><option value="s">s</option><option value="m">m</option><option value="l">l</option></select></label>
                    <label class="train-field train-field-span"><span>Base Checkpoint</span><input v-model="form.baseCheckpoint" placeholder="yolo11n.pt" /></label>
                    <label class="train-field"><span>Job Name</span><input v-model="form.jobName" placeholder="bolt-detector" /></label>
                    <label class="train-field"><span>Training Mode</span><select v-model="form.trainingMode"><option value="standard">Standard · 1x RTX 5080</option><option value="high_speed">High-Speed · 2x RTX 5080</option></select></label>
                    <label class="train-field"><span>Epochs</span><input v-model.number="form.epochs" type="number" min="1" /></label>
                    <label class="train-field"><span>Image Size</span><input v-model.number="form.imgsz" type="number" min="320" step="32" /></label>
                    <label class="train-field"><span>Batch</span><input v-model.number="form.batch" type="number" min="1" /></label>
                    <label class="train-field"><span>Workers</span><input v-model.number="form.workers" type="number" min="1" /></label>
                  </div>
                </section>

                <section class="space-y-(--spacing-md) border-t border-hairline pt-(--spacing-xl)">
                  <div class="flex flex-wrap items-center gap-(--spacing-md)">
                    <button class="dataset-primary-button" @click="buildVersion">Create Dataset Version</button>
                    <button class="dataset-secondary-button" :disabled="!builderReady" @click="refreshEstimate">Refresh Summary</button>
                    <button class="dataset-primary-button" :disabled="!trainingStore.currentEstimate" @click="submitJob">Queue Training Job</button>
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
                <button class="dataset-secondary-button" :disabled="!builderReady" @click="refreshEstimate">Recompute</button>
              </div>

              <div v-if="builderSummary" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-(--spacing-md)">
                <div class="train-stat train-stat-wide"><span>Dataset Version</span><strong>{{ trainingStore.selectedVersion?.version_name }}</strong><small>{{ trainingStore.selectedVersion?.source_name }}</small></div>
                <div class="train-stat"><span>Usable Images</span><strong>{{ builderSummary.usable_labeled_images }}</strong><small>{{ builderSummary.original_file_count }} original files</small></div>
                <div class="train-stat"><span>Annotations</span><strong>{{ builderSummary.total_annotations }}</strong><small>{{ builderSummary.average_annotations_per_image }} avg / image</small></div>
                <div class="train-stat"><span>Classes</span><strong>{{ builderSummary.class_count }}</strong><small>{{ builderSummary.classes.join(', ') }}</small></div>
                <div class="train-stat"><span>Split</span><strong>{{ form.splitTrain }} / {{ form.splitVal }} / {{ form.splitTest }}</strong><small>train / val / test</small></div>
                <div class="train-stat"><span>Preprocessing</span><strong>{{ form.resizeMode === 'keep' ? 'Keep original' : 'Fit to train size' }}</strong><small>{{ form.autoOrient ? 'Auto orient enabled' : 'Auto orient disabled' }}</small></div>
                <div class="train-stat"><span>Augmentation</span><strong>{{ form.augmentationProfile }}</strong><small>{{ form.trainingMode === 'high_speed' ? '2x RTX 5080' : '1x RTX 5080' }}</small></div>
                <div class="train-stat" v-if="trainingStore.currentEstimate"><span>Estimate</span><strong>{{ trainingStore.currentEstimate.estimated_time_range_minutes[0] }}-{{ trainingStore.currentEstimate.estimated_time_range_minutes[1] }} min</strong><small>{{ trainingStore.currentEstimate.estimated_disk_usage_mb }} MB · {{ trainingStore.currentEstimate.estimated_vram_tier }} VRAM tier</small></div>
              </div>
              <div v-else class="text-[13px] text-ink-mute">Build or select a dataset version first to generate the final run summary.</div>
            </div>
          </div>

          <aside class="space-y-(--spacing-lg) xl:sticky xl:top-(--spacing-lg)">
            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
              <div class="flex items-center justify-between mb-(--spacing-md)">
                <h3 class="text-[16px] font-medium text-ink">Training Jobs</h3>
                <button class="dataset-secondary-button !px-2 !py-1" @click="trainingStore.refreshJobs()">Refresh</button>
              </div>
              <div class="train-list">
                <button v-for="job in trainingStore.jobs" :key="job.id" class="train-list-row" @click="openJob(job.id)">
                  <div>
                    <strong>{{ job.job_name }}</strong>
                    <span>{{ job.architecture_family }} / {{ job.architecture_size }} / {{ job.training_mode }}</span>
                  </div>
                  <span :class="['dataset-status-pill', `is-${job.status}`]">{{ job.status }}</span>
                </button>
                <div v-if="!trainingStore.jobs.length" class="train-empty">No training jobs yet.</div>
              </div>
            </div>

            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
              <div class="flex items-center justify-between mb-(--spacing-md)">
                <h3 class="text-[16px] font-medium text-ink">Dataset Versions</h3>
                <button class="dataset-secondary-button !px-2 !py-1" @click="trainingStore.refreshVersions()">Refresh</button>
              </div>
              <div class="train-list">
                <button v-for="version in trainingStore.versions" :key="version.id" class="train-list-row" @click="pickVersion(version)">
                  <div>
                    <strong>{{ version.version_name }}</strong>
                    <span>{{ version.source_type }} / {{ version.summary.usable_labeled_images }} images</span>
                  </div>
                </button>
                <div v-if="!trainingStore.versions.length" class="train-empty">No dataset versions yet.</div>
              </div>
            </div>

            <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
              <div class="flex items-center justify-between mb-(--spacing-md)">
                <h3 class="text-[16px] font-medium text-ink">Model Versions</h3>
                <button class="dataset-secondary-button !px-2 !py-1" @click="trainingStore.refreshModels()">Refresh</button>
              </div>
              <div class="train-list">
                <button v-for="model in trainingStore.models" :key="model.id" class="train-list-row" @click="openResult(model.id)">
                  <div>
                    <strong>{{ model.model_name }}</strong>
                    <span>{{ model.family }} / {{ model.size }}</span>
                  </div>
                  <span class="dataset-status-pill is-completed">{{ model.status }}</span>
                </button>
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
                <button class="train-link" @click="navigate('/train-tune')">Back to Train Tune Builder</button>
                <h1 class="text-[32px] leading-[1.1] tracking-[-0.72px] font-medium text-ink mt-(--spacing-sm)">Live Progress Training</h1>
                <p class="text-[14px] text-ink-mute leading-[1.55] max-w-[780px]">Monitor the active training run, watch epoch metrics stream in live, inspect checkpoints, and jump into the final registered result when the job completes.</p>
              </div>
              <div class="flex items-center gap-(--spacing-md)">
                <span :class="['dataset-status-pill', `is-${trainingStore.selectedJob.status}`]">{{ trainingStore.selectedJob.status }}</span>
                <button v-if="trainingStore.selectedJob.status === 'completed'" class="dataset-primary-button" @click="openResultFromJob(trainingStore.selectedJob)">Open Result</button>
                <button v-else-if="!['failed', 'cancelled'].includes(trainingStore.selectedJob.status)" class="dataset-secondary-button" @click="trainingStore.cancelJob(trainingStore.selectedJob.id)">Cancel Job</button>
              </div>
            </div>
          </div>

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
                    <h2 class="text-[20px] font-medium text-ink">Metrics History</h2>
                    <p class="text-[13px] text-ink-mute leading-[1.45]">Append-only epoch history for the current training run.</p>
                  </div>
                  <span class="text-[12px] text-ink-mute">{{ trainingStore.jobMetrics.length }} epochs captured</span>
                </div>
                <div class="train-metric-table">
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
            <button class="train-link" @click="navigate('/train-tune')">Back to Train Tune Builder</button>
            <div class="flex flex-wrap items-start justify-between gap-(--spacing-lg) mt-(--spacing-sm)">
              <div>
                <h1 class="text-[32px] leading-[1.1] tracking-[-0.72px] font-medium text-ink">Train Tune Result</h1>
                <p class="text-[14px] text-ink-mute leading-[1.55] max-w-[760px]">Registered model artifact, linked dataset version, and best metrics from the completed training job.</p>
              </div>
              <span class="dataset-status-pill is-completed">{{ trainingStore.selectedModel.status }}</span>
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
              </div>
            </div>

            <aside class="space-y-(--spacing-lg)">
              <div class="border border-hairline rounded-(--radius-lg) bg-canvas px-(--spacing-lg) py-(--spacing-lg)">
                <h3 class="text-[16px] font-medium text-ink mb-(--spacing-md)">Result Context</h3>
                <div class="space-y-(--spacing-sm) text-[13px] text-ink-mute">
                  <div><strong class="text-ink">Created</strong><br />{{ trainingStore.selectedModel.created_at }}</div>
                  <div><strong class="text-ink">Dataset Version Path</strong><br />{{ resultSourceVersion?.storage_path || 'N/A' }}</div>
                  <div><strong class="text-ink">Job Output Path</strong><br />{{ resultJob?.output_dir || 'N/A' }}</div>
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
  </div>
</template>

<style scoped>
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
.train-link { background: transparent; border: 0; padding: 0; font-size: 12px; color: var(--color-primary-deep); cursor: pointer; }
.train-metric-table { display: flex; flex-direction: column; gap: 0; }
.train-metric-head, .train-metric-row { display: grid; grid-template-columns: 72px repeat(6, minmax(0, 1fr)); gap: 12px; }
.train-metric-head { padding-bottom: 10px; border-bottom: 1px solid var(--color-hairline); font-size: 12px; color: var(--color-ink-mute); font-weight: 500; }
.train-metric-row { padding: 12px 0; border-bottom: 1px solid var(--color-hairline-cool); font-size: 13px; color: var(--color-ink); }
.train-log-block { display: flex; flex-direction: column; gap: 8px; max-height: 540px; overflow: auto; }
.train-log-row { display: flex; flex-direction: column; gap: 4px; padding: 12px; border: 1px solid var(--color-hairline); border-radius: var(--radius-md); background: var(--color-canvas-soft); }
.train-log-row strong { font-size: 12px; color: var(--color-ink); }
.train-log-row span { font-size: 12px; line-height: 1.45; color: var(--color-ink-mute); word-break: break-word; }
.dataset-status-pill { display: inline-flex; align-items: center; justify-content: center; min-height: 24px; padding: 0 10px; border-radius: 999px; font-size: 11px; text-transform: capitalize; background: var(--color-canvas-soft); color: var(--color-ink-mute); border: 1px solid var(--color-hairline); }
.dataset-status-pill.is-running, .dataset-status-pill.is-preparing { color: var(--color-primary-deep); background: color-mix(in srgb, var(--color-primary) 10%, white); border-color: color-mix(in srgb, var(--color-primary) 35%, white); }
.dataset-status-pill.is-completed { color: #14532d; background: #dcfce7; border-color: #86efac; }
.dataset-status-pill.is-failed, .dataset-status-pill.is-cancelled { color: #991b1b; background: #fee2e2; border-color: #fecaca; }

@media (max-width: 1024px) {
  .train-field-span { grid-column: span 1; }
  .train-stat-wide { grid-column: span 1; }
  .train-metric-head, .train-metric-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
