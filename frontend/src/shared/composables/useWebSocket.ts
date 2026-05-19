import { ref } from 'vue'
import type { Detection } from '../types'
import { createStreamWS, type StreamConfig, type StreamMessage } from '../api/ws'

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

    const socket = createStreamWS()
    ws = socket

    socket.onopen = () => {
      connected.value = true
      socket.send(JSON.stringify(config))
    }

    socket.onmessage = (ev) => {
      try {
        const message: StreamMessage = JSON.parse(ev.data)
        if ('error' in message) {
          error.value = message.error
          return
        }

        lastFrame.value = message.frame
        detections.value = message.detections
        inferenceMs.value = message.inference_ms
      } catch {
        // ignore malformed frames
      }
    }

    socket.onerror = () => {
      error.value = 'Connection error'
      connected.value = false
    }

    socket.onclose = () => {
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
