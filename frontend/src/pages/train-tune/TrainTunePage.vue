<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import { useTrainingStore } from '../../shared/stores/training'
import type { DatasetVersion } from '../../shared/api/training'

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()
const trainingStore = useTrainingStore()

const sourceType = ref<'live' | 'zip'>('live')
const selectedDataset = ref('')
const zipFile = ref<File | null>(null)
const versionName = ref('')
const splitMode = ref<'existing' | 'regenerate'>('existing')
const splitTrain = ref(70)
const splitVal = ref(20)
const splitTest = ref(10)
const autoOrient = ref(true)
const resizeMode = ref('keep')
const augmentationProfile = ref<'baseline' | 'standard'>('baseline')
const family = ref<'yolo11' | 'yolo26'>('yolo11')
const size = ref<'n' | 's' | 'm' | 'l'>('n')
const baseCheckpoint = ref('yolo11n.pt')
const epochs = ref(50)
const imgsz = ref(640)
const batch = ref(8)
const workers = ref(2)
const trainingMode = ref<'standard' | 'high_speed'>('standard')
const jobName = ref('')
const step = ref(1)
const localError = ref<string | null>(null)

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function onZipChange(event: Event) {
  const input = event.target as HTMLInputElement
  zipFile.value = input.files?.[0] ?? null
}

function defaultCheckpoint(selectedFamily: 'yolo11' | 'yolo26', selectedSize: 'n' | 's' | 'm' | 'l') {
  if (selectedFamily === 'yolo11') return `yolo11${selectedSize}.pt`
  return `models/yoloe-26${selectedSize}-seg.pt`
}

watch([family, size], ([nextFamily, nextSize]) => {
  baseCheckpoint.value = defaultCheckpoint(nextFamily, nextSize)
})

const splitConfig = computed(() => ({ train: splitTrain.value, val: splitVal.value, test: splitTest.value }))
const preprocessingConfig = computed(() => ({ auto_orient: autoOrient.value, resize_mode: resizeMode.value }))
const augmentationConfig = computed(() => ({ profile: augmentationProfile.value }))
const totalSplit = computed(() => splitTrain.value + splitVal.value + splitTest.value)
const latestMetric = computed(() => trainingStore.selectedJob?.metrics_latest ?? trainingStore.jobMetrics.at(-1) ?? null)
const activeJob = computed(() => trainingStore.selectedJob)

onMounted(async () => {
  await Promise.all([datasetStore.fetchProjects(), trainingStore.hydrate()])
})

async function buildVersion() {
  localError.value = null
  if (totalSplit.value !== 100) {
    localError.value = 'Split train/val/test harus total 100.'
    return
  }
  try {
    let version: DatasetVersion
    if (sourceType.value === 'live') {
      if (!selectedDataset.value) {
        localError.value = 'Pilih dataset project dulu.'
        return
      }
      version = await trainingStore.createLiveVersion({
        datasetName: selectedDataset.value,
        versionName: versionName.value || `${selectedDataset.value}-snapshot`,
        splitConfig: splitConfig.value,
        preprocessingConfig: preprocessingConfig.value,
        augmentationConfig: augmentationConfig.value,
        resizeMode: resizeMode.value,
      })
    } else {
      if (!zipFile.value) {
        localError.value = 'Pilih export zip dulu.'
        return
      }
      version = await trainingStore.importVersion({
        file: zipFile.value,
        versionName: versionName.value || zipFile.value.name.replace(/\.zip$/i, ''),
        splitMode: splitMode.value,
        splitConfig: splitConfig.value,
        preprocessingConfig: preprocessingConfig.value,
        augmentationConfig: augmentationConfig.value,
      })
    }
    if (!jobName.value) {
      jobName.value = `${version.version_name}-${family.value}-${size.value}`
    }
    step.value = 4
    await refreshEstimate()
  } catch (err) {
    localError.value = err instanceof Error ? err.message : 'Gagal membuat dataset version'
  }
}

async function refreshEstimate() {
  localError.value = null
  const version = trainingStore.selectedVersion
  if (!version) {
    localError.value = 'Dataset version belum ada.'
    return
  }
  try {
    await trainingStore.estimate({
      dataset_version_id: version.id,
      family: family.value,
      size: size.value,
      epochs: epochs.value,
      imgsz: imgsz.value,
      batch: batch.value,
      workers: workers.value,
      training_mode: trainingMode.value,
    })
    step.value = 5
  } catch (err) {
    localError.value = err instanceof Error ? err.message : 'Gagal membuat estimasi training'
  }
}

