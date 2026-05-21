<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { DatasetOverlayDetection } from '../../shared/api/dataset'

type Box = [number, number, number, number]
type DragAction = 'create' | 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

const props = withDefaults(defineProps<{
  imageSrc: string
  alt?: string
  width?: number | null
  height?: number | null
  detections?: DatasetOverlayDetection[]
  showBbox?: boolean
  showLabels?: boolean
  showMasks?: boolean
  selectedId?: number | null
  draftBox?: Box | null
  editorOpen?: boolean
}>(), {
  alt: '',
  width: null,
  height: null,
  detections: () => [],
  showBbox: true,
  showLabels: false,
  showMasks: false,
  selectedId: null,
  draftBox: null,
  editorOpen: false,
})

const emit = defineEmits<{
  select: [id: number]
  'draft-change': [box: Box]
  'create-draft': [box: Box]
}>()

const stageRef = ref<HTMLElement | null>(null)
const planeRef = ref<HTMLElement | null>(null)
const stageSize = ref({ width: 0, height: 0 })
const hoverPoint = ref<{ x: number; y: number } | null>(null)
let observer: ResizeObserver | null = null
let drag: { action: DragAction; pointerId: number; start: { x: number; y: number }; box: Box } | null = null

const imageWidth = computed(() => Math.max(1, props.width ?? 16))
const imageHeight = computed(() => Math.max(1, props.height ?? 9))
const visibleDetections = computed(() => props.detections ?? [])
const selectedDetection = computed(() => visibleDetections.value.find((d) => d.id === props.selectedId))
const activeBox = computed<Box | null>(() => props.draftBox ?? (selectedDetection.value?.box as Box | undefined) ?? null)

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

const COLORS = ['#3ecf8e', '#24b47e', '#ffffff', '#ffdb13', '#644fc1', '#6b01c2', '#9a9a9a', '#212121']
function detColor(idx: number): string { return COLORS[idx % COLORS.length] }
function clamp(value: number, min: number, max: number): number { return Math.min(Math.max(value, min), max) }


const guideStyle = computed(() => {
  const point = hoverPoint.value
  if (!point || drag) return null
  return {
    '--guide-x': `${(point.x / imageWidth.value) * 100}%`,
    '--guide-y': `${(point.y / imageHeight.value) * 100}%`,
  }
})

const popoverStyle = computed(() => {
  const box = activeBox.value
  if (!box) return {}
  const [x1, y1, x2, y2] = normalizeBox(box)
  const anchorX = x2 > imageWidth.value * 0.72 ? x1 : x2
  const anchorY = y1 < imageHeight.value * 0.28 ? y2 : y1
  return {
    left: `${(anchorX / imageWidth.value) * 100}%`,
    top: `${(anchorY / imageHeight.value) * 100}%`,
    transform: `${x2 > imageWidth.value * 0.72 ? 'translate(calc(-100% - 10px),' : 'translate(10px,'} ${y1 < imageHeight.value * 0.28 ? '10px)' : 'calc(-100% - 10px))'}`,
  }
})

function updateStageSize() {
  const el = stageRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  stageSize.value = { width: rect.width, height: rect.height }
}

function normalizeBox(box: number[] | Box): Box {
  const x1 = clamp(Math.min(box[0] ?? 0, box[2] ?? 0), 0, imageWidth.value)
  const y1 = clamp(Math.min(box[1] ?? 0, box[3] ?? 0), 0, imageHeight.value)
  const x2 = clamp(Math.max(box[0] ?? 0, box[2] ?? 0), 0, imageWidth.value)
  const y2 = clamp(Math.max(box[1] ?? 0, box[3] ?? 0), 0, imageHeight.value)
  return [x1, y1, x2, y2]
}

function normalizedBox(det: DatasetOverlayDetection): Box {
  return normalizeBox(det.box ?? [0, 0, 0, 0])
}

function boxStyle(det: DatasetOverlayDetection, idx: number) {
  const [x1, y1, x2, y2] = normalizedBox(det)
  return {
    left: `${(x1 / imageWidth.value) * 100}%`,
    top: `${(y1 / imageHeight.value) * 100}%`,
    width: `${((x2 - x1) / imageWidth.value) * 100}%`,
    height: `${((y2 - y1) / imageHeight.value) * 100}%`,
    borderColor: det.id === props.selectedId ? '#ffdb13' : detColor(idx),
  }
}

function activeBoxStyle() {
  const box = activeBox.value
  if (!box) return {}
  const [x1, y1, x2, y2] = normalizeBox(box)
  return {
    left: `${(x1 / imageWidth.value) * 100}%`,
    top: `${(y1 / imageHeight.value) * 100}%`,
    width: `${((x2 - x1) / imageWidth.value) * 100}%`,
    height: `${((y2 - y1) / imageHeight.value) * 100}%`,
  }
}

function labelStyle(det: DatasetOverlayDetection) {
  const [, y1] = normalizedBox(det)
  return {
    top: y1 < 22 ? '0px' : '0px',
    transform: y1 < 22 ? 'translateY(0)' : 'translateY(calc(-100% - 2px))',
  }
}

function maskPoints(det: DatasetOverlayDetection) {
  return (det.mask ?? [])
    .map(([x, y]) => `${clamp(x, 0, imageWidth.value)},${clamp(y, 0, imageHeight.value)}`)
    .join(' ')
}

function pointFromEvent(e: PointerEvent) {
  const el = planeRef.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  return {
    x: clamp(((e.clientX - rect.left) / rect.width) * imageWidth.value, 0, imageWidth.value),
    y: clamp(((e.clientY - rect.top) / rect.height) * imageHeight.value, 0, imageHeight.value),
  }
}

