import { api } from './client'

export interface DatasetProject {
  name: string
  created: string
  class_to_id: Record<string, number>
  class_colors: Record<string, string>
  stats: {
    total_images: number
    total_annotations: number
    accepted: number
    rejected: number
    classes: string[]
    class_counts: Record<string, number>
  }
}

export interface DatasetOverlayDetection {
  id?: number
  box: number[]
  label: string
  confidence: number
  cls_id?: number
  accepted?: boolean
  manual?: boolean
  assisted?: boolean
  source?: string
  mask?: number[][]
  mask_rle?: { x: number; y: number; width: number; height: number; counts: number[] }
}

export interface DatasetImage {
  img_id: string
  filename: string
  status: 'unlabeled' | 'new' | 'accepted' | 'review'
  accepted: number
  rejected: number
  image_url: string
  source?: string | null
  width?: number | null
  height?: number | null
  detections_preview?: DatasetOverlayDetection[]
}

export interface DatasetLabelJobItem {
  img_id: string
  filename: string
  image_url: string
  width?: number | null
  height?: number | null
  state: 'queued' | 'running' | 'done' | 'failed'
  detections_count: number
  detections?: DatasetOverlayDetection[]
  error?: string | null
}

export interface DatasetLabelJobStatus {
  job_id: string
  dataset: string
  state: 'queued' | 'running' | 'done' | 'failed'
  processed: number
  total: number
  current_image_url: string | null
  current_filename: string | null
  detections_count: number
  error: string | null
  results: unknown[]
  items: DatasetLabelJobItem[]
}

export interface ImageAnnotation {
  img_id: string
  filename: string
  annotations: {
    image: string
    width: number
    height: number
    source: string
    created: string
    detections: DetectionAnnotation[]
  } | null
}

export interface DetectionAnnotation {
  id: number
  box: number[]
  label: string
  confidence: number
  cls_id: number
  accepted: boolean
  manual?: boolean
  assisted?: boolean
  source?: string
  mask?: number[][]
  mask_rle?: { x: number; y: number; width: number; height: number; counts: number[] }
}

export async function listDatasets(): Promise<DatasetProject[]> {
  const res = await api.get('/datasets')
  return res.data
}

export async function createDataset(name: string, classes: string[] = []): Promise<unknown> {
  const form = new FormData()
  form.append('name', name)
  form.append('classes', JSON.stringify(classes))
  const res = await api.post('/datasets', form)
  return res.data
}

export async function deleteDataset(name: string): Promise<unknown> {
  const res = await api.delete(`/datasets/${name}`)
  return res.data
}

export async function updateClassColor(name: string, label: string, color: string): Promise<DatasetProject> {
  const res = await api.patch(`/datasets/${name}/class-colors`, { label, color })
  return res.data
}

export async function renameClass(name: string, oldLabel: string, newLabel: string): Promise<DatasetProject> {
  const res = await api.put(`/datasets/${name}/classes/rename`, { old_label: oldLabel, new_label: newLabel })
  return res.data
}

export async function deleteClass(name: string, label: string): Promise<DatasetProject> {
  const res = await api.delete(`/datasets/${name}/classes/${encodeURIComponent(label)}`)
  return res.data
}

export async function listImages(
  name: string,
  page = 1,
  limit = 20,
): Promise<{ images: DatasetImage[]; total: number; page: number; limit: number }> {
  const res = await api.get(`/datasets/${name}/images`, { params: { page, limit } })
  return res.data
}

export async function getImage(name: string, imgId: string): Promise<ImageAnnotation> {
  const res = await api.get(`/datasets/${name}/images/${imgId}`)
  return res.data
}

export async function saveToDataset(
  name: string,
  file: File,
  detections: unknown[],
  source = 'inference',
): Promise<unknown> {
  const form = new FormData()
  form.append('file', file)
  form.append('detections', JSON.stringify(detections))
  form.append('source', source)
  const res = await api.post(`/datasets/${name}/save`, form)
  return res.data
}

export async function uploadRaw(
  name: string,
  files: File[],
): Promise<{ uploaded: number; results: unknown[] }> {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  const res = await api.post(`/datasets/${name}/upload`, form)
  return res.data
}

export async function uploadStream(
  name: string,
  params: {
    file?: File
    rtspUrl?: string
    sampleFps?: number
  },
): Promise<{ uploaded: number; results: unknown[] }> {
  const form = new FormData()
  if (params.file) form.append('file', params.file)
  if (params.rtspUrl) form.append('rtsp_url', params.rtspUrl)
  form.append('sample_fps', String(params.sampleFps ?? 1))
  const res = await api.post(`/datasets/${name}/upload-stream`, form, {
    timeout: 300_000,
  })
  return res.data
}

export async function labelImages(
  name: string,
  promptType: string,
  labels: string[] = [],
  confidence = 0.5,
  visual?: { referImage?: File; bboxes?: [number, number, number, number][]; vcls?: string[] },
): Promise<{ labeled: number; total_unlabeled: number; results: unknown[] }> {
  const form = new FormData()
  form.append('prompt_type', promptType)
  form.append('labels', JSON.stringify(labels))
  form.append('confidence', String(confidence))
  if (visual?.referImage) form.append('refer_image', visual.referImage)
  form.append('bboxes', JSON.stringify(visual?.bboxes ?? []))
  form.append('vcls', JSON.stringify(visual?.vcls ?? []))
  const res = await api.post(`/datasets/${name}/label`, form)
  return res.data
}


