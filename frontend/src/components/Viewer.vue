<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Detection, MaskRle } from '../types'
import { useInferenceStore } from '../stores/inference'
import DetectionLog from './DetectionLog.vue'
import StatsGrid from './StatsGrid.vue'

const store = useInferenceStore()
const mediaImg = ref<HTMLImageElement | null>(null)
const mediaWrapper = ref<HTMLDivElement | null>(null)
const maskCanvas = ref<HTMLCanvasElement | null>(null)
const statsPanelOpen = ref(true)

const MASK_RGB = [
  [62, 207, 142],
  [107, 1, 194],
  [37, 99, 235],
  [255, 219, 19],
  [234, 88, 12],
]

const MASK_COLORS = MASK_RGB.map(([r, g, b]) => `rgba(${r}, ${g}, ${b}, 0.25)`)
const MASK_STROKES = MASK_RGB.map(([r, g, b]) => `rgba(${r}, ${g}, ${b}, 0.65)`)

const activeDetections = computed<Detection[]>(() => {
  if (store.viewerState === 'video') {
    return store.videoDetections[store.videoIndex] ?? []
  }
  return store.detections
})

let resizeObserver: ResizeObserver | null = null
let pendingFrame: number | null = null

function scheduleDrawMasks() {
  if (pendingFrame !== null) {
    cancelAnimationFrame(pendingFrame)
  }

  pendingFrame = requestAnimationFrame(() => {
    pendingFrame = null
    void nextTick(drawMasks)
  })
}



function drawRasterMask(
  ctx: CanvasRenderingContext2D,
  mask: MaskRle,
  color: number[],
  naturalWidth: number,
  naturalHeight: number,
  displayWidth: number,
  displayHeight: number,
) {
  if (mask.width <= 0 || mask.height <= 0 || mask.counts.length === 0) return

  const maskCanvas = document.createElement('canvas')
  maskCanvas.width = mask.width
  maskCanvas.height = mask.height

  const maskCtx = maskCanvas.getContext('2d')
  if (!maskCtx) return

  const imageData = maskCtx.createImageData(mask.width, mask.height)
  let value = 0
  let pixel = 0
  for (const count of mask.counts) {
    if (value === 1) {
      for (let i = 0; i < count; i++) {
        const offset = (pixel + i) * 4
        imageData.data[offset] = color[0]
        imageData.data[offset + 1] = color[1]
        imageData.data[offset + 2] = color[2]
        imageData.data[offset + 3] = 102
      }
    }
    pixel += count
    value = value === 0 ? 1 : 0
  }

  maskCtx.putImageData(imageData, 0, 0)

  const dx = (mask.x / naturalWidth) * displayWidth
  const dy = (mask.y / naturalHeight) * displayHeight
  const dw = (mask.width / naturalWidth) * displayWidth
  const dh = (mask.height / naturalHeight) * displayHeight

  ctx.imageSmoothingEnabled = true
  ctx.save()
  ctx.filter = 'blur(1px)'
  ctx.drawImage(maskCanvas, dx, dy, dw, dh)
  ctx.restore()
}

function drawSmoothPolygon(ctx: CanvasRenderingContext2D, points: [number, number][]) {
  const len = points.length
  if (len < 3) return

  const first = midpoint(points[0], points[1])
  ctx.moveTo(first[0], first[1])

  for (let i = 1; i <= len; i++) {
    const current = points[i % len]
    const next = points[(i + 1) % len]
    const mid = midpoint(current, next)
    ctx.quadraticCurveTo(current[0], current[1], mid[0], mid[1])
  }
}

function midpoint(a: [number, number], b: [number, number]): [number, number] {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}

