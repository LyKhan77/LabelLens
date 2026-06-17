import { api } from './client'

export type TrainingTaskType = 'detect' | 'segment' | 'pose' | 'classify_single'

export interface DatasetVersionTrainingConfig {
  family: 'yolo11' | 'yolo26'
  size: 'n' | 's' | 'm' | 'l'
  base_checkpoint: string
  epochs: number
  patience: number
  imgsz: number
  batch: number
  workers: number
  training_mode: 'standard' | 'high_speed'
}

export interface DatasetVersion {
  id: string
  source_type: 'live_dataset' | 'export_zip'
  source_name: string
  source_ref: string
  version_name: string
  created_at: string
  class_to_id: Record<string, number>
  classes: string[]
  task_type: TrainingTaskType
  split_config: { train: number; val: number; test: number }
  training_config?: DatasetVersionTrainingConfig
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
    generated_images?: number
    final_image_count?: number
    final_train_images?: number
  }
}

export interface TrainingPolicyPreviewSampleStage {
  image: string
  annotations: Array<{ label: string; box: number[]; mask?: number[][]; keypoints?: Array<{ name?: string; x: number; y: number; visibility?: string }> }>
}

export interface TrainingPolicyPreviewSample {
  filename: string
  original: TrainingPolicyPreviewSampleStage
  preprocessed: TrainingPolicyPreviewSampleStage
  augmented: TrainingPolicyPreviewSampleStage
}

export interface TrainingPolicyPreview {
  source_type: 'live' | 'zip'
  source_name: string
  task_type: TrainingTaskType
  classes: string[]
  preprocessing_config: Record<string, unknown>
  augmentation_config: Record<string, unknown>
  samples: TrainingPolicyPreviewSample[]
}

export interface TrainingEstimate {
  dataset_version_id: string
  estimated_disk_usage_mb: number
  estimated_vram_tier: string
  estimated_time_range_minutes: [number, number]
  family: string
  size: string
  task_type: TrainingTaskType
}

export interface TrainingRecommendation {
  dataset_version_id: string
  image_count: number
  epochs: number
  patience: number
  batch: number
  imgsz: number
  augmentation_mode: 'basic' | 'advanced'
  reason: string
}

export interface TrainingJob {
  id: string
  job_name: string
  status: 'queued' | 'preparing' | 'running' | 'completed' | 'failed' | 'cancelled'
  dataset_version_id: string
  architecture_family: string
  architecture_size: string
  task_type: TrainingTaskType
  base_checkpoint: string
  device_policy: string
  training_mode: 'standard' | 'high_speed'
  epochs: number
  patience?: number
  imgsz: number
  batch: number
  workers: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  queue_position: number
  output_dir: string
  train_log_path?: string | null
  raw_results_csv_path?: string | null
  best_model_path: string | null
  last_checkpoint_path: string | null
  resume?: boolean
  resume_from_checkpoint?: string | null
  amp?: boolean | null
  cuda_device_order?: string | null
  cuda_visible_devices?: string | null
  train_device?: string | null
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
  task_type: TrainingTaskType
  best_model_path: string
  class_names: string[]
  metrics_best: TrainingMetricPoint | null
  created_at: string
  status: 'ready' | 'archived'
}

export interface TrainingEvent extends Partial<TrainingMetricPoint> {
  job_id: string
  timestamp: number
  event: 'job_started' | 'metric_update' | 'checkpoint_saved' | 'job_completed' | 'job_failed' | 'job_cancelled' | 'log_line' | 'training_device_mapping' | 'raw_results_csv_path'
  phase?: string
  path?: string
  line?: string
  error?: string
  best_model_path?: string
  last_checkpoint_path?: string
  amp?: boolean
  cuda_device_order?: string
  cuda_visible_devices?: string
  device?: string
}

export async function listDatasetVersions(): Promise<DatasetVersion[]> {
  const res = await api.get('/training/dataset-versions')
  return res.data
}

export async function deleteDatasetVersion(versionId: string): Promise<void> {
  await api.delete(`/training/dataset-versions/${versionId}`)
}

export async function previewDatasetPolicy(params: {
  sourceType: 'live' | 'zip'
  datasetName?: string
  file?: File | null
  splitConfig: { train: number; val: number; test: number }
  preprocessingConfig: Record<string, unknown>
  augmentationConfig: Record<string, unknown>
  taskType: TrainingTaskType
}): Promise<TrainingPolicyPreview> {
  const form = new FormData()
  form.append('source_type', params.sourceType)
  if (params.datasetName) form.append('dataset_name', params.datasetName)
  if (params.file) form.append('file', params.file)
  form.append('split_config', JSON.stringify(params.splitConfig))
  form.append('preprocessing_config', JSON.stringify(params.preprocessingConfig))
  form.append('augmentation_config', JSON.stringify(params.augmentationConfig))
  form.append('task_type', params.taskType)
  const res = await api.post('/training/dataset-versions/preview', form, { timeout: 120_000 })
  return res.data
}

export async function createLiveDatasetVersion(params: {
  datasetName: string
  versionName: string
  splitConfig: { train: number; val: number; test: number }
  preprocessingConfig: Record<string, unknown>
  augmentationConfig: Record<string, unknown>
  trainingConfig: DatasetVersionTrainingConfig
  resizeMode: string
  taskType: TrainingTaskType
}): Promise<DatasetVersion> {
  const form = new FormData()
  form.append('dataset_name', params.datasetName)
  form.append('version_name', params.versionName)
  form.append('split_config', JSON.stringify(params.splitConfig))
  form.append('preprocessing_config', JSON.stringify(params.preprocessingConfig))
  form.append('augmentation_config', JSON.stringify(params.augmentationConfig))
  form.append('training_config', JSON.stringify(params.trainingConfig))
  form.append('resize_mode', params.resizeMode)
  form.append('task_type', params.taskType)
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
  trainingConfig: DatasetVersionTrainingConfig
  taskType: TrainingTaskType
}): Promise<DatasetVersion> {
  const form = new FormData()
  form.append('file', params.file)
  form.append('version_name', params.versionName)
  form.append('split_mode', params.splitMode)
  form.append('split_config', JSON.stringify(params.splitConfig))
  form.append('preprocessing_config', JSON.stringify(params.preprocessingConfig))
  form.append('augmentation_config', JSON.stringify(params.augmentationConfig))
  form.append('training_config', JSON.stringify(params.trainingConfig))
  form.append('task_type', params.taskType)
  const res = await api.post('/training/dataset-versions/import', form, { timeout: 300_000 })
  return res.data
}

export async function estimateTraining(payload: {
  dataset_version_id: string
  family: string
  size: string
  epochs: number
  patience?: number
  imgsz: number
  batch: number
  workers: number
  training_mode: 'standard' | 'high_speed'
  task_type: TrainingTaskType
}): Promise<TrainingEstimate> {
  const res = await api.post('/training/estimate', payload)
  return res.data
}

export async function recommendTraining(payload: {
  dataset_version_id: string
  family?: string
  size?: string
  imgsz?: number
  task_type?: TrainingTaskType
}): Promise<TrainingRecommendation> {
  const res = await api.post('/training/recommend', payload)
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
  patience: number
  imgsz: number
  batch: number
  workers: number
  training_mode: 'standard' | 'high_speed'
  task_type: TrainingTaskType
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

export async function resumeTrainingJob(jobId: string): Promise<TrainingJob> {
  const res = await api.post(`/training/jobs/${jobId}/resume`)
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

export async function deleteModelVersion(modelId: string): Promise<void> {
  await api.delete(`/training/models/${modelId}`)
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
