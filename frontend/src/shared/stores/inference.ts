import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PromptMode, MediaMode, ViewerState, BBoxAnnotation, Detection, Stats, Classification, InferenceMode } from '../types'
import { detectImage, detectVideo } from '../api/detection'
import { loadModel, getModelStatus } from '../api/client'
import { useWebSocket } from '../composables/useWebSocket'
import { useDatasetStore } from './dataset'

export const useInferenceStore = defineStore('inference', () => {
  // Mode selection
  const inferenceMode = ref<InferenceMode | null>(null)
  const modelLoaded = ref(false)
  const modelLoading = ref(false)
  const modelError = ref<string | null>(null)
  const loadingMode = ref<InferenceMode | null>(null)

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
  const showMasks = ref(false)

  // State
  const isRunning = ref(false)
  const viewerState = ref<ViewerState>('empty')
  const resultImage = ref<string>('')
  const detections = ref<Detection[]>([])
  const stats = ref<Stats | null>(null)
  const classification = ref<Classification | null>(null)
  const error = ref<string | null>(null)

  // Video state
  const videoFrames = ref<string[]>([])
  const videoDetections = ref<Detection[][]>([])
  const videoIndex = ref(0)
  const videoPlaying = ref(false)
  let videoTimer: ReturnType<typeof setInterval> | null = null
  let abortController: AbortController | null = null

  // RTSP state
  const rtspFrame = ref<string>('')
  const rtspConnected = ref(false)
  const ws = useWebSocket()
  const datasetStore = useDatasetStore()
  let rtspAutoSaveTimer: ReturnType<typeof setInterval> | null = null
  let rtspAutoLabelStopTimer: ReturnType<typeof setTimeout> | null = null
  let rtspAutoSaveInFlight = false

  function clearRtspAutoSaveLoop() {
    if (rtspAutoSaveTimer) {
      clearInterval(rtspAutoSaveTimer)
      rtspAutoSaveTimer = null
    }
    if (rtspAutoLabelStopTimer) {
      clearTimeout(rtspAutoLabelStopTimer)
      rtspAutoLabelStopTimer = null
    }
    rtspAutoSaveInFlight = false
  }

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
  watch(videoIndex, (idx) => {
    if (viewerState.value === 'video') {
      detections.value = videoDetections.value[idx] ?? []
    }
  })
  watch(
    () => [
      mediaMode.value,
      isRunning.value,
      datasetStore.autoLabelActive,
      datasetStore.autoLabelDataset,
      datasetStore.autoLabelFps,
      datasetStore.autoLabelRtspTimerSeconds,
    ],
    () => {
      if (
        mediaMode.value === 'rtsp' &&
        isRunning.value &&
        datasetStore.autoLabelActive &&
        datasetStore.autoLabelDataset
      ) {
        startRtspAutoSaveLoop()
      } else {
        clearRtspAutoSaveLoop()
      }
    },
    { immediate: true },
  )

  const hasMediaInput = computed(() => {
    if (mediaMode.value === 'rtsp') return rtspUrl.value.trim().length > 0
    return file.value !== null
  })

  const canSwitchMediaMode = computed(() => !isRunning.value && !hasMediaInput.value)

  const canRun = computed(() => {
    if (isRunning.value) return false
    if (inferenceMode.value === 'free') {
      // Free mode needs no prompt validation
    } else {
      if (promptMode.value === 'text' && labels.value.length === 0) return false
      if (promptMode.value === 'visual' && (annotations.value.length === 0 || !referImage.value)) return false
    }
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
    classification.value = null
    error.value = null
    viewerState.value = 'empty'
    videoFrames.value = []
    videoDetections.value = []
    videoIndex.value = 0
    rtspFrame.value = ''
  }

  function clearMediaInput() {
    if (isRunning.value) {
      error.value = 'Stop inference before clearing media'
      return
    }

    stopVideo()
    clearRtspAutoSaveLoop()
    ws.disconnect()
    rtspConnected.value = false
    file.value = null
    rtspUrl.value = ''
    clearOutput()
  }

  function buildPromptParams() {
    const effectivePromptType = inferenceMode.value === 'free' ? 'free' as const : promptMode.value
    return {
      promptType: effectivePromptType,
      labels: effectivePromptType === 'text' ? labels.value : undefined,
      referImage: effectivePromptType === 'visual' ? referImage.value ?? undefined : undefined,
      bboxes: effectivePromptType === 'visual'
        ? annotations.value.map(a => a.bbox) as [number, number, number, number][]
        : undefined,
      vcls: effectivePromptType === 'visual'
        ? annotations.value.map(a => a.label)
        : undefined,
      confidence: confidence.value,
      showLabels: showLabels.value,
      showBbox: showBbox.value,
      showMasks: showMasks.value,
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
        classification.value = resp.classification ?? null
        viewerState.value = 'result'

        // Auto-save to dataset if auto-labelling is active
        await autoSaveToDataset()
        // Auto-crop detected objects to dataset if auto-crop is active
        await autoCropToDataset()
      } else if (mediaMode.value === 'video' && file.value) {
        abortController = new AbortController()
        const resp = await detectVideo({
          file: file.value,
          ...buildPromptParams(),
          cropTarget: datasetStore.autoCropActive ? datasetStore.autoCropDataset ?? undefined : undefined,
          signal: abortController.signal,
        })
        videoFrames.value = resp.frames
        videoDetections.value = resp.detections
        videoIndex.value = 0
        resultImage.value = videoFrames.value[0] ?? ''
        detections.value = videoDetections.value[0] ?? []
        stats.value = resp.stats as unknown as Stats
        viewerState.value = 'video'
        await autoSaveToDataset()
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
      show_masks: showMasks.value,
      crop_target: datasetStore.autoCropActive ? datasetStore.autoCropDataset ?? undefined : undefined,
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

  function frameBase64ToFile(base64: string): File | null {
    try {
      const binary = atob(base64)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i)
      }
      const blob = new Blob([bytes], { type: 'image/jpeg' })
      return new File([blob], `rtsp_${Date.now()}.jpg`, { type: 'image/jpeg' })
    } catch {
      return null
    }
  }

  function playVideo() {
    stopVideo()
    videoPlaying.value = true
    videoTimer = setInterval(() => {
      if (videoIndex.value < videoFrames.value.length - 1) {
        videoIndex.value += 1
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
    clearRtspAutoSaveLoop()
    if (datasetStore.autoLabelActive) {
      datasetStore.disableAutoLabel()
    }
    if (datasetStore.autoCropActive) {
      datasetStore.disableAutoCrop()
    }
    if (viewerState.value === 'loading' || viewerState.value === 'rtsp') {
      viewerState.value = 'empty'
    }
  }

  function reset() {
    clearOutput()
    stopVideo()
    clearRtspAutoSaveLoop()
  }

  async function autoSaveToDataset() {
    if (!datasetStore.autoLabelActive || !datasetStore.autoLabelDataset) return

    const params = buildPromptParams()
    const streamParams = {
      promptType: params.promptType,
      labels: params.labels,
      confidence: params.confidence,
      sampleFps: datasetStore.autoLabelFps,
      referImage: params.referImage,
      bboxes: params.bboxes,
      vcls: params.vcls,
    }

    try {
      if (mediaMode.value === 'image' && file.value) {
        if (detections.value.length === 0) return
        await datasetStore.saveToDataset(
          datasetStore.autoLabelDataset,
          file.value,
          detections.value,
          mediaMode.value,
        )
      } else if (mediaMode.value === 'video' && file.value) {
        await datasetStore.saveStream(datasetStore.autoLabelDataset, {
          file: file.value,
          ...streamParams,
        })
      }
    } catch {
      // Auto-save failure should not block inference
    }
  }

  async function autoCropToDataset() {
    if (!datasetStore.autoCropActive || !datasetStore.autoCropDataset) return
    if (mediaMode.value !== 'image' || !file.value) return
    if (detections.value.length === 0) return
    try {
      await datasetStore.saveCrops(datasetStore.autoCropDataset, file.value, detections.value)
    } catch {
      // Auto-crop failure should not block inference
    }
  }

  function startRtspAutoSaveLoop() {
    clearRtspAutoSaveLoop()

    if (!datasetStore.autoLabelActive || !datasetStore.autoLabelDataset) {
      return
    }

    const fps = Math.max(0.1, datasetStore.autoLabelFps)
    const intervalMs = Math.max(200, Math.round(1000 / fps))

    rtspAutoSaveTimer = setInterval(() => {
      void autoSaveRtspFrame()
    }, intervalMs)

    if (datasetStore.autoLabelRtspTimerSeconds && datasetStore.autoLabelRtspTimerSeconds > 0) {
      rtspAutoLabelStopTimer = setTimeout(() => {
        datasetStore.disableAutoLabel()
        clearRtspAutoSaveLoop()
      }, datasetStore.autoLabelRtspTimerSeconds * 1000)
    }
  }

  async function autoSaveRtspFrame() {
    if (rtspAutoSaveInFlight) return
    if (mediaMode.value !== 'rtsp') return
    if (!datasetStore.autoLabelActive || !datasetStore.autoLabelDataset) return
    if (!rtspFrame.value || detections.value.length === 0) return

    const frameFile = frameBase64ToFile(rtspFrame.value)
    if (!frameFile) return

    rtspAutoSaveInFlight = true
    try {
      await datasetStore.saveToDataset(
        datasetStore.autoLabelDataset,
        frameFile,
        detections.value,
        'rtsp',
      )
    } catch {
      // Auto-save failure should not block stream inference
    } finally {
      rtspAutoSaveInFlight = false
    }
  }

  async function selectMode(mode: InferenceMode) {
    modelLoading.value = true
    modelError.value = null
    loadingMode.value = mode
    try {
      const result = await loadModel(mode)
      if (result.loaded) {
        inferenceMode.value = mode
        modelLoaded.value = true
      } else {
        modelError.value = result.error || 'Failed to load model'
      }
    } catch (e: unknown) {
      modelError.value = e instanceof Error ? e.message : 'Failed to load model'
    } finally {
      modelLoading.value = false
      loadingMode.value = null
    }
  }

  async function loadModelStatus() {
    try {
      const status = await getModelStatus()
      if (status.loaded) {
        inferenceMode.value = status.mode as InferenceMode
        modelLoaded.value = true
      }
    } catch {
      // Backend unreachable, stay on mode selection
    }
  }

  function switchMode() {
    if (isRunning.value) stopInference()
    modelLoaded.value = false
    inferenceMode.value = null
    modelError.value = null
    loadingMode.value = null
  }

  return {
    inferenceMode, modelLoaded, modelLoading, modelError, loadingMode,
    promptMode, labels, referImage, annotations,
    mediaMode, file, rtspUrl,
    confidence, showLabels, showBbox, showMasks,
    isRunning, viewerState, resultImage, detections, stats, classification, error,
    videoFrames, videoDetections, videoIndex, videoPlaying,
    rtspFrame, rtspConnected, ws,
    hasMediaInput, canSwitchMediaMode, canRun,
    addLabel, removeLabel, addAnnotation, removeAnnotation, clearAnnotations,
    selectMediaMode, clearMediaInput,
    runInference, stopInference, reset, playVideo, stopVideo,
    selectMode, loadModelStatus, switchMode,
  }
})