function drawMasks() {
  const img = mediaImg.value
  const wrapper = mediaWrapper.value
  const canvas = maskCanvas.value
  if (!img || !wrapper || !canvas) return

  const rect = wrapper.getBoundingClientRect()
  const width = rect.width
  const height = rect.height
  const naturalWidth = img.naturalWidth
  const naturalHeight = img.naturalHeight
  if (!width || !height || !naturalWidth || !naturalHeight) return

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.round(width * dpr)
  canvas.height = Math.round(height * dpr)

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  if (!store.showMasks) return

  const sorted = activeDetections.value
    .map((det, index) => ({
      det,
      index,
      area: (det.box[2] - det.box[0]) * (det.box[3] - det.box[1]),
    }))
    .sort((a, b) => b.area - a.area)

  sorted.forEach(({ det, index }) => {
    if (det.mask_rle) {
      drawRasterMask(
        ctx,
        det.mask_rle,
        MASK_RGB[index % MASK_RGB.length],
        naturalWidth,
        naturalHeight,
        width,
        height,
      )
      return
    }

    if (!det.mask || det.mask.length < 3) return

    const points = det.mask.map(([x, y]) => [
      (x / naturalWidth) * width,
      (y / naturalHeight) * height,
    ] as [number, number])

    ctx.beginPath()
    drawSmoothPolygon(ctx, points)
    ctx.closePath()
    ctx.fillStyle = MASK_COLORS[index % MASK_COLORS.length]
    ctx.strokeStyle = MASK_STROKES[index % MASK_STROKES.length]
    ctx.lineWidth = 1.5
    ctx.fill()
    ctx.stroke()
  })
}

watch(mediaImg, (img) => {
  resizeObserver?.disconnect()
  resizeObserver = null

  if (img && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(scheduleDrawMasks)
    resizeObserver.observe(img)
    const wrapper = mediaWrapper.value
    if (wrapper) resizeObserver.observe(wrapper)
  }

  scheduleDrawMasks()
})

watch(
  () => [
    store.showMasks,
    store.viewerState,
    store.resultImage,
    store.rtspFrame,
    store.videoIndex,
    store.detections,
    store.videoDetections,
  ],
  scheduleDrawMasks,
  { deep: true },
)

onMounted(() => {
  window.addEventListener('resize', scheduleDrawMasks)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (pendingFrame !== null) {
    cancelAnimationFrame(pendingFrame)
  }
  window.removeEventListener('resize', scheduleDrawMasks)
})
</script>

