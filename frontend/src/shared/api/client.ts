import axios from 'axios'
import type { InferenceMode } from '../types'

export const api = axios.create({
  baseURL: '/api',
  timeout: 120_000,
})

export async function loadModel(mode: InferenceMode) {
  const res = await api.post('/model/load', { mode })
  return res.data
}

export async function getModelStatus() {
  const res = await api.get('/model/status')
  return res.data as {
    mode: InferenceMode | null
    loaded: boolean
    model_name: string | null
    device: string
  }
}

export async function loadCustomModel(modelId: string) {
  const res = await api.post('/model/load-custom', { model_id: modelId })
  return res.data as {
    mode: string | null
    loaded: boolean
    model_name: string | null
    device: string
    class_names: string[]
  }
}