export async function createLabelJob(
  name: string,
  params: {
    promptType: string
    labels?: string[]
    confidence?: number
    referImage?: File
    bboxes?: [number, number, number, number][]
    vcls?: string[]
  },
): Promise<DatasetLabelJobStatus> {
  const form = new FormData()
  form.append('prompt_type', params.promptType)
  form.append('labels', JSON.stringify(params.labels ?? []))
  form.append('confidence', String(params.confidence ?? 0.5))
  if (params.referImage) form.append('refer_image', params.referImage)
  form.append('bboxes', JSON.stringify(params.bboxes ?? []))
  form.append('vcls', JSON.stringify(params.vcls ?? []))
  const res = await api.post(`/datasets/${name}/label-jobs`, form)
  return res.data
}

export async function getLabelJob(
  name: string,
  jobId: string,
): Promise<DatasetLabelJobStatus> {
  const res = await api.get(`/datasets/${name}/label-jobs/${jobId}`)
  return res.data
}

export async function batchUpload(
  name: string,
  files: File[],
  promptType: string,
  labels: string[] = [],
  confidence = 0.5,
): Promise<{ processed: number; results: unknown[] }> {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  form.append('prompt_type', promptType)
  form.append('labels', JSON.stringify(labels))
  form.append('confidence', String(confidence))
  const res = await api.post(`/datasets/${name}/batch`, form)
  return res.data
}


export type DetectionPayload = {
  label?: string
  box?: [number, number, number, number]
  accepted?: boolean
  confidence?: number
  assisted?: boolean
  source?: string
  mask?: number[][]
  mask_rle?: { x: number; y: number; width: number; height: number; counts: number[] }
}

export async function inferNextVisualPrompt(
  name: string,
  sourceImgId: string,
  payload: {
    target_img_id: string
    prompts: { box: [number, number, number, number]; label: string }[]
    confidence?: number
  },
): Promise<{ source_img_id: string; target_img_id: string; candidates: DatasetOverlayDetection[] }> {
  const res = await api.post(`/datasets/${name}/images/${sourceImgId}/infer-next`, payload)
  return res.data
}

export async function addDetection(
  name: string,
  imgId: string,
  payload: Required<Pick<DetectionPayload, 'label' | 'box'>> & Omit<DetectionPayload, 'label' | 'box'>,
): Promise<ImageAnnotation['annotations']> {
  const res = await api.post(`/datasets/${name}/images/${imgId}/detections`, payload)
  return res.data
}

export async function updateDetection(
  name: string,
  imgId: string,
  detId: number,
  payload: DetectionPayload,
): Promise<ImageAnnotation['annotations']> {
  const res = await api.patch(`/datasets/${name}/images/${imgId}/detections/${detId}`, payload)
  return res.data
}

export async function deleteDetection(
  name: string,
  imgId: string,
  detId: number,
): Promise<ImageAnnotation['annotations']> {
  const res = await api.delete(`/datasets/${name}/images/${imgId}/detections/${detId}`)
  return res.data
}

export async function reviewImage(
  name: string,
  imgId: string,
  reviews: { id: number; accepted: boolean }[],
): Promise<unknown> {
  const res = await api.patch(`/datasets/${name}/images/${imgId}/review`, reviews)
  return res.data
}

export async function deleteImage(name: string, imgId: string): Promise<unknown> {
  const res = await api.delete(`/datasets/${name}/images/${imgId}`)
  return res.data
}

export async function exportDataset(
  name: string,
  format: 'yolo' | 'coco',
  split = 0.8,
): Promise<Blob> {
  const form = new FormData()
  form.append('format', format)
  form.append('split', String(split))
  const res = await api.post(`/datasets/${name}/export`, form, {
    responseType: 'blob',
  })
  return res.data as Blob
}

export async function saveStream(
  name: string,
  params: {
    file?: File
    rtspUrl?: string
    promptType: string
    labels?: string[]
    confidence?: number
    sampleFps?: number
    referImage?: File
    bboxes?: [number, number, number, number][]
    vcls?: string[]
  },
): Promise<{ processed: number; results: unknown[] }> {
  const form = new FormData()
  if (params.file) form.append('file', params.file)
  if (params.rtspUrl) form.append('rtsp_url', params.rtspUrl)
  form.append('prompt_type', params.promptType)
  form.append('labels', JSON.stringify(params.labels ?? []))
  form.append('confidence', String(params.confidence ?? 0.5))
  form.append('sample_fps', String(params.sampleFps ?? 1))
  if (params.referImage) form.append('refer_image', params.referImage)
  form.append('bboxes', JSON.stringify(params.bboxes ?? []))
  form.append('vcls', JSON.stringify(params.vcls ?? []))
  const res = await api.post(`/datasets/${name}/save-stream`, form, {
    timeout: 300_000,
  })
  return res.data
}

export async function generateSamMask(
  name: string,
  imgId: string,
  box: [number, number, number, number],
): Promise<{ mask?: number[][]; mask_rle?: { x: number; y: number; width: number; height: number; counts: number[] }; inference_ms: number }> {
  const res = await api.post(`/datasets/${name}/images/${imgId}/sam-mask`, { box })
  return res.data
}