async function submitJob() {
  localError.value = null
  const version = trainingStore.selectedVersion
  if (!version) {
    localError.value = 'Dataset version belum ada.'
    return
  }
  try {
    await trainingStore.createJob({
      job_name: jobName.value || `${version.version_name}-${family.value}-${size.value}`,
      dataset_version_id: version.id,
      family: family.value,
      size: size.value,
      base_checkpoint: baseCheckpoint.value,
      epochs: epochs.value,
      imgsz: imgsz.value,
      batch: batch.value,
      workers: workers.value,
      training_mode: trainingMode.value,
    })
    step.value = 6
  } catch (err) {
    localError.value = err instanceof Error ? err.message : 'Gagal submit training job'
  }
}

async function openJob(jobId: string) {
  await trainingStore.selectJob(jobId)
  step.value = 6
}

function pickVersion(version: DatasetVersion) {
  trainingStore.selectedVersion = version
  step.value = Math.max(step.value, 4)
}
</script>

<template>
  <div class="train-tune-page">
    <header class="train-tune-header">
      <div class="brand">
        <img src="/favicon.png" alt="LabelLens" class="brand-logo" />
        <div>
          <div class="brand-title"><span>Label</span><span class="accent">Lens</span></div>
          <p class="brand-subtitle">Train Tune Workspace</p>
        </div>
      </div>
      <div class="header-actions">
        <button class="ghost-button" @click="navigate('/')">Mode Select</button>
        <button class="ghost-button" @click="navigate('/datasets')">Datasets</button>
        <button class="ghost-button" :disabled="!inferenceStore.modelLoaded" @click="navigate('/workspace')">Workspace</button>
      </div>
    </header>

    <main class="train-tune-layout">
      <section class="builder-panel">
        <div class="section-title">Build Training Run</div>
        <div class="stepper">
          <span v-for="label, idx in ['Source', 'Split', 'Prep', 'Model', 'Summary', 'Live']" :key="label" :class="['step-chip', step >= idx + 1 ? 'is-active' : '']">
            {{ idx + 1 }}. {{ label }}
          </span>
        </div>

        <div class="form-grid">
          <label class="field">
            <span>Source</span>
            <select v-model="sourceType">
              <option value="live">Live Dataset</option>
              <option value="zip">Export ZIP</option>
            </select>
          </label>

          <label class="field">
            <span>Version Name</span>
            <input v-model="versionName" placeholder="bolt-dataset-v1" />
          </label>

          <label v-if="sourceType === 'live'" class="field field-span">
            <span>Dataset Project</span>
            <select v-model="selectedDataset">
              <option value="" disabled>Select dataset...</option>
              <option v-for="project in datasetStore.projects" :key="project.name" :value="project.name">
                {{ project.name }}
              </option>
            </select>
          </label>

          <label v-else class="field field-span">
            <span>Export ZIP</span>
            <input type="file" accept=".zip" @change="onZipChange" />
          </label>

          <label v-if="sourceType === 'zip'" class="field">
            <span>Split Mode</span>
            <select v-model="splitMode">
              <option value="existing">Use existing split</option>
              <option value="regenerate">Regenerate split</option>
            </select>
          </label>

          <label class="field">
            <span>Train %</span>
            <input v-model.number="splitTrain" type="number" min="0" max="100" />
          </label>
          <label class="field">
            <span>Val %</span>
            <input v-model.number="splitVal" type="number" min="0" max="100" />
          </label>
          <label class="field">
            <span>Test %</span>
            <input v-model.number="splitTest" type="number" min="0" max="100" />
          </label>

          <label class="field">
            <span>Preprocessing</span>
            <select v-model="resizeMode">
              <option value="keep">Keep original size</option>
              <option value="fit">Fit to train resolution</option>
            </select>
          </label>
          <label class="field">
            <span>Auto Orient</span>
            <select v-model="autoOrient">
              <option :value="true">Enabled</option>
              <option :value="false">Disabled</option>
            </select>
          </label>
          <label class="field">
            <span>Augmentation</span>
            <select v-model="augmentationProfile">
              <option value="baseline">Baseline</option>
              <option value="standard">Standard</option>
            </select>
          </label>

          <label class="field">
            <span>Family</span>
            <select v-model="family">
              <option value="yolo11">YOLO11</option>
              <option value="yolo26">YOLO26</option>
            </select>
          </label>
          <label class="field">
            <span>Size</span>
            <select v-model="size">
              <option value="n">n</option>
              <option value="s">s</option>
              <option value="m">m</option>
              <option value="l">l</option>
            </select>
          </label>
          <label class="field field-span">
            <span>Base Checkpoint</span>
            <input v-model="baseCheckpoint" placeholder="yolo11n.pt" />
          </label>

          <label class="field">
            <span>Job Name</span>
            <input v-model="jobName" placeholder="bolt-detector" />
          </label>
          <label class="field">
            <span>Training Mode</span>
            <select v-model="trainingMode">
              <option value="standard">Standard - 1x 5080</option>
              <option value="high_speed">High-Speed - 2x 5080</option>
            </select>
          </label>
          <label class="field">
            <span>Epochs</span>
            <input v-model.number="epochs" type="number" min="1" />
          </label>
          <label class="field">
            <span>Image Size</span>
            <input v-model.number="imgsz" type="number" min="320" step="32" />
          </label>
          <label class="field">
            <span>Batch</span>
            <input v-model.number="batch" type="number" min="1" />
          </label>
          <label class="field">
            <span>Workers</span>
            <input v-model.number="workers" type="number" min="1" />
          </label>
        </div>

        <div class="builder-actions">
          <button class="primary-button" @click="buildVersion">Create Dataset Version</button>
          <button class="secondary-button" :disabled="!trainingStore.selectedVersion" @click="refreshEstimate">Refresh Summary</button>
          <button class="primary-button" :disabled="!trainingStore.currentEstimate" @click="submitJob">Queue Training Job</button>
        </div>

        <p v-if="trainingMode === 'high_speed'" class="warning">
          High-Speed Mode memakai 2x RTX 5080. Job hanya akan start saat inference idle, dan inference baru akan diblok sementara job berjalan.
        </p>
        <p v-if="localError || trainingStore.error" class="error-message">{{ localError || trainingStore.error }}</p>
      </section>

      <section class="summary-panel">
        <div class="panel-block">
          <div class="section-title">Summary</div>
          <div v-if="trainingStore.selectedVersion" class="summary-grid">
            <div><span>Dataset Version</span><strong>{{ trainingStore.selectedVersion.version_name }}</strong></div>
            <div><span>Source</span><strong>{{ trainingStore.selectedVersion.source_name }}</strong></div>
            <div><span>Usable Images</span><strong>{{ trainingStore.selectedVersion.summary.usable_labeled_images }}</strong></div>
            <div><span>Annotations</span><strong>{{ trainingStore.selectedVersion.summary.total_annotations }}</strong></div>
            <div><span>Classes</span><strong>{{ trainingStore.selectedVersion.summary.classes.join(', ') }}</strong></div>
            <div><span>Split</span><strong>{{ splitTrain }}/{{ splitVal }}/{{ splitTest }}</strong></div>
          </div>
          <div v-else class="empty-state">Build or pick a dataset version first.</div>

          <div v-if="trainingStore.currentEstimate" class="estimate-card">
            <div><span>Est. Time</span><strong>{{ trainingStore.currentEstimate.estimated_time_range_minutes[0] }}-{{ trainingStore.currentEstimate.estimated_time_range_minutes[1] }} min</strong></div>
            <div><span>Disk</span><strong>{{ trainingStore.currentEstimate.estimated_disk_usage_mb }} MB</strong></div>
            <div><span>VRAM</span><strong>{{ trainingStore.currentEstimate.estimated_vram_tier }}</strong></div>
          </div>
        </div>

        <div class="panel-block">
          <div class="panel-title-row">
            <div class="section-title">Training Jobs</div>
            <button class="ghost-button" @click="trainingStore.refreshJobs()">Refresh</button>
          </div>
          <div class="list-block">
            <button v-for="job in trainingStore.jobs" :key="job.id" class="list-row" @click="openJob(job.id)">
              <div>
                <strong>{{ job.job_name }}</strong>
                <span>{{ job.architecture_family }} / {{ job.architecture_size }} / {{ job.training_mode }}</span>
              </div>
              <span :class="['status-badge', `status-${job.status}`]">{{ job.status }}</span>
            </button>
            <div v-if="!trainingStore.jobs.length" class="empty-state">No training jobs yet.</div>
          </div>
        </div>

        <div class="panel-block">
          <div class="panel-title-row">
            <div class="section-title">Dataset Versions</div>
            <button class="ghost-button" @click="trainingStore.refreshVersions()">Refresh</button>
          </div>
          <div class="list-block">
            <button v-for="version in trainingStore.versions" :key="version.id" class="list-row" @click="pickVersion(version)">
              <div>
                <strong>{{ version.version_name }}</strong>
                <span>{{ version.source_type }} / {{ version.summary.usable_labeled_images }} imgs</span>
              </div>
            </button>
            <div v-if="!trainingStore.versions.length" class="empty-state">No dataset versions yet.</div>
          </div>
        </div>

        <div class="panel-block">
          <div class="panel-title-row">
            <div class="section-title">Model Versions</div>
            <button class="ghost-button" @click="trainingStore.refreshModels()">Refresh</button>
          </div>
          <div class="list-block">
            <div v-for="model in trainingStore.models" :key="model.id" class="list-row static-row">
              <div>
                <strong>{{ model.model_name }}</strong>
                <span>{{ model.family }} / {{ model.size }}</span>
              </div>
              <span class="status-badge status-completed">{{ model.status }}</span>
            </div>
            <div v-if="!trainingStore.models.length" class="empty-state">No trained models yet.</div>
          </div>
        </div>
      </section>

      <section class="live-panel">
        <div class="panel-title-row">
          <div class="section-title">Live Progress</div>
          <span :class="['status-badge', trainingStore.liveConnected ? 'status-running' : '']">{{ trainingStore.liveConnected ? 'live' : 'idle' }}</span>
        </div>

        <div v-if="activeJob" class="live-grid">
          <div><span>Job</span><strong>{{ activeJob.job_name }}</strong></div>
          <div><span>Status</span><strong>{{ activeJob.status }}</strong></div>
          <div><span>Mode</span><strong>{{ activeJob.training_mode }}</strong></div>
          <div><span>Output</span><strong>{{ activeJob.output_dir }}</strong></div>
          <div><span>Epoch</span><strong>{{ latestMetric ? `${latestMetric.epoch}/${latestMetric.total_epochs ?? activeJob.epochs}` : `0/${activeJob.epochs}` }}</strong></div>
          <div><span>ETA</span><strong>{{ latestMetric?.eta_sec ?? 0 }} sec</strong></div>
          <div><span>mAP50</span><strong>{{ latestMetric?.map50 ?? 0 }}</strong></div>
          <div><span>mAP50-95</span><strong>{{ latestMetric?.map50_95 ?? 0 }}</strong></div>
          <div><span>Precision</span><strong>{{ latestMetric?.precision ?? 0 }}</strong></div>
          <div><span>Recall</span><strong>{{ latestMetric?.recall ?? 0 }}</strong></div>
          <div><span>Train Loss</span><strong>{{ latestMetric?.train_loss ?? 0 }}</strong></div>
          <div><span>Val Loss</span><strong>{{ latestMetric?.val_loss ?? 0 }}</strong></div>
        </div>
        <div v-else class="empty-state">Select or queue a training job to watch live progress.</div>

        <div class="panel-title-row">
          <div class="section-title">Metrics History</div>
          <button v-if="activeJob && !['completed', 'failed', 'cancelled'].includes(activeJob.status)" class="secondary-button" @click="trainingStore.cancelJob(activeJob.id)">Cancel Job</button>
        </div>
        <div class="metrics-table">
          <div class="metrics-head">
            <span>Epoch</span><span>mAP50</span><span>mAP50-95</span><span>Precision</span><span>Recall</span>
          </div>
          <div v-for="point in trainingStore.jobMetrics" :key="point.epoch" class="metrics-row">
            <span>{{ point.epoch }}</span><span>{{ point.map50 }}</span><span>{{ point.map50_95 }}</span><span>{{ point.precision }}</span><span>{{ point.recall }}</span>
          </div>
          <div v-if="!trainingStore.jobMetrics.length" class="empty-state">No metrics yet.</div>
        </div>

        <div class="panel-title-row">
          <div class="section-title">Event Log</div>
        </div>
        <div class="log-block">
          <div v-for="event in trainingStore.liveEvents" :key="`${event.timestamp}-${event.event}`" class="log-row">
            <strong>{{ event.event }}</strong>
            <span v-if="event.event === 'metric_update'">epoch {{ event.epoch }} · mAP50 {{ event.map50 }}</span>
            <span v-else-if="event.event === 'checkpoint_saved'">{{ event.path }}</span>
            <span v-else-if="event.event === 'job_failed'">{{ event.error }}</span>
            <span v-else-if="event.event === 'log_line'">{{ event.line }}</span>
            <span v-else>{{ event.phase || event.best_model_path || 'state update' }}</span>
          </div>
          <div v-if="!trainingStore.liveEvents.length" class="empty-state">No live events yet.</div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.train-tune-page {
  min-height: 100vh;
  background: var(--color-canvas, #f6f8fb);
  color: var(--color-ink, #111827);
}

.train-tune-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.92);
}

