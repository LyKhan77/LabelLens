import { ref, shallowRef } from 'vue'
import type { Detection } from '../types'
import { createStreamWS, type StreamConfig, type StreamFrame } from '../api/ws'

export function useWebSocket() {
  const lastFrame = ref<string>('')
  const detections = ref<Detection[]>([])
  const inferenceMs = ref(0)
  const connected = ref(false)
  const error = ref<string | null>(null)
  let ws: WebSocket | null = null

  function connect(config: StreamConfig) {
    disconnect()
    error.value = null
    connected.value = false

    ws = createStreamWS(config)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (ev) => {
      try {
        const frame: StreamFrame = JSON.parse(ev.data)
        lastFrame.value = frame.frame
        detections.value = frame.detections
        inferenceMs.value = frame.inference_ms
      } catch {
        // ignore malformed frames
      }
    }

    ws.onerror = () => {
      error.value = 'Connection error'
      connected.value = false
    }

    ws.onclose = () => {
      connected.value = false
    }
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
  }

  return { lastFrame, detections, inferenceMs, connected, error, connect, disconnect }
}
