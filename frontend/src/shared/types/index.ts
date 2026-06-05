export interface BBoxAnnotation {
  bbox: [number, number, number, number]
  label: string
}

export interface TextPrompt {
  type: 'text'
  labels: string[]
}

export interface VisualPrompt {
  type: 'visual'
  referImage: File
  annotations: BBoxAnnotation[]
}

export type GroundingPrompt = TextPrompt | VisualPrompt

export interface MaskRle {
  x: number
  y: number
  width: number
  height: number
  counts: number[]
}

export interface Detection {
  box: number[]
  label: string
  confidence: number
  cls_id?: number
  mask?: [number, number][]
  mask_rle?: MaskRle
}

export interface Stats {
  total_objects: number
  classes_count: Record<string, number>
  inference_ms: number
}

export interface ImageDetectionResponse {
  image: string
  detections: Detection[]
  stats: Stats
}

export type MediaMode = 'image' | 'video' | 'rtsp'
export type PromptMode = 'text' | 'visual' | 'free'
export type InferenceMode = 'free' | 'prompt'
export type ViewerState = 'empty' | 'loading' | 'result' | 'video' | 'rtsp'

export type DatasetTaskType = 'detect' | 'segment' | 'classify_single' | 'classify_multi' | 'pose'

export interface PoseTemplate {
  name: string
  keypoint_names: string[]
  skeleton: [number, number][]
  flip_idx: number[]
  kpt_shape: [number, 3]
}

export interface DatasetTaskConfig {
  classification_mode?: 'single' | 'multi'
  requires_masks?: boolean
  pose_template?: PoseTemplate
}

// GPU Detection
export interface GpuInfo {
  index: number
  name: string
  vram_total_mb: number
  vram_used_mb: number
  uuid: string
}

export interface GpuConfig {
  yoloe_device: number
  sam_device: number
  updated_at?: string
}

export interface TrainingGpuConfig {
  training_mode: 'standard' | 'high_speed'
  training_device: string
  visible_devices: string
  amp: boolean
  updated_at?: string
}

export interface GpuListResponse {
  gpus: GpuInfo[]
  cuda_visible_devices: string
  inference_config: GpuConfig
}

export interface TrainingGpuListResponse {
  gpus: GpuInfo[]
  training_config: TrainingGpuConfig
}
