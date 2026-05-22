import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DatasetVersion, ModelVersion, TrainingEstimate, TrainingEvent, TrainingJob, TrainingMetricPoint } from '../api/training'
import * as api from '../api/training'

export const useTrainingStore = defineStore('training', () => {
  const versions = ref<DatasetVersion[]>([])
  const jobs = ref<TrainingJob[]>([])
  const models = ref<ModelVersion[]>([])
  const selectedVersion = ref<DatasetVersion | null>(null)
  const selectedJob = ref<TrainingJob | null>(null)
  const selectedModel = ref<ModelVersion | null>(null)
  const jobMetrics = ref<TrainingMetricPoint[]>([])
  const liveEvents = ref<TrainingEvent[]>([])
  const currentEstimate = ref<TrainingEstimate | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const liveConnected = ref(false)
  let ws: WebSocket | null = null

  async function hydrate() {
    loading.value = true
    error.value = null
    try {
      const [versionData, jobData, modelData] = await Promise.all([
        api.listDatasetVersions(),
        api.listTrainingJobs(),
        api.listModelVersions(),
      ])
      versions.value = versionData
      jobs.value = jobData
      models.value = modelData
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load Train Tune workspace'
    } finally {
      loading.value = false
    }
  }

  async function createLiveVersion(params: Parameters<typeof api.createLiveDatasetVersion>[0]) {
    const version = await api.createLiveDatasetVersion(params)
    versions.value = [version, ...versions.value]
    selectedVersion.value = version
    return version
  }

  async function importVersion(params: Parameters<typeof api.importDatasetVersion>[0]) {
    const version = await api.importDatasetVersion(params)
    versions.value = [version, ...versions.value]
    selectedVersion.value = version
    return version
  }

  async function estimate(payload: Parameters<typeof api.estimateTraining>[0]) {
    currentEstimate.value = await api.estimateTraining(payload)
    return currentEstimate.value
  }

  async function refreshJobs() {
    jobs.value = await api.listTrainingJobs()
    if (selectedJob.value) {
      selectedJob.value = jobs.value.find((job) => job.id === selectedJob.value?.id) ?? selectedJob.value
    }
  }

  async function refreshModels() {
    models.value = await api.listModelVersions()
    if (selectedModel.value) {
      selectedModel.value = models.value.find((model) => model.id === selectedModel.value?.id) ?? selectedModel.value
    }
  }

  async function refreshVersions() {
    versions.value = await api.listDatasetVersions()
    if (selectedVersion.value) {
      selectedVersion.value = versions.value.find((version) => version.id === selectedVersion.value?.id) ?? selectedVersion.value
    }
  }

  async function createJob(payload: Parameters<typeof api.createTrainingJob>[0]) {
    const job = await api.createTrainingJob(payload)
    jobs.value = [job, ...jobs.value]
    selectedJob.value = job
    selectedModel.value = null
    connectJob(job.id)
    return job
  }

  async function selectJob(jobId: string, options: { connect?: boolean } = {}) {
    selectedJob.value = await api.getTrainingJob(jobId)
    selectedModel.value = null
    jobMetrics.value = await api.listTrainingMetrics(jobId)
    if (options.connect !== false) {
      connectJob(jobId)
    } else {
      disconnectJob()
    }
    return selectedJob.value
  }

  async function selectModel(modelId: string) {
    selectedModel.value = await api.getModelVersion(modelId)
    const jobId = selectedModel.value.job_id
    if (jobId) {
      await selectJob(jobId, { connect: false })
    } else {
      selectedJob.value = null
      jobMetrics.value = []
      disconnectJob()
    }
    return selectedModel.value
  }

  async function cancelJob(jobId: string) {
    selectedJob.value = await api.cancelTrainingJob(jobId)
    await refreshJobs()
  }

  async function recomputeJob(jobId: string) {
    const job = await api.recomputeTrainingJob(jobId)
    jobs.value = [job, ...jobs.value]
    selectedJob.value = job
    selectedModel.value = null
    connectJob(job.id)
    return job
  }

  async function deleteJob(jobId: string) {
    await api.deleteTrainingJob(jobId)
    jobs.value = jobs.value.filter((job) => job.id !== jobId)
    if (selectedJob.value?.id === jobId) {
      selectedJob.value = null
      jobMetrics.value = []
      liveEvents.value = []
      disconnectJob()
    }
  }

  function mergeJob(jobId: string, patch: Partial<TrainingJob>) {
    jobs.value = jobs.value.map((job) => (job.id === jobId ? { ...job, ...patch } : job))
    if (selectedJob.value?.id === jobId) {
      selectedJob.value = { ...selectedJob.value, ...patch }
    }
  }

  function findModelByJobId(jobId: string) {
    return models.value.find((model) => model.job_id === jobId) ?? null
  }

  function connectJob(jobId: string) {
    disconnectJob()
    liveEvents.value = []
    liveConnected.value = false
    const socket = api.createTrainingWS(jobId)
    ws = socket

    socket.onopen = () => {
      liveConnected.value = true
    }
    socket.onclose = () => {
      liveConnected.value = false
    }
    socket.onerror = () => {
      liveConnected.value = false
    }
    socket.onmessage = async (event) => {
      try {
        const payload: TrainingEvent = JSON.parse(event.data)
        liveEvents.value = [...liveEvents.value.slice(-119), payload]
        if (payload.event === 'metric_update') {
          const point: TrainingMetricPoint = {
            epoch: payload.epoch ?? 0,
            total_epochs: payload.total_epochs,
            train_loss: payload.train_loss ?? 0,
            val_loss: payload.val_loss ?? 0,
            map50: payload.map50 ?? 0,
            map50_95: payload.map50_95 ?? 0,
            precision: payload.precision ?? 0,
            recall: payload.recall ?? 0,
            lr: payload.lr ?? 0,
            time_per_epoch_sec: payload.time_per_epoch_sec ?? 0,
            elapsed_sec: payload.elapsed_sec,
            eta_sec: payload.eta_sec,
          }
          jobMetrics.value = [...jobMetrics.value.filter((item) => item.epoch !== point.epoch), point].sort((a, b) => a.epoch - b.epoch)
          mergeJob(jobId, { status: 'running', metrics_latest: point })
        }
        if (payload.event === 'job_started') {
          mergeJob(jobId, { status: payload.phase === 'preparing' ? 'preparing' : 'running' })
        }
        if (payload.event === 'checkpoint_saved') {
          mergeJob(jobId, { last_checkpoint_path: payload.path ?? null })
        }
        if (payload.event === 'job_completed') {
          await refreshJobs()
          await refreshModels()
        }
        if (payload.event === 'job_failed' || payload.event === 'job_cancelled') {
          await refreshJobs()
        }
      } catch (err) {
        error.value = err instanceof Error ? err.message : 'Malformed training event'
      }
    }
  }

  function disconnectJob() {
    if (ws) {
      ws.close()
      ws = null
    }
    liveConnected.value = false
  }

  function resetSelection() {
    selectedVersion.value = null
    selectedJob.value = null
    selectedModel.value = null
    jobMetrics.value = []
    liveEvents.value = []
    currentEstimate.value = null
    disconnectJob()
  }

  return {
    versions,
    jobs,
    models,
    selectedVersion,
    selectedJob,
    selectedModel,
    jobMetrics,
    liveEvents,
    currentEstimate,
    loading,
    error,
    liveConnected,
    hydrate,
    createLiveVersion,
    importVersion,
    estimate,
    refreshJobs,
    refreshModels,
    refreshVersions,
    createJob,
    selectJob,
    selectModel,
    cancelJob,
    recomputeJob,
    deleteJob,
    connectJob,
    disconnectJob,
    findModelByJobId,
    resetSelection,
  }
})
