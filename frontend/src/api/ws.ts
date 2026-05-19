export interface StreamConfig {
  rtsp_url: string
  prompt_type: 'text' | 'visual'
  labels?: string[]
  refer_image_b64?: string
  bboxes?: [number, number, number, number][]
  vcls?: string[]
  confidence: number
  show_labels: boolean
  show_bbox: boolean
}

export interface StreamFrame {
  frame: string
  detections: { box: number[]; label: string; confidence: number }[]
  inference_ms: number
}

export interface StreamError {
  error: string
}

export type StreamMessage = StreamFrame | StreamError

export function createStreamWS(): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${location.host}/ws/stream`
  return new WebSocket(url)
}
