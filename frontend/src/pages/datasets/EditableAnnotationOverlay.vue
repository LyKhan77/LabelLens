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
  classColors?: Record<string, string>
  activeTool?: 'select' | 'bbox' | 'pan'
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
  classColors: () => ({}),
  activeTool: 'bbox',
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
const zoom = ref(1)
const panOffset = ref({ x: 0, y: 0 })
const isStageActive = ref(false)
const spacePressed = ref(false)
const isDraggingAnnotation = ref(false)
let observer: ResizeObserver | null = null
let drag: { action: DragAction; pointerId: number; start: { x: number; y: number }; box: Box } | null = null
let panDrag: { pointerId: number; startClient: { x: number; y: number }; startPan: { x: number; y: number } } | null = null

const imageWidth = computed(() => Math.max(1, props.width ?? 16))
const imageHeight = computed(() => Math.max(1, props.height ?? 9))
const visibleDetections = computed(() => props.detections ?? [])
const selectedDetection = computed(() => visibleDetections.value.find((d) => d.id === props.selectedId))
const activeBox = computed<Box | null>(() => props.draftBox ?? (selectedDetection.value?.box as Box | undefined) ?? null)
const zoomPercent = computed(() => `${Math.round(zoom.value * 100)}%`)
const canPan = computed(() => zoom.value > 1.01)

