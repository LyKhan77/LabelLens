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
