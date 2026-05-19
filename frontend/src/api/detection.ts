import { api } from './client'
import type { Detection, ImageDetectionResponse } from '../types'

export interface VideoDetectionResponse {
  frames: string[]
  detections: Detection[][]
  stats: {
    total_objects: number
    classes_count: Record<string, number>
    inference_ms: number
    total_frames: number
    processed_frames: number
  }
}

export async function detectImage(params: {
  file: File
  promptType: 'text' | 'visual'
  labels?: string[]
  referImage?: File
  bboxes?: [number, number, number, number][]
  vcls?: string[]
  confidence: number
  showLabels: boolean
  showBbox: boolean
}): Promise<ImageDetectionResponse> {
  const form = new FormData()
  form.append('file', params.file)
  form.append('prompt_type', params.promptType)
  form.append('confidence', String(params.confidence))
  form.append('show_labels', String(params.showLabels))
  form.append('show_bbox', String(params.showBbox))

  if (params.promptType === 'text' && params.labels) {
    form.append('labels', params.labels.join(','))
  }

  if (params.promptType === 'visual') {
    if (params.referImage) form.append('refer_image', params.referImage)
    form.append('bboxes', JSON.stringify(params.bboxes ?? []))
    form.append('vcls', JSON.stringify(params.vcls ?? []))
  }

  const { data } = await api.post<ImageDetectionResponse>('/detect/image', form)
  return data
}

export async function detectVideo(params: {
  file: File
  promptType: 'text' | 'visual'
  labels?: string[]
  referImage?: File
  bboxes?: [number, number, number, number][]
  vcls?: string[]
  confidence: number
  showLabels: boolean
  showBbox: boolean
  sampleFps?: number
  signal?: AbortSignal
}): Promise<VideoDetectionResponse> {
  const form = new FormData()
  form.append('file', params.file)
  form.append('prompt_type', params.promptType)
  form.append('confidence', String(params.confidence))
  form.append('show_labels', String(params.showLabels))
  form.append('show_bbox', String(params.showBbox))
  form.append('sample_fps', String(params.sampleFps ?? 5))

  if (params.promptType === 'text' && params.labels) {
    form.append('labels', params.labels.join(','))
  }

  if (params.promptType === 'visual') {
    if (params.referImage) form.append('refer_image', params.referImage)
    form.append('bboxes', JSON.stringify(params.bboxes ?? []))
    form.append('vcls', JSON.stringify(params.vcls ?? []))
  }

  const { data } = await api.post<VideoDetectionResponse>('/detect/video', form, {
    signal: params.signal,
  })
  return data
}