.brand { display: flex; align-items: center; gap: 12px; }
.brand-logo { width: 36px; height: 36px; border-radius: 10px; }
.brand-title { font-size: 24px; font-weight: 700; }
.accent { color: var(--color-primary, #2563eb); }
.brand-subtitle { margin: 2px 0 0; font-size: 12px; color: #64748b; }
.header-actions { display: flex; gap: 10px; }

.train-tune-layout {
  display: grid;
  grid-template-columns: minmax(320px, 1.15fr) minmax(320px, 1fr) minmax(360px, 1.1fr);
  gap: 18px;
  padding: 18px 24px 24px;
}

.builder-panel, .summary-panel, .live-panel {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.summary-panel, .live-panel { overflow: hidden; }
.section-title { font-size: 15px; font-weight: 600; }
.panel-title-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.stepper { display: flex; flex-wrap: wrap; gap: 8px; }
.step-chip { padding: 6px 10px; border-radius: 999px; background: #eef2f7; color: #64748b; font-size: 12px; }
.step-chip.is-active { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: #64748b; }
.field-span { grid-column: 1 / -1; }
.field input, .field select {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 6px;
  background: #fff;
  padding: 10px 12px;
  color: #111827;
}
.builder-actions, .header-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.primary-button, .secondary-button, .ghost-button {
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
}
.primary-button { background: #2563eb; color: #fff; border: 1px solid #2563eb; }
.secondary-button { background: #eff6ff; color: #1d4ed8; border: 1px solid rgba(37, 99, 235, 0.2); }
.ghost-button { background: transparent; color: #475569; border: 1px solid rgba(15, 23, 42, 0.1); }
.primary-button:disabled, .secondary-button:disabled, .ghost-button:disabled { opacity: 0.55; cursor: not-allowed; }
.warning { margin: 0; font-size: 12px; color: #92400e; background: #fff7ed; border: 1px solid #fdba74; border-radius: 6px; padding: 10px 12px; }
.error-message { margin: 0; font-size: 12px; color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 10px 12px; }
.panel-block { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.summary-grid, .live-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.summary-grid div, .live-grid div, .estimate-card div { display: flex; flex-direction: column; gap: 4px; }
.summary-grid span, .live-grid span, .estimate-card span { font-size: 12px; color: #64748b; }
.summary-grid strong, .live-grid strong, .estimate-card strong { font-size: 13px; color: #111827; word-break: break-word; }
.estimate-card { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; padding: 12px; border-radius: 6px; background: #eff6ff; }
.list-block, .metrics-table, .log-block { overflow: auto; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.list-row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; text-align: left; border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 6px; padding: 10px 12px; background: #fff; cursor: pointer; }
.static-row { cursor: default; }
.list-row strong { display: block; font-size: 13px; color: #0f172a; }
.list-row span { font-size: 12px; color: #64748b; }
.status-badge { padding: 4px 8px; border-radius: 999px; background: #e2e8f0; color: #475569; font-size: 11px; text-transform: capitalize; }
.status-running { background: #dcfce7; color: #15803d; }
.status-completed { background: #dbeafe; color: #1d4ed8; }
.status-failed, .status-cancelled { background: #fee2e2; color: #b91c1c; }
.metrics-head, .metrics-row { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; font-size: 12px; }
.metrics-head { color: #64748b; font-weight: 600; }
.metrics-row { padding: 8px 0; border-top: 1px solid rgba(15, 23, 42, 0.06); color: #111827; }
.log-row { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 6px; background: #f8fafc; font-size: 12px; }
.log-row strong { color: #111827; }
.empty-state { font-size: 12px; color: #64748b; padding: 8px 0; }

@media (max-width: 1280px) {
  .train-tune-layout { grid-template-columns: 1fr; }
}
</style>
