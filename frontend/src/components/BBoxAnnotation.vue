<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import type { BBoxAnnotation } from '../types'

const props = defineProps<{
  imageSrc: string
  annotations: BBoxAnnotation[]
}>()

const emit = defineEmits<{
  add: [annotation: BBoxAnnotation]
  remove: [index: number]
}>()

const canvas = ref<HTMLCanvasElement | null>(null)
const container = ref<HTMLDivElement | null>(null)

const isDrawing = ref(false)
const drawStart = ref({ x: 0, y: 0 })
const drawCurrent = ref({ x: 0, y: 0 })
const labelInput = ref('')
const showLabelPopup = ref(false)
const pendingBbox = ref<[number, number, number, number] | null>(null)

let imageEl: HTMLImageElement | null = null
let scaleX = 1
let scaleY = 1

const COLORS = [
  '#3ecf8e', '#24b47e', '#6b01c2', '#644fc1', '#ffdb13',
  '#dc2626', '#2563eb', '#ea580c',
]

function loadImage() {
  if (!canvas.value || !props.imageSrc) return

  imageEl = new Image()
  imageEl.onload = () => {
    renderCanvas()
  }
  imageEl.src = props.imageSrc
}

function renderCanvas() {
  const cvs = canvas.value
  const img = imageEl
  if (!cvs || !img || !img.complete) return

  const maxW = container.value?.clientWidth ?? 340
  const scale = maxW / img.naturalWidth
  const displayW = Math.floor(img.naturalWidth * scale)
  const displayH = Math.floor(img.naturalHeight * scale)

  cvs.width = displayW
  cvs.height = displayH

  scaleX = img.naturalWidth / displayW
  scaleY = img.naturalHeight / displayH

  const ctx = cvs.getContext('2d')
  if (!ctx) return

  ctx.drawImage(img, 0, 0, displayW, displayH)

  // Draw existing annotations
  props.annotations.forEach((ann, i) => {
    const [x1, y1, x2, y2] = ann.bbox
    const color = COLORS[i % COLORS.length]
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(x1 / scaleX, y1 / scaleY, (x2 - x1) / scaleX, (y2 - y1) / scaleY)

    ctx.fillStyle = color
    const labelH = 20
    const labelW = ctx.measureText(ann.label).width + 8
    ctx.fillRect(x1 / scaleX, y1 / scaleY - labelH, labelW, labelH)
    ctx.fillStyle = '#ffffff'
    ctx.font = '12px Inter, sans-serif'
    ctx.fillText(ann.label, x1 / scaleX + 4, y1 / scaleY - 6)
  })

  // Draw rubber-band rect while drawing
  if (isDrawing.value) {
    const ctx2 = cvs.getContext('2d')
    if (!ctx2) return
    ctx2.strokeStyle = '#3ecf8e'
    ctx2.lineWidth = 2
    ctx2.setLineDash([4, 4])
    const x = Math.min(drawStart.value.x, drawCurrent.value.x)
    const y = Math.min(drawStart.value.y, drawCurrent.value.y)
    const w = Math.abs(drawCurrent.value.x - drawStart.value.x)
    const h = Math.abs(drawCurrent.value.y - drawStart.value.y)
    ctx2.strokeRect(x, y, w, h)
    ctx2.setLineDash([])
  }
}

function getCanvasPos(e: MouseEvent) {
  const cvs = canvas.value
  if (!cvs) return { x: 0, y: 0 }
  const rect = cvs.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function onMouseDown(e: MouseEvent) {
  if (showLabelPopup.value) return
  const pos = getCanvasPos(e)
  isDrawing.value = true
  drawStart.value = pos
  drawCurrent.value = pos
}

function onMouseMove(e: MouseEvent) {
  if (!isDrawing.value) return
  drawCurrent.value = getCanvasPos(e)
  renderCanvas()
}

function onMouseUp(e: MouseEvent) {
  if (!isDrawing.value) return
  isDrawing.value = false
  const pos = getCanvasPos(e)

  const x1 = Math.min(drawStart.value.x, pos.x) * scaleX
  const y1 = Math.min(drawStart.value.y, pos.y) * scaleY
  const x2 = Math.max(drawStart.value.x, pos.x) * scaleX
  const y2 = Math.max(drawStart.value.y, pos.y) * scaleY

  // Minimum size check
  if (x2 - x1 < 10 || y2 - y1 < 10) {
    renderCanvas()
    return
  }

  pendingBbox.value = [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)]
  showLabelPopup.value = true
  labelInput.value = ''
}

function confirmLabel() {
  if (!pendingBbox.value || !labelInput.value.trim()) return

  emit('add', {
    bbox: pendingBbox.value,
    label: labelInput.value.trim(),
  })

  showLabelPopup.value = false
  pendingBbox.value = null
  labelInput.value = ''
  renderCanvas()
}

function cancelLabel() {
  showLabelPopup.value = false
  pendingBbox.value = null
  renderCanvas()
}

watch(() => props.imageSrc, loadImage)
watch(() => props.annotations, () => renderCanvas(), { deep: true })

onMounted(loadImage)
onUnmounted(() => { imageEl = null })
</script>

<template>
  <div ref="container" class="relative">
    <canvas
      ref="canvas"
      class="w-full rounded-(--radius-md) border border-hairline cursor-crosshair"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
    />

    <!-- Label popup -->
    <div
      v-if="showLabelPopup"
      class="absolute bottom-2 left-2 right-2 bg-canvas rounded-(--radius-md) border border-hairline shadow-lg p-3"
    >
      <p class="text-xs text-ink-mute mb-1.5">Label for this region:</p>
      <div class="flex gap-1.5">
        <input
          v-model="labelInput"
          type="text"
          placeholder="e.g. product, defect"
          class="flex-1 px-2 py-1 text-sm rounded-(--radius-xs) border border-hairline focus:outline-none focus:border-primary"
          autofocus
          @keydown.enter="confirmLabel"
          @keydown.escape="cancelLabel"
        />
        <button
          class="px-3 py-1 text-sm font-medium rounded-(--radius-xs) bg-primary text-on-primary hover:bg-primary-deep transition-colors"
          @click="confirmLabel"
        >
          Add
        </button>
        <button
          class="px-2 py-1 text-sm rounded-(--radius-xs) border border-hairline text-ink-mute hover:text-ink transition-colors"
          @click="cancelLabel"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>
