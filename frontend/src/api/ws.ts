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

export function createStreamWS(config: StreamConfig): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${location.host}/ws/stream`
  const ws = new WebSocket(url)

  ws.onopen = () => {
    ws.send(JSON.stringify(config))
  }

  return ws
}
