import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PromptMode, MediaMode, ViewerState, BBoxAnnotation, Detection, Stats } from '../types'
import { detectImage, detectVideo } from '../api/detection'
import { useWebSocket } from '../composables/useWebSocket'

export const useInferenceStore = defineStore('inference', () => {
  // Grounding prompt
  const promptMode = ref<PromptMode>('text')
  const labels = ref<string[]>([])
  const referImage = ref<File | null>(null)
  const annotations = ref<BBoxAnnotation[]>([])

  // Media input
  const mediaMode = ref<MediaMode>('image')
  const file = ref<File | null>(null)
  const rtspUrl = ref('')

  // Settings
  const confidence = ref(0.5)
  const showLabels = ref(true)
  const showBbox = ref(true)

  // State
  const isRunning = ref(false)
  const viewerState = ref<ViewerState>('empty')
  const resultImage = ref<string>('')
  const detections = ref<Detection[]>([])
  const stats = ref<Stats | null>(null)
  const error = ref<string | null>(null)

  // Video state
  const videoFrames = ref<string[]>([])
  const videoIndex = ref(0)
  const videoPlaying = ref(false)
  let videoTimer: ReturnType<typeof setInterval> | null = null
  let abortController: AbortController | null = null

  // RTSP state
  const rtspFrame = ref<string>('')
  const rtspConnected = ref(false)
  const ws = useWebSocket()

  // Sync WebSocket reactive state to store
  watch(() => ws.lastFrame.value, (v) => { if (v) rtspFrame.value = v })
  watch(() => ws.detections.value, (v) => { detections.value = v })
  watch(() => ws.inferenceMs.value, (v) => {
    if (v > 0) {
      stats.value = {
        total_objects: detections.value.length,
        classes_count: detections.value.reduce((acc, d) => { acc[d.label] = (acc[d.label] || 0) + 1; return acc }, {} as Record<string, number>),
        inference_ms: v,
      }
    }
  })
  watch(() => ws.connected.value, (v) => { rtspConnected.value = v })
  watch(() => ws.error.value, (v) => { if (v) error.value = v })

  const hasMediaInput = computed(() => {
    if (mediaMode.value === 'rtsp') return rtspUrl.value.trim().length > 0
    return file.value !== null
  })

  const canSwitchMediaMode = computed(() => !isRunning.value && !hasMediaInput.value)

  const canRun = computed(() => {
    if (isRunning.value) return false
    if (promptMode.value === 'text' && labels.value.length === 0) return false
    if (promptMode.value === 'visual' && (annotations.value.length === 0 || !referImage.value)) return false
    if (mediaMode.value === 'image' && !file.value) return false
    if (mediaMode.value === 'video' && !file.value) return false
    if (mediaMode.value === 'rtsp' && !rtspUrl.value.trim()) return false
    return true
  })

  function addLabel(label: string) {
    const trimmed = label.trim()
    if (trimmed && !labels.value.includes(trimmed)) {
      labels.value.push(trimmed)
    }
  }

  function removeLabel(idx: number) {
    labels.value.splice(idx, 1)
  }

  function addAnnotation(ann: BBoxAnnotation) {
    annotations.value.push(ann)
  }

  function removeAnnotation(idx: number) {
    annotations.value.splice(idx, 1)
  }

  function clearAnnotations() {
    annotations.value = []
  }

  function selectMediaMode(mode: MediaMode) {
    if (mode === mediaMode.value) return
    if (!canSwitchMediaMode.value) {
      error.value = isRunning.value
        ? 'Stop inference before switching media mode'
        : 'Clear Media before switching media mode'
      return
    }
    error.value = null
    mediaMode.value = mode
  }

  function clearOutput() {
    resultImage.value = ''
    detections.value = []
    stats.value = null
    error.value = null
    viewerState.value = 'empty'
    videoFrames.value = []
    videoIndex.value = 0
    rtspFrame.value = ''
  }

  function clearMediaInput() {
    if (isRunning.value) {
      error.value = 'Stop inference before clearing media'
      return
    }

    stopVideo()
    ws.disconnect()
    rtspConnected.value = false
    file.value = null
    rtspUrl.value = ''
    clearOutput()
  }

  function buildPromptParams() {
    return {
      promptType: promptMode.value,
      labels: promptMode.value === 'text' ? labels.value : undefined,
      referImage: promptMode.value === 'visual' ? referImage.value ?? undefined : undefined,
      bboxes: promptMode.value === 'visual'
        ? annotations.value.map(a => a.bbox) as [number, number, number, number][]
        : undefined,
      vcls: promptMode.value === 'visual'
        ? annotations.value.map(a => a.label)
        : undefined,
      confidence: confidence.value,
      showLabels: showLabels.value,
      showBbox: showBbox.value,
    }
  }

  async function runInference() {
    if (!canRun.value) return

    isRunning.value = true
    error.value = null
    viewerState.value = 'loading'

    try {
      if (mediaMode.value === 'image' && file.value) {
        abortController = new AbortController()
        const resp = await detectImage({
          file: file.value,
          ...buildPromptParams(),
        })
        resultImage.value = resp.image
        detections.value = resp.detections
        stats.value = resp.stats
        viewerState.value = 'result'
      } else if (mediaMode.value === 'video' && file.value) {
        abortController = new AbortController()
        const resp = await detectVideo({
          file: file.value,
          ...buildPromptParams(),
          signal: abortController.signal,
        })
        videoFrames.value = resp.frames
        videoIndex.value = 0
        detections.value = resp.detections[0] ?? []
        stats.value = resp.stats as unknown as Stats
        viewerState.value = 'video'
        playVideo()
      } else if (mediaMode.value === 'rtsp') {
        await startRtsp()
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        viewerState.value = 'empty'
      } else {
        error.value = e instanceof Error ? e.message : 'Inference failed'
        viewerState.value = 'empty'
      }
      viewerState.value = 'empty'
    } finally {
      if (mediaMode.value !== 'rtsp') {
        isRunning.value = false
      }
    }
  }

  async function startRtsp() {
    let referImageB64: string | undefined
    if (promptMode.value === 'visual' && referImage.value) {
      referImageB64 = await fileToBase64(referImage.value)
    }

    viewerState.value = 'rtsp'
    isRunning.value = true

    ws.connect({
      rtsp_url: rtspUrl.value,
      prompt_type: promptMode.value,
      labels: promptMode.value === 'text' ? labels.value : undefined,
      refer_image_b64: referImageB64,
      bboxes: promptMode.value === 'visual'
        ? annotations.value.map(a => a.bbox) as [number, number, number, number][]
        : undefined,
      vcls: promptMode.value === 'visual'
        ? annotations.value.map(a => a.label)
        : undefined,
      confidence: confidence.value,
      show_labels: showLabels.value,
      show_bbox: showBbox.value,
    })
  }

  async function fileToBase64(f: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        resolve(result.split(',')[1])
      }
      reader.onerror = reject
      reader.readAsDataURL(f)
    })
  }

  function playVideo() {
    stopVideo()
    videoPlaying.value = true
    videoTimer = setInterval(() => {
      if (videoIndex.value < videoFrames.value.length - 1) {
        videoIndex.value++
        resultImage.value = videoFrames.value[videoIndex.value]
      } else {
        videoIndex.value = 0
      }
    }, 200)
  }

  function stopVideo() {
    if (videoTimer) {
      clearInterval(videoTimer)
      videoTimer = null
    }
    videoPlaying.value = false
  }

  function stopInference() {
    isRunning.value = false
    stopVideo()
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    if (mediaMode.value === 'rtsp') {
      ws.disconnect()
      rtspConnected.value = false
      rtspFrame.value = ''
    }
    if (viewerState.value === 'loading' || viewerState.value === 'rtsp') {
      viewerState.value = 'empty'
    }
  }

  function reset() {
    clearOutput()
    stopVideo()
  }

  return {
    promptMode, labels, referImage, annotations,
    mediaMode, file, rtspUrl,
    confidence, showLabels, showBbox,
    isRunning, viewerState, resultImage, detections, stats, error,
    videoFrames, videoIndex, videoPlaying,
    rtspFrame, rtspConnected, ws,
    hasMediaInput, canSwitchMediaMode, canRun,
    addLabel, removeLabel, addAnnotation, removeAnnotation, clearAnnotations,
    selectMediaMode, clearMediaInput,
    runInference, stopInference, reset, playVideo, stopVideo,
  }
})