<template>
  <div class="min-w-0 min-h-0 flex-1 flex items-center justify-center bg-canvas-soft relative overflow-hidden">
    <!-- Stats toggle pill (collapsed) -->
    <button
      v-if="store.stats && store.viewerState !== 'empty' && store.viewerState !== 'loading' && !statsPanelOpen"
      class="absolute right-3 top-3 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border border-hairline bg-canvas/95 shadow-md backdrop-blur text-[11px] font-medium uppercase tracking-wider text-ink-mute hover:text-ink hover:bg-canvas transition-colors cursor-pointer"
      aria-label="Show Inference Stats"
      @click="statsPanelOpen = true"
    >
      <span class="h-1.5 w-1.5 rounded-full bg-primary" />
      Stats
    </button>
    <!-- Stats panel (expanded) -->
    <aside
      v-if="store.stats && store.viewerState !== 'empty' && store.viewerState !== 'loading' && statsPanelOpen"
      class="absolute right-3 top-3 z-10 w-[260px] max-h-[calc(100%-1.5rem)] overflow-hidden rounded-(--radius-md) border border-hairline bg-canvas/95 p-2 shadow-lg backdrop-blur"
      aria-label="Inference Stats and Detection Log"
    >
      <div class="mb-1.5 flex items-center justify-between gap-2">
        <p class="text-[11px] font-medium uppercase tracking-wider text-ink-mute">Inference Stats</p>
        <button
          class="p-0.5 rounded hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          aria-label="Hide Inference Stats"
          @click="statsPanelOpen = false"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <StatsGrid />
      <div class="my-2 border-t border-hairline" />
      <DetectionLog />
    </aside>
    <!-- Empty state -->
    <div v-if="store.viewerState === 'empty'" class="text-center">
      <svg class="w-16 h-16 mx-auto mb-3 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <path d="m21 15-5-5L5 21" />
      </svg>
      <p class="text-ink-mute text-sm">Upload media and run inference to see results</p>
      <p v-if="store.error" class="text-red-500 text-xs mt-2">{{ store.error }}</p>
    </div>

    <!-- Loading state -->
    <div v-else-if="store.viewerState === 'loading'" class="text-center">
      <div class="w-10 h-10 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
      <p class="text-ink-mute text-sm mb-3">Running inference...</p>
      <button
        class="px-4 py-1.5 text-sm font-medium rounded-sm border border-hairline text-ink-mute hover:text-ink hover:bg-canvas transition-colors"
        @click="store.stopInference()"
      >
        Cancel
      </button>
    </div>

    <!-- Image result -->
    <div v-else-if="store.viewerState === 'result'" class="w-full h-full min-h-0 flex items-center justify-center p-3 sm:p-4">
      <div ref="mediaWrapper" class="relative inline-flex max-w-full max-h-full overflow-hidden">
        <img
          ref="mediaImg"
          :src="`data:image/jpeg;base64,${store.resultImage}`"
          alt="Detection result"
          class="max-w-full max-h-full rounded-lg shadow-lg object-contain"
          @load="drawMasks"
        />
        <canvas
          ref="maskCanvas"
          class="pointer-events-none absolute inset-0 rounded-lg"
          aria-hidden="true"
        />
      </div>
    </div>

    <!-- Video result -->
    <div v-else-if="store.viewerState === 'video'" class="w-full h-full min-h-0 flex flex-col">
      <div class="min-h-0 flex-1 flex items-center justify-center p-3 sm:p-4">
        <div ref="mediaWrapper" class="relative inline-flex max-w-full max-h-full overflow-hidden">
          <img
            ref="mediaImg"
            :src="`data:image/jpeg;base64,${store.videoFrames[store.videoIndex]}`"
            alt="Video frame"
            class="max-w-full max-h-full rounded-lg shadow-lg object-contain"
            @load="drawMasks"
          />
          <canvas
            ref="maskCanvas"
            class="pointer-events-none absolute inset-0 rounded-lg"
            aria-hidden="true"
          />
        </div>
      </div>
      <!-- Video controls -->
      <div class="flex items-center gap-2 px-4 py-2 border-t border-hairline bg-canvas">
        <button
          class="px-2 py-1 text-sm rounded-xs border border-hairline hover:bg-canvas-soft transition-colors"
          @click="store.videoPlaying ? store.stopVideo() : store.playVideo()"
        >
          {{ store.videoPlaying ? 'Pause' : 'Play' }}
        </button>
        <div class="flex-1">
          <input
            v-model.number="store.videoIndex"
            type="range"
            min="0"
            :max="store.videoFrames.length - 1"
            class="w-full h-1 rounded-full appearance-none bg-hairline-cool accent-primary cursor-pointer"
          />
        </div>
        <span class="text-xs text-ink-mute font-mono">
          {{ store.videoIndex + 1 }} / {{ store.videoFrames.length }}
        </span>
      </div>
    </div>

    <!-- RTSP result -->
    <div v-else-if="store.viewerState === 'rtsp'" class="w-full h-full min-h-0 flex flex-col">
      <div class="min-h-0 flex-1 flex items-center justify-center p-3 sm:p-4">
        <div v-if="store.rtspFrame" class="w-full h-full min-h-0 flex items-center justify-center">
          <div ref="mediaWrapper" class="relative inline-flex max-w-full max-h-full overflow-hidden">
            <img
              ref="mediaImg"
              :src="`data:image/jpeg;base64,${store.rtspFrame}`"
              alt="RTSP stream"
              class="max-w-full max-h-full rounded-lg object-contain"
              @load="drawMasks"
            />
            <canvas
              ref="maskCanvas"
              class="pointer-events-none absolute inset-0 rounded-lg"
              aria-hidden="true"
            />
          </div>
        </div>
        <div v-else class="text-center">
          <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p class="text-ink-mute text-sm">Connecting to stream...</p>
          <p v-if="store.error" class="text-red-500 text-xs mt-1">{{ store.error }}</p>
        </div>
      </div>
      <!-- RTSP status bar -->
      <div class="flex items-center gap-2 px-4 py-2 border-t border-hairline bg-canvas">
        <span
          class="w-2 h-2 rounded-full"
          :class="store.rtspConnected ? 'bg-primary animate-pulse' : 'bg-red-500'"
        />
        <span class="text-xs text-ink-mute">
          {{ store.rtspConnected ? 'Live' : 'Disconnected' }}
        </span>
        <span v-if="store.stats?.inference_ms" class="text-xs text-ink-faint font-mono ml-auto">
          {{ store.stats.inference_ms.toFixed(0) }} ms/frame
        </span>
      </div>
    </div>
  </div>
</template>
