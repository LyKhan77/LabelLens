import { api } from './client'
import type { GpuListResponse, GpuConfig, TrainingGpuListResponse, TrainingGpuConfig } from '../types'

export async function getGpus(): Promise<GpuListResponse> {
  const res = await api.get('/system/gpus')
  return res.data
}

export async function updateGpuConfig(yoloe_device: number, sam_device: number): Promise<{
  inference_config: GpuConfig
  yoloe_reloaded: boolean
  sam_unloaded: boolean
}> {
  const res = await api.put('/system/gpu-config', { yoloe_device, sam_device })
  return res.data
}

export async function getTrainingGpus(): Promise<TrainingGpuListResponse> {
  const res = await api.get('/system/gpus/training')
  return res.data
}

export async function updateTrainingGpuConfig(config: {
  training_mode: string
  training_device: string
  visible_devices: string
  amp: boolean
}): Promise<{ training_config: TrainingGpuConfig }> {
  const res = await api.put('/training/gpu-config', config)
  return res.data
}
