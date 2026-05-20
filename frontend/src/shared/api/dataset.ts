import { api } from './client'

export interface DatasetProject {
  name: string
  created: string
  class_to_id: Record<string, number>
  stats: {
    total_images: number
    total_annotations: number
    accepted: number
    rejected: number
    classes: string[]
  }
}

export interface DatasetImage {
  img_id: string
  filename: string
  status: 'new' | 'accepted' | 'review'
  accepted: number
  rejected: number
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
): Promise<{ labeled: number; total_unlabeled: number; results: unknown[] }> {
  const form = new FormData()
  form.append('prompt_type', promptType)
  form.append('labels', JSON.stringify(labels))
  form.append('confidence', String(confidence))
  const res = await api.post(`/datasets/${name}/label`, form)
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
  },
): Promise<{ processed: number; results: unknown[] }> {
  const form = new FormData()
  if (params.file) form.append('file', params.file)
  if (params.rtspUrl) form.append('rtsp_url', params.rtspUrl)
  form.append('prompt_type', params.promptType)
  form.append('labels', JSON.stringify(params.labels ?? []))
  form.append('confidence', String(params.confidence ?? 0.5))
  form.append('sample_fps', String(params.sampleFps ?? 1))
  const res = await api.post(`/datasets/${name}/save-stream`, form, {
    timeout: 300_000,
  })
  return res.data
}
