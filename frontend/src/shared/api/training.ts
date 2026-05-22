import { api } from './client'

export interface DatasetVersion {
  id: string
  source_type: 'live_dataset' | 'export_zip'
  source_name: string
  source_ref: string
  version_name: string
  created_at: string
  class_to_id: Record<string, number>
  classes: string[]
  split_config: { train: number; val: number; test: number }
  preprocessing_config: Record<string, unknown>
  augmentation_config: Record<string, unknown>
  storage_path: string
  dataset_yaml: string
  split_counts: Record<string, number | string>
  summary: {
    original_file_count: number
    usable_labeled_images: number
    total_annotations: number
    class_count: number
    classes: string[]
    average_annotations_per_image: number
  }
}

export interface TrainingEstimate {
  dataset_version_id: string
  estimated_disk_usage_mb: number
  estimated_vram_tier: string
  estimated_time_range_minutes: [number, number]
  family: string
  size: string
}

export interface TrainingJob {
  id: string
  job_name: string
  status: 'queued' | 'preparing' | 'running' | 'completed' | 'failed' | 'cancelled'
  dataset_version_id: string
  architecture_family: string
  architecture_size: string
  task_type: string
  base_checkpoint: string
  device_policy: string
  training_mode: 'standard' | 'high_speed'
  epochs: number
  imgsz: number
  batch: number
  workers: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  queue_position: number
  output_dir: string
  best_model_path: string | null
  last_checkpoint_path: string | null
  training_summary: DatasetVersion['summary']
  failure_reason: string | null
  metrics_latest: TrainingMetricPoint | null
  dataset_version_name: string
  class_names: string[]
}

export interface TrainingMetricPoint {
  epoch: number
  total_epochs?: number
  train_loss: number
  val_loss: number
  map50: number
  map50_95: number
  precision: number
  recall: number
  lr: number
  time_per_epoch_sec: number
  elapsed_sec?: number
  eta_sec?: number
}

export interface ModelVersion {
  id: string
  model_name: string
  version_name: string
  job_id: string
  dataset_version_id: string
  family: string
  size: string
  best_model_path: string
  class_names: string[]
  metrics_best: TrainingMetricPoint | null
  created_at: string
  status: 'ready' | 'archived'
}

export interface TrainingEvent extends Partial<TrainingMetricPoint> {
  job_id: string
  timestamp: number
  event: 'job_started' | 'metric_update' | 'checkpoint_saved' | 'job_completed' | 'job_failed' | 'job_cancelled' | 'log_line'
  phase?: string
  path?: string
  line?: string
  error?: string
  best_model_path?: string
  last_checkpoint_path?: string
}

export async function listDatasetVersions(): Promise<DatasetVersion[]> {
  const res = await api.get('/training/dataset-versions')
  return res.data
}

export async function deleteDatasetVersion(versionId: string): Promise<void> {
  await api.delete(`/training/dataset-versions/${versionId}`)
}

export async function createLiveDatasetVersion(params: {
  datasetName: string
  versionName: string
  splitConfig: { train: number; val: number; test: number }
  preprocessingConfig: Record<string, unknown>
  augmentationConfig: Record<string, unknown>
  resizeMode: string
}): Promise<DatasetVersion> {
  const form = new FormData()
  form.append('dataset_name', params.datasetName)
  form.append('version_name', params.versionName)
  form.append('split_config', JSON.stringify(params.splitConfig))
  form.append('preprocessing_config', JSON.stringify(params.preprocessingConfig))
  form.append('augmentation_config', JSON.stringify(params.augmentationConfig))
  form.append('resize_mode', params.resizeMode)
  const res = await api.post('/training/dataset-versions/live', form)
  return res.data
}

export async function importDatasetVersion(params: {
  file: File
  versionName: string
  splitMode: 'existing' | 'regenerate'
  splitConfig: { train: number; val: number; test: number }
  preprocessingConfig: Record<string, unknown>
  augmentationConfig: Record<string, unknown>
}): Promise<DatasetVersion> {
  const form = new FormData()
  form.append('file', params.file)
  form.append('version_name', params.versionName)
  form.append('split_mode', params.splitMode)
  form.append('split_config', JSON.stringify(params.splitConfig))
  form.append('preprocessing_config', JSON.stringify(params.preprocessingConfig))
  form.append('augmentation_config', JSON.stringify(params.augmentationConfig))
  const res = await api.post('/training/dataset-versions/import', form, { timeout: 300_000 })
  return res.data
}

export async function estimateTraining(payload: {
  dataset_version_id: string
  family: string
  size: string
  epochs: number
  imgsz: number
  batch: number
  workers: number
  training_mode: 'standard' | 'high_speed'
}): Promise<TrainingEstimate> {
  const res = await api.post('/training/estimate', payload)
  return res.data
}

export async function listTrainingJobs(): Promise<TrainingJob[]> {
  const res = await api.get('/training/jobs')
  return res.data
}

export async function getTrainingJob(jobId: string): Promise<TrainingJob> {
  const res = await api.get(`/training/jobs/${jobId}`)
  return res.data
}

export async function createTrainingJob(payload: {
  job_name: string
  dataset_version_id: string
  family: string
  size: string
  base_checkpoint: string
  epochs: number
  imgsz: number
  batch: number
  workers: number
  training_mode: 'standard' | 'high_speed'
}): Promise<TrainingJob> {
  const res = await api.post('/training/jobs', payload)
  return res.data
}

export async function cancelTrainingJob(jobId: string): Promise<TrainingJob> {
  const res = await api.post(`/training/jobs/${jobId}/cancel`)
  return res.data
}

export async function recomputeTrainingJob(jobId: string): Promise<TrainingJob> {
  const res = await api.post(`/training/jobs/${jobId}/recompute`)
  return res.data
}

export async function deleteTrainingJob(jobId: string): Promise<void> {
  await api.delete(`/training/jobs/${jobId}`)
}

export async function listTrainingMetrics(jobId: string): Promise<TrainingMetricPoint[]> {
  const res = await api.get(`/training/jobs/${jobId}/metrics`)
  return res.data
}

export async function listModelVersions(): Promise<ModelVersion[]> {
  const res = await api.get('/training/models')
  return res.data
}

export function createTrainingWS(jobId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/api/ws/training/${jobId}`)
}

export async function getModelVersion(modelId: string): Promise<ModelVersion> {
  const res = await api.get(`/training/models/${modelId}`)
  return res.data
}
