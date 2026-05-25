<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { DatasetOverlayDetection } from '../../shared/api/dataset'

const props = withDefaults(defineProps<{
  imageSrc: string
  alt?: string
  width?: number | null
  height?: number | null
  detections?: DatasetOverlayDetection[]
  showBbox?: boolean
  showLabels?: boolean
  showMasks?: boolean
  classColors?: Record<string, string>
}>(), {
  alt: '',
  width: null,
  height: null,
  detections: () => [],
  showBbox: true,
  showLabels: false,
  showMasks: false,
  classColors: () => ({}),
})

const stageRef = ref<HTMLElement | null>(null)
const stageSize = ref({ width: 0, height: 0 })
let observer: ResizeObserver | null = null

const imageWidth = computed(() => Math.max(1, props.width ?? 16))
const imageHeight = computed(() => Math.max(1, props.height ?? 9))
const visibleDetections = computed(() => props.detections ?? [])

const planeStyle = computed(() => {
  const stageWidth = stageSize.value.width
  const stageHeight = stageSize.value.height
  if (!stageWidth || !stageHeight) {
    return { width: '100%', height: '100%', left: '0px', top: '0px' }
  }

  const imageAspect = imageWidth.value / imageHeight.value
  const stageAspect = stageWidth / stageHeight
  let width = stageWidth
  let height = stageHeight

  if (stageAspect > imageAspect) {
    height = stageHeight
    width = height * imageAspect
  } else {
    width = stageWidth
    height = width / imageAspect
  }

  return {
    width: `${width}px`,
    height: `${height}px`,
    left: `${(stageWidth - width) / 2}px`,
    top: `${(stageHeight - height) / 2}px`,
  }
})

const COLORS = ['#3ECF8E', '#2563EB', '#F59E0B', '#EF4444', '#8B5CF6', '#14B8A6', '#EC4899', '#84CC16']
function classColor(label: string): string {
  if (props.classColors[label]) return props.classColors[label]
  let hash = 0
  for (let i = 0; i < label.length; i++) hash = ((hash << 5) - hash + label.charCodeAt(i)) | 0
  return COLORS[Math.abs(hash) % COLORS.length]
}
function clamp(value: number, min: number, max: number): number { return Math.min(Math.max(value, min), max) }

function updateStageSize() {
  const el = stageRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  stageSize.value = { width: rect.width, height: rect.height }
}

function normalizedBox(det: DatasetOverlayDetection) {
  const box = det.box ?? []
  const x1 = clamp(Math.min(box[0] ?? 0, box[2] ?? 0), 0, imageWidth.value)
  const y1 = clamp(Math.min(box[1] ?? 0, box[3] ?? 0), 0, imageHeight.value)
  const x2 = clamp(Math.max(box[0] ?? 0, box[2] ?? 0), 0, imageWidth.value)
  const y2 = clamp(Math.max(box[1] ?? 0, box[3] ?? 0), 0, imageHeight.value)
  return { x1, y1, x2, y2 }
}

function boxStyle(det: DatasetOverlayDetection) {
  const { x1, y1, x2, y2 } = normalizedBox(det)
  return {
    left: `${(x1 / imageWidth.value) * 100}%`,
    top: `${(y1 / imageHeight.value) * 100}%`,
    width: `${((x2 - x1) / imageWidth.value) * 100}%`,
    height: `${((y2 - y1) / imageHeight.value) * 100}%`,
    borderColor: classColor(det.label),
  }
}

function labelStyle(det: DatasetOverlayDetection) {
  const { y1 } = normalizedBox(det)
  return {
    backgroundColor: classColor(det.label),
    top: y1 < 22 ? '0px' : '0px',
    transform: y1 < 22 ? 'translateY(0)' : 'translateY(calc(-100% - 2px))',
  }
}

function maskPoints(det: DatasetOverlayDetection) {
  return (det.mask ?? [])
    .map(([x, y]) => `${clamp(x, 0, imageWidth.value)},${clamp(y, 0, imageHeight.value)}`)
    .join(' ')
}

onMounted(() => {
  nextTick(updateStageSize)
  if (stageRef.value) {
    observer = new ResizeObserver(updateStageSize)
    observer.observe(stageRef.value)
  }
})

onUnmounted(() => {
  observer?.disconnect()
  observer = null
})

watch(() => [props.width, props.height, props.imageSrc], () => nextTick(updateStageSize))
</script>

<template>
  <div ref="stageRef" class="dataset-media-stage">
    <div class="dataset-media-plane" :style="planeStyle">
      <img class="dataset-media-image" :src="imageSrc" :alt="alt" loading="lazy" @load="updateStageSize" />

      <svg
        v-if="showMasks"
        class="dataset-media-mask-layer"
        :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
        preserveAspectRatio="none"
      >
        <polygon
          v-for="(det, idx) in visibleDetections.filter((d) => d.mask && d.mask.length)"
          :key="`mask-${det.id ?? idx}`"
          :points="maskPoints(det)"
          :fill="classColor(det.label)"
          fill-opacity="0.22"
          :stroke="classColor(det.label)"
          stroke-opacity="0.55"
          stroke-width="2"
        />
      </svg>

      <template v-if="showBbox">
        <div
          v-for="(det, idx) in visibleDetections"
          :key="`box-${det.id ?? idx}`"
          class="dataset-media-box"
          :class="{ 'is-rejected': det.accepted === false }"
          :style="boxStyle(det)"
        >
          <span
            v-if="showLabels"
            class="dataset-media-label"
            :style="labelStyle(det)"
          >
            {{ det.label }} {{ (det.confidence * 100).toFixed(0) }}%
          </span>
        </div>
      </template>
    </div>
  </div>
</template>
