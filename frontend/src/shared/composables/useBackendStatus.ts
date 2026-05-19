import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api/client'

export function useBackendStatus(intervalMs = 5000) {
  const connected = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  async function check() {
    try {
      const { data } = await api.get('/health')
      connected.value = data.model_loaded === true
    } catch {
      connected.value = false
    }
  }

  onMounted(() => {
    check()
    timer = setInterval(check, intervalMs)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { connected }
}
