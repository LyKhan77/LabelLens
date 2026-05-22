import { api } from './client'

export interface SamStatus {
  enabled: boolean
  loaded: boolean
  loading: boolean
  model: string | null
  device: string
}

export interface SamMaskResponse {
  mask?: number[][]
  mask_rle?: { x: number; y: number; width: number; height: number; counts: number[] }
  inference_ms: number
}

export async function getSamStatus(): Promise<SamStatus> {
  const res = await api.get('/sam/status')
  return res.data
}

export async function loadSam(): Promise<SamStatus> {
  const res = await api.post('/sam/load')
  return res.data
}

export async function unloadSam(): Promise<{ unloaded: boolean }> {
  const res = await api.post('/sam/unload')
  return res.data
}