const planeStyle = computed(() => {
  const stageWidth = stageSize.value.width
  const stageHeight = stageSize.value.height
  const transform = `translate(${panOffset.value.x}px, ${panOffset.value.y}px) scale(${zoom.value})`
  if (!stageWidth || !stageHeight) {
    return { width: '100%', height: '100%', left: '0px', top: '0px', transform }
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
    transform,
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
function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement
}

const guideStyle = computed(() => {
  if (props.activeTool !== 'bbox') return null
  const point = hoverPoint.value
  if (!point || drag || panDrag) return null
  return {
    '--guide-x': `${(point.x / imageWidth.value) * 100}%`,
    '--guide-y': `${(point.y / imageHeight.value) * 100}%`,
  }
})

const popoverStyle = computed(() => {
  const box = activeBox.value
  const plane = planeRef.value
  if (!box || !plane) return {}

  const [x1, y1, x2, y2] = normalizeBox(box)
  const planeRect = plane.getBoundingClientRect()
  const renderedBox = {
    left: planeRect.left + (x1 / imageWidth.value) * planeRect.width,
    top: planeRect.top + (y1 / imageHeight.value) * planeRect.height,
    right: planeRect.left + (x2 / imageWidth.value) * planeRect.width,
    bottom: planeRect.top + (y2 / imageHeight.value) * planeRect.height,
  }

  const margin = 10
  const viewportWidth = window.innerWidth || stageSize.value.width
  const viewportHeight = window.innerHeight || stageSize.value.height
  const width = Math.min(280, Math.max(220, viewportWidth - margin * 2))
  const estimatedHeight = 190
  let left = renderedBox.right + margin
  if (left + width > viewportWidth - margin) left = renderedBox.left - width - margin
  left = clamp(left, margin, Math.max(margin, viewportWidth - width - margin))

  let top = renderedBox.top
  if (top + estimatedHeight > viewportHeight - margin) top = renderedBox.top - estimatedHeight - margin
  if (top < margin) top = viewportHeight - estimatedHeight - margin
  top = clamp(top, margin, Math.max(margin, viewportHeight - estimatedHeight - margin))

  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
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

function boxStyle(det: DatasetOverlayDetection) {
  const [x1, y1, x2, y2] = normalizedBox(det)
  const color = det.id === props.selectedId ? '#ffdb13' : classColor(det.label)
  return {
    left: `${(x1 / imageWidth.value) * 100}%`,
    top: `${(y1 / imageHeight.value) * 100}%`,
    width: `${((x2 - x1) / imageWidth.value) * 100}%`,
    height: `${((y2 - y1) / imageHeight.value) * 100}%`,
    borderColor: color,
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

function setZoom(nextZoom: number, origin?: { x: number; y: number }) {
  const previous = zoom.value
  const next = clamp(Math.round(nextZoom * 100) / 100, 1, 6)
  if (Math.abs(previous - next) < 0.01) return
  if (origin && stageRef.value) {
    const rect = stageRef.value.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    panOffset.value = {
      x: panOffset.value.x + (1 - next / previous) * (origin.x - centerX - panOffset.value.x),
      y: panOffset.value.y + (1 - next / previous) * (origin.y - centerY - panOffset.value.y),
    }
  }
  zoom.value = next
  if (next === 1) panOffset.value = { x: 0, y: 0 }
}

function zoomBy(delta: number, origin?: { x: number; y: number }) {
  setZoom(zoom.value + delta, origin)
}

function resetZoom() {
  zoom.value = 1
  panOffset.value = { x: 0, y: 0 }
}

function onWheel(e: WheelEvent) {
  if (!isStageActive.value) return
  zoomBy(e.deltaY < 0 ? 0.2 : -0.2, { x: e.clientX, y: e.clientY })
}

function onPlanePointerDown(e: PointerEvent) {
  if ((props.activeTool === 'pan' || spacePressed.value) && canPan.value) {
    panDrag = {
      pointerId: e.pointerId,
      startClient: { x: e.clientX, y: e.clientY },
      startPan: { ...panOffset.value },
    }
    planeRef.value?.setPointerCapture(e.pointerId)
    e.preventDefault()
    return
  }
  if (props.activeTool === 'select') return
  if (props.activeTool === 'bbox') {
    const point = pointFromEvent(e)
    if (!point) return
    drag = { action: 'create', pointerId: e.pointerId, start: point, box: [point.x, point.y, point.x, point.y] }
    isDraggingAnnotation.value = true
    planeRef.value?.setPointerCapture(e.pointerId)
    e.preventDefault()
  }
}

function onBoxPointerDown(e: PointerEvent, det: DatasetOverlayDetection) {
  if (props.activeTool === 'pan' || (spacePressed.value && canPan.value)) {
    onPlanePointerDown(e)
    return
  }
  if (props.activeTool !== 'select' && props.activeTool !== 'bbox') return
  if (det.id == null) return
  emit('select', det.id)
  const point = pointFromEvent(e)
  if (!point) return
  drag = { action: 'move', pointerId: e.pointerId, start: point, box: normalizeBox((props.draftBox ?? det.box) as Box) }
  isDraggingAnnotation.value = true
  planeRef.value?.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onHandlePointerDown(e: PointerEvent, action: DragAction) {
  const point = pointFromEvent(e)
  const box = activeBox.value
  if (!point || !box) return
  drag = { action, pointerId: e.pointerId, start: point, box: normalizeBox(box) }
  isDraggingAnnotation.value = true
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
  if (panDrag && panDrag.pointerId === e.pointerId) {
    panOffset.value = {
      x: panDrag.startPan.x + e.clientX - panDrag.startClient.x,
      y: panDrag.startPan.y + e.clientY - panDrag.startClient.y,
    }
    e.preventDefault()
    return
  }
  const point = pointFromEvent(e)
  if (!point) return
  hoverPoint.value = point
  if (!drag || drag.pointerId !== e.pointerId) {
    isDraggingAnnotation.value = false
    return
  }
  applyDrag(point)
}

function onPointerLeave() {
  hoverPoint.value = null
  isStageActive.value = false
  spacePressed.value = false
}

function onPointerUp(e: PointerEvent) {
  if (panDrag && panDrag.pointerId === e.pointerId) {
    planeRef.value?.releasePointerCapture(e.pointerId)
    panDrag = null
    return
  }
  if (!drag || drag.pointerId !== e.pointerId) return
  const point = pointFromEvent(e)
  if (point) applyDrag(point)
  const box = activeBox.value
  if (drag.action === 'create' && box && (box[2] - box[0]) >= 2 && (box[3] - box[1]) >= 2) {
    emit('create-draft', normalizeBox(box))
  }
  planeRef.value?.releasePointerCapture(e.pointerId)
  drag = null
  isDraggingAnnotation.value = false
}

function handleKeydown(e: KeyboardEvent) {
  if (!isStageActive.value || isEditableTarget(e.target)) return
  if (e.key === ' ' && canPan.value) {
    spacePressed.value = true
    e.preventDefault()
  }
  if (e.key === '+' || e.key === '=') {
    zoomBy(0.25)
    e.preventDefault()
  }
  if (e.key === '-' || e.key === '_') {
    zoomBy(-0.25)
    e.preventDefault()
  }
  if (e.key === '0') {
    resetZoom()
    e.preventDefault()
  }
}

function handleKeyup(e: KeyboardEvent) {
  if (e.key === ' ') spacePressed.value = false
}

onMounted(() => {
  nextTick(updateStageSize)
  if (stageRef.value) {
    observer = new ResizeObserver(updateStageSize)
    observer.observe(stageRef.value)
  }
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('keyup', handleKeyup)
})

onUnmounted(() => {
  observer?.disconnect()
  observer = null
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('keyup', handleKeyup)
})

watch(() => [props.width, props.height, props.imageSrc], () => {
  resetZoom()
  nextTick(updateStageSize)
})
</script>

<template>
  <div
    ref="stageRef"
    class="dataset-media-stage"
    :class="{ 'is-zoomed': canPan, 'is-panning': Boolean(panDrag), 'is-space-panning': spacePressed && canPan }"
    tabindex="0"
    @mouseenter="isStageActive = true"
    @mouseleave="onPointerLeave"
    @focusin="isStageActive = true"
    @focusout="isStageActive = false"
    @wheel.prevent="onWheel"
  >
    <div
      ref="planeRef"
      class="dataset-media-plane dataset-editor-plane"
      :class="`tool-${props.activeTool}`"
      :style="planeStyle"
      @pointerdown="onPlanePointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="hoverPoint = null"
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
          :fill="classColor(det.label)"
          fill-opacity="0.22"
          :stroke="classColor(det.label)"
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
          :style="boxStyle(det)"
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

      <div v-if="activeBox" class="dataset-editor-active-box" :class="{ 'is-dragging': isDraggingAnnotation }" :style="activeBoxStyle()">
        <template v-if="!isDraggingAnnotation">
          <button type="button" class="dataset-editor-handle is-nw" @pointerdown.stop="onHandlePointerDown($event, 'nw')" />
          <button type="button" class="dataset-editor-handle is-ne" @pointerdown.stop="onHandlePointerDown($event, 'ne')" />
          <button type="button" class="dataset-editor-handle is-sw" @pointerdown.stop="onHandlePointerDown($event, 'sw')" />
          <button type="button" class="dataset-editor-handle is-se" @pointerdown.stop="onHandlePointerDown($event, 'se')" />
          <button type="button" class="dataset-editor-handle is-n" @pointerdown.stop="onHandlePointerDown($event, 'n')" />
          <button type="button" class="dataset-editor-handle is-s" @pointerdown.stop="onHandlePointerDown($event, 's')" />
          <button type="button" class="dataset-editor-handle is-w" @pointerdown.stop="onHandlePointerDown($event, 'w')" />
          <button type="button" class="dataset-editor-handle is-e" @pointerdown.stop="onHandlePointerDown($event, 'e')" />
        </template>
      </div>
    </div>

    <div class="dataset-zoom-toolbar" @pointerdown.stop @click.stop>
      <button type="button" aria-label="Zoom out" @click="zoomBy(-0.25)">-</button>
      <span>{{ zoomPercent }}</span>
      <button type="button" aria-label="Zoom in" @click="zoomBy(0.25)">+</button>
      <button type="button" aria-label="Reset zoom" @click="resetZoom">Reset</button>
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
</template>
