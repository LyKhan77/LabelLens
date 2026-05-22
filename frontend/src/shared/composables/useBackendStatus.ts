import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api/client'

export function useBackendStatus(intervalMs = 5000) {
  const connected = ref(false)
  const yoloeStatus = ref<'offline' | 'loaded' | 'no-model'>('offline')
  const samStatus = ref<'offline' | 'loaded' | 'disabled' | 'available'>('offline')
  let timer: ReturnType<typeof setInterval> | null = null

  async function check() {
    try {
      const [healthRes, modelRes, samRes] = await Promise.allSettled([
        api.get('/health'),
        api.get('/model/status'),
        api.get('/sam/status'),
      ])

      connected.value = healthRes.status === 'fulfilled'
      if (healthRes.status === 'fulfilled') {
        connected.value = true
        const hData = healthRes.value.data
        if (hData.model_loaded) {
          yoloeStatus.value = 'loaded'
        } else {
          yoloeStatus.value = 'no-model'
        }
      } else {
        connected.value = false
        yoloeStatus.value = 'offline'
      }

      if (modelRes.status === 'fulfilled') {
        yoloeStatus.value = modelRes.value.data.loaded ? 'loaded' : 'no-model'
      }

      if (samRes.status === 'fulfilled') {
        const s = samRes.value.data
        if (!s.enabled) samStatus.value = 'disabled'
        else if (s.loaded) samStatus.value = 'loaded'
        else samStatus.value = 'available'
      } else {
        samStatus.value = connected.value ? 'available' : 'offline'
      }
    } catch {
      connected.value = false
      yoloeStatus.value = 'offline'
      samStatus.value = 'offline'
    }
  }

  onMounted(() => {
    check()
    timer = setInterval(check, intervalMs)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { connected, yoloeStatus, samStatus }
}