function emitBox(box: Box) {
  const next = normalizeBox(box)
  if ((next[2] - next[0]) < 2 || (next[3] - next[1]) < 2) return
  emit('draft-change', next)
}

function onPlanePointerDown(e: PointerEvent) {
  const point = pointFromEvent(e)
  if (!point) return
  drag = { action: 'create', pointerId: e.pointerId, start: point, box: [point.x, point.y, point.x, point.y] }
  planeRef.value?.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onBoxPointerDown(e: PointerEvent, det: DatasetOverlayDetection) {
  if (det.id == null) return
  emit('select', det.id)
  const point = pointFromEvent(e)
  if (!point) return
  drag = { action: 'move', pointerId: e.pointerId, start: point, box: normalizeBox((props.draftBox ?? det.box) as Box) }
  planeRef.value?.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onHandlePointerDown(e: PointerEvent, action: DragAction) {
  const point = pointFromEvent(e)
  const box = activeBox.value
  if (!point || !box) return
  drag = { action, pointerId: e.pointerId, start: point, box: normalizeBox(box) }
  planeRef.value?.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function applyDrag(point: { x: number; y: number }) {
  if (!drag) return
  const dx = point.x - drag.start.x
  const dy = point.y - drag.start.y
  let [x1, y1, x2, y2] = drag.box

  if (drag.action === 'create') {
    emit('draft-change', [drag.start.x, drag.start.y, point.x, point.y])
    return
  }
  if (drag.action === 'move') {
    const width = x2 - x1
    const height = y2 - y1
    x1 = clamp(x1 + dx, 0, imageWidth.value - width)
    y1 = clamp(y1 + dy, 0, imageHeight.value - height)
    x2 = x1 + width
    y2 = y1 + height
    emitBox([x1, y1, x2, y2])
    return
  }

  if (drag.action.includes('w')) x1 = clamp(x1 + dx, 0, x2 - 2)
  if (drag.action.includes('e')) x2 = clamp(x2 + dx, x1 + 2, imageWidth.value)
  if (drag.action.includes('n')) y1 = clamp(y1 + dy, 0, y2 - 2)
  if (drag.action.includes('s')) y2 = clamp(y2 + dy, y1 + 2, imageHeight.value)
  emitBox([x1, y1, x2, y2])
}

function onPointerMove(e: PointerEvent) {
  const point = pointFromEvent(e)
  if (!point) return
  hoverPoint.value = point
  if (!drag || drag.pointerId !== e.pointerId) return
  applyDrag(point)
}

function onPointerLeave() {
  hoverPoint.value = null
}

function onPointerUp(e: PointerEvent) {
  if (!drag || drag.pointerId !== e.pointerId) return
  const point = pointFromEvent(e)
  if (point) applyDrag(point)
  const box = activeBox.value
  if (drag.action === 'create' && box && (box[2] - box[0]) >= 2 && (box[3] - box[1]) >= 2) {
    emit('create-draft', normalizeBox(box))
  }
  planeRef.value?.releasePointerCapture(e.pointerId)
  drag = null
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
    <div
      ref="planeRef"
      class="dataset-media-plane dataset-editor-plane"
      :style="planeStyle"
      @pointerdown="onPlanePointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerLeave"
    >
      <img class="dataset-media-image" :src="imageSrc" :alt="alt" loading="lazy" @load="updateStageSize" />

      <div v-if="guideStyle" class="dataset-editor-guides" :style="guideStyle" />

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
          :fill="detColor(idx)"
          fill-opacity="0.22"
          :stroke="detColor(idx)"
          stroke-opacity="0.55"
          stroke-width="2"
        />
      </svg>

      <template v-if="showBbox">
        <button
          v-for="(det, idx) in visibleDetections"
          :key="`box-${det.id ?? idx}`"
          type="button"
          class="dataset-media-box dataset-editor-box"
          :class="{ 'is-rejected': det.accepted === false, 'is-selected': det.id === selectedId }"
          :style="boxStyle(det, idx)"
          @pointerdown.stop="onBoxPointerDown($event, det)"
        >
          <span
            v-if="showLabels"
            class="dataset-media-label dataset-editor-label"
            :style="labelStyle(det)"
          >
            {{ det.label }} {{ det.manual ? 'Manual' : `${(det.confidence * 100).toFixed(0)}%` }}
          </span>
        </button>
      </template>

      <div v-if="activeBox" class="dataset-editor-active-box" :style="activeBoxStyle()">
        <button type="button" class="dataset-editor-handle is-nw" @pointerdown.stop="onHandlePointerDown($event, 'nw')" />
        <button type="button" class="dataset-editor-handle is-ne" @pointerdown.stop="onHandlePointerDown($event, 'ne')" />
        <button type="button" class="dataset-editor-handle is-sw" @pointerdown.stop="onHandlePointerDown($event, 'sw')" />
        <button type="button" class="dataset-editor-handle is-se" @pointerdown.stop="onHandlePointerDown($event, 'se')" />
        <button type="button" class="dataset-editor-handle is-n" @pointerdown.stop="onHandlePointerDown($event, 'n')" />
        <button type="button" class="dataset-editor-handle is-s" @pointerdown.stop="onHandlePointerDown($event, 's')" />
        <button type="button" class="dataset-editor-handle is-w" @pointerdown.stop="onHandlePointerDown($event, 'w')" />
        <button type="button" class="dataset-editor-handle is-e" @pointerdown.stop="onHandlePointerDown($event, 'e')" />
      </div>

      <div
        v-if="activeBox && editorOpen && $slots.editor"
        class="dataset-editor-popover"
        :style="popoverStyle"
        @pointerdown.stop
        @pointermove.stop
        @pointerup.stop
        @click.stop
      >
        <slot name="editor" />
      </div>
    </div>
  </div>
</template>
