<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import type { PoseAnnotation, PoseKeypointAnnotation, PosePayload } from '../../shared/api/dataset'
import type { PoseTemplate } from '../../shared/types'
import type { PoseTool } from './PoseToolbar.vue'

const props = withDefaults(defineProps<{
  imageSrc: string
  width: number
  height: number
  poses: PoseAnnotation[]
  template: PoseTemplate
  activeTool?: PoseTool
  editingPoseId?: number | null
  saving?: boolean
}>(), {
  activeTool: 'move',
  editingPoseId: null,
})

const emit = defineEmits<{
  save: [payload: PosePayload]
  update: [payload: PosePayload & { id: number }]
  delete: [payload: { id: number }]
  'update:editingPoseId': [id: number | null]
}>()

// Anatomical default layout, normalized 0..1 within the bbox (x right, y down).
const KEYPOINT_LAYOUT: Record<string, [number, number]> = {
  top_left: [0, 0], top_right: [1, 0], bottom_right: [1, 1], bottom_left: [0, 1],
  nose: [0.5, 0.1], left_eye: [0.43, 0.07], right_eye: [0.57, 0.07],
  left_ear: [0.37, 0.09], right_ear: [0.63, 0.09],
  left_shoulder: [0.35, 0.25], right_shoulder: [0.65, 0.25],
  left_elbow: [0.28, 0.43], right_elbow: [0.72, 0.43],
  left_wrist: [0.25, 0.6], right_wrist: [0.75, 0.6],
  left_hip: [0.42, 0.58], right_hip: [0.58, 0.58],
  left_knee: [0.4, 0.78], right_knee: [0.6, 0.78],
  left_ankle: [0.39, 0.97], right_ankle: [0.61, 0.97],
}

type Editor = { sourceId: number | null; label: string; box: number[]; keypoints: PoseKeypointAnnotation[] }
const editor = ref<Editor | null>(null)
const selectedKeypoint = ref<string | null>(null)
const hoverKeypoint = ref<string | null>(null)
const draggingKeypoint = ref<string | null>(null)
const draggingHandle = ref<string | null>(null)

// Stage/plane zoom-pan model (mirrors EditableAnnotationOverlay so cursor math stays exact).
const stageRef = ref<HTMLElement | null>(null)
const planeRef = ref<HTMLElement | null>(null)
const stageSize = ref({ width: 0, height: 0 })
const zoom = ref(1)
const panOffset = reactive({ x: 0, y: 0 })
let panDrag: { pointerId: number; startClient: { x: number; y: number }; startPan: { x: number; y: number } } | null = null
let observer: ResizeObserver | null = null

const imageWidth = computed(() => Math.max(1, props.width || 16))
const imageHeight = computed(() => Math.max(1, props.height || 9))
const skeletonEdges = computed(() => props.template.skeleton ?? [])
const editing = computed(() => editor.value !== null)
const canPan = computed(() => zoom.value > 1.01)
const zoomPercent = computed(() => `${Math.round(zoom.value * 100)}%`)

// Letterbox-fit rendered size of the plane inside the stage (pre-transform).
const rendered = computed(() => {
  const sw = stageSize.value.width
  const sh = stageSize.value.height
  if (!sw || !sh) return { width: 0, height: 0, left: 0, top: 0 }
  const imageAspect = imageWidth.value / imageHeight.value
  const stageAspect = sw / sh
  let width = sw
  let height = sh
  if (stageAspect > imageAspect) {
    height = sh
    width = height * imageAspect
  } else {
    width = sw
    height = width / imageAspect
  }
  return { width, height, left: (sw - width) / 2, top: (sh - height) / 2 }
})

const planeStyle = computed(() => {
  const r = rendered.value
  const transform = `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom.value})`
  if (!r.width || !r.height) return { width: '100%', height: '100%', left: '0px', top: '0px', transform }
  return { width: `${r.width}px`, height: `${r.height}px`, left: `${r.left}px`, top: `${r.top}px`, transform }
})

// image-px per on-screen-px, accounting for zoom — keeps node/handle sizes constant on screen.
const unit = computed(() => {
  const rw = rendered.value.width
  if (!rw) return 1
  return imageWidth.value / (rw * zoom.value)
})
const nodeR = computed(() => 5 * unit.value)
const selR = computed(() => 8 * unit.value)
const ringR = computed(() => 11 * unit.value)
const hitR = computed(() => 16 * unit.value)
const strokeW = computed(() => 2 * unit.value)
const skeletonW = computed(() => 2.5 * unit.value)
const handleHalf = computed(() => 6 * unit.value)
const labelFont = computed(() => 12 * unit.value)
const visibilityOptions: PoseKeypointAnnotation['visibility'][] = ['visible', 'occluded', 'missing']

function clamp(v: number, lo: number, hi: number) {
  return Math.min(Math.max(v, lo), hi)
}

function keypointMap(keypoints: PoseKeypointAnnotation[]) {
  return new Map(keypoints.map((kp) => [kp.name, kp]))
}

function visibilityColor(v: PoseKeypointAnnotation['visibility']) {
  return v === 'missing' ? '#9CA3AF' : v === 'occluded' ? '#F59E0B' : '#2563EB'
}

function layoutKeypoints(box: number[]): PoseKeypointAnnotation[] {
  const w = box[2] - box[0]
  const h = box[3] - box[1]
  return props.template.keypoint_names.map((name, index) => {
    const layout = KEYPOINT_LAYOUT[name]
    if (layout) {
      return { name, x: box[0] + layout[0] * w, y: box[1] + layout[1] * h, visibility: 'visible' }
    }
    const angle = (Math.PI * 2 * index) / Math.max(1, props.template.keypoint_names.length)
    const cx = box[0] + w / 2
    const cy = box[1] + h / 2
    return { name, x: cx + Math.cos(angle) * w * 0.35, y: cy + Math.sin(angle) * h * 0.35, visibility: 'visible' }
  })
}

function createDraft() {
  const w = imageWidth.value
  const h = imageHeight.value
  const box = [w * 0.25, h * 0.2, w * 0.75, h * 0.8]
  editor.value = { sourceId: null, label: 'pose', box, keypoints: layoutKeypoints(box) }
  selectedKeypoint.value = null
}

function editExisting(pose: PoseAnnotation) {
  editor.value = {
    sourceId: pose.id,
    label: pose.label,
    box: [...pose.box],
    keypoints: pose.keypoints.map((kp) => ({ ...kp })),
  }
  selectedKeypoint.value = null
  emit('update:editingPoseId', pose.id)
}

watch(() => props.editingPoseId, (id) => {
  if (id === null || id === undefined) return
  const pose = props.poses.find((p) => p.id === id)
  if (pose && editor.value?.sourceId !== id) editExisting(pose)
})

// Screen → image-space coords from the post-transform plane rect (always on-point).
function pointFromEvent(event: PointerEvent) {
  const el = planeRef.value
  if (!el) return { x: 0, y: 0 }
  const rect = el.getBoundingClientRect()
  return {
    x: ((event.clientX - rect.left) / rect.width) * imageWidth.value,
    y: ((event.clientY - rect.top) / rect.height) * imageHeight.value,
  }
}

function startKeypointDrag(name: string, event: PointerEvent) {
  if (props.activeTool === 'visibility') { cycleVisibility(name); return }
  if (props.activeTool !== 'move') return
  selectedKeypoint.value = name
  draggingKeypoint.value = name
  planeRef.value?.setPointerCapture?.(event.pointerId)
}

function startHandleDrag(handle: string, event: PointerEvent) {
  if (props.activeTool !== 'bbox') return
  draggingHandle.value = handle
  planeRef.value?.setPointerCapture?.(event.pointerId)
}

function onPlanePointerDown(event: PointerEvent) {
  if (props.activeTool === 'pan') {
    panDrag = { pointerId: event.pointerId, startClient: { x: event.clientX, y: event.clientY }, startPan: { ...panOffset } }
    planeRef.value?.setPointerCapture?.(event.pointerId)
    event.preventDefault()
  }
}

function onPointerMove(event: PointerEvent) {
  if (panDrag && panDrag.pointerId === event.pointerId) {
    panOffset.x = panDrag.startPan.x + event.clientX - panDrag.startClient.x
    panOffset.y = panDrag.startPan.y + event.clientY - panDrag.startClient.y
    event.preventDefault()
    return
  }
  if (!editor.value) return
  if (draggingKeypoint.value) {
    const pos = pointFromEvent(event)
    const box = editor.value.box
    const x = clamp(pos.x, box[0], box[2])
    const y = clamp(pos.y, box[1], box[3])
    editor.value.keypoints = editor.value.keypoints.map((kp) =>
      kp.name === draggingKeypoint.value ? { ...kp, x, y } : kp,
    )
  } else if (draggingHandle.value) {
    resizeBox(event)
  }
}

function resizeBox(event: PointerEvent) {
  if (!editor.value) return
  const pos = pointFromEvent(event)
  const previousBox = [...editor.value.box]
  const box = [...previousBox]
  const x = clamp(pos.x, 0, imageWidth.value)
  const y = clamp(pos.y, 0, imageHeight.value)
  const h = draggingHandle.value as string
  if (h.includes('w')) box[0] = Math.min(x, box[2] - 4)
  if (h.includes('e')) box[2] = Math.max(x, box[0] + 4)
  if (h.includes('n')) box[1] = Math.min(y, box[3] - 4)
  if (h.includes('s')) box[3] = Math.max(y, box[1] + 4)
  editor.value.box = box
  editor.value.keypoints = resizeKeypoints(editor.value.keypoints, previousBox, box)
}

function resizeKeypoints(keypoints: PoseKeypointAnnotation[], fromBox: number[], toBox: number[]) {
  const fromW = Math.max(1, fromBox[2] - fromBox[0])
  const fromH = Math.max(1, fromBox[3] - fromBox[1])
  const toW = Math.max(1, toBox[2] - toBox[0])
  const toH = Math.max(1, toBox[3] - toBox[1])
  return keypoints.map((kp) => {
    const nx = (kp.x - fromBox[0]) / fromW
    const ny = (kp.y - fromBox[1]) / fromH
    return {
      ...kp,
      x: clamp(toBox[0] + nx * toW, toBox[0], toBox[2]),
      y: clamp(toBox[1] + ny * toH, toBox[1], toBox[3]),
    }
  })
}

function onPointerUp(event: PointerEvent) {
  if (panDrag && panDrag.pointerId === event.pointerId) {
    planeRef.value?.releasePointerCapture?.(event.pointerId)
    panDrag = null
    return
  }
  draggingKeypoint.value = null
  draggingHandle.value = null
}

function setZoom(next: number, origin?: { x: number; y: number }) {
  const previous = zoom.value
  const target = clamp(Math.round(next * 100) / 100, 1, 6)
  if (Math.abs(previous - target) < 0.01) return
  if (origin && stageRef.value) {
    const rect = stageRef.value.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    panOffset.x = panOffset.x + (1 - target / previous) * (origin.x - centerX - panOffset.x)
    panOffset.y = panOffset.y + (1 - target / previous) * (origin.y - centerY - panOffset.y)
  }
  zoom.value = target
  if (target === 1) { panOffset.x = 0; panOffset.y = 0 }
}

function zoomBy(delta: number, origin?: { x: number; y: number }) {
  setZoom(zoom.value + delta, origin)
}

function resetZoom() {
  zoom.value = 1
  panOffset.x = 0
  panOffset.y = 0
}

function onWheel(event: WheelEvent) {
  zoomBy(event.deltaY < 0 ? 0.2 : -0.2, { x: event.clientX, y: event.clientY })
}

function cycleVisibility(name: string) {
  if (!editor.value) return
  editor.value.keypoints = editor.value.keypoints.map((kp) => {
    if (kp.name !== name) return kp
    const nextVis = visibilityOptions[(visibilityOptions.indexOf(kp.visibility) + 1) % visibilityOptions.length]
    return { ...kp, visibility: nextVis }
  })
}

function setVisibility(name: string, visibility: PoseKeypointAnnotation['visibility']) {
  if (!editor.value) return
  editor.value.keypoints = editor.value.keypoints.map((kp) =>
    kp.name === name ? { ...kp, visibility } : kp,
  )
}

function handlePositions(box: number[]) {
  const mx = (box[0] + box[2]) / 2
  const my = (box[1] + box[3]) / 2
  return [
    { id: 'nw', x: box[0], y: box[1] }, { id: 'n', x: mx, y: box[1] }, { id: 'ne', x: box[2], y: box[1] },
    { id: 'e', x: box[2], y: my }, { id: 'se', x: box[2], y: box[3] }, { id: 's', x: mx, y: box[3] },
    { id: 'sw', x: box[0], y: box[3] }, { id: 'w', x: box[0], y: my },
  ]
}

function buildPayload(): PosePayload {
  const e = editor.value as Editor
  return { label: e.label.trim() || 'pose', box: e.box, keypoints: e.keypoints, confidence: 1, accepted: true }
}

function saveEditor() {
  if (!editor.value) return
  if (editor.value.sourceId === null) {
    emit('save', buildPayload())
  } else {
    emit('update', { ...buildPayload(), id: editor.value.sourceId })
  }
  closeEditor()
}

function deleteEditor() {
  if (editor.value?.sourceId != null) emit('delete', { id: editor.value.sourceId })
  closeEditor()
}

function closeEditor() {
  editor.value = null
  selectedKeypoint.value = null
  emit('update:editingPoseId', null)
}

function updateStageSize() {
  const el = stageRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  stageSize.value = { width: rect.width, height: rect.height }
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

watch(() => [props.width, props.height, props.imageSrc], () => {
  resetZoom()
  nextTick(updateStageSize)
})
</script>

<template>
  <div
    ref="stageRef"
    class="dataset-media-stage dataset-review-frame"
    :class="{ 'is-zoomed': canPan, 'is-panning': Boolean(panDrag) }"
    @wheel.prevent="onWheel"
  >
    <div
      ref="planeRef"
      class="dataset-media-plane"
      :class="`pose-tool-${activeTool}`"
      :style="planeStyle"
      @pointerdown="onPlanePointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    >
      <img class="dataset-media-image" :src="imageSrc" alt="" draggable="false" @load="updateStageSize" />

      <svg class="absolute inset-0 w-full h-full" :viewBox="`0 0 ${imageWidth} ${imageHeight}`" preserveAspectRatio="none">
        <!-- Saved poses (read-only unless being edited) -->
        <g v-for="pose in poses" :key="pose.id">
          <template v-if="editor?.sourceId !== pose.id">
            <rect
              :x="pose.box[0]" :y="pose.box[1]"
              :width="pose.box[2] - pose.box[0]" :height="pose.box[3] - pose.box[1]"
              fill="none" stroke="#3ECF8E" :stroke-width="strokeW"
              class="cursor-pointer" @pointerdown.stop="editExisting(pose)"
            />
            <line
              v-for="edge in skeletonEdges" :key="`${pose.id}-${edge[0]}-${edge[1]}`"
              :x1="keypointMap(pose.keypoints).get(template.keypoint_names[edge[0]])?.x"
              :y1="keypointMap(pose.keypoints).get(template.keypoint_names[edge[0]])?.y"
              :x2="keypointMap(pose.keypoints).get(template.keypoint_names[edge[1]])?.x"
              :y2="keypointMap(pose.keypoints).get(template.keypoint_names[edge[1]])?.y"
              stroke="#3ECF8E" :stroke-width="skeletonW" opacity="0.7"
            />
            <circle
              v-for="kp in pose.keypoints" :key="`${pose.id}-${kp.name}`"
              :cx="kp.x" :cy="kp.y" :r="nodeR"
              :fill="kp.visibility === 'missing' ? '#9CA3AF' : '#3ECF8E'"
              stroke="#ffffff" :stroke-width="strokeW * 0.75"
            />
          </template>
        </g>

        <!-- Editor -->
        <g v-if="editor">
          <rect
            :x="editor.box[0]" :y="editor.box[1]"
            :width="editor.box[2] - editor.box[0]" :height="editor.box[3] - editor.box[1]"
            fill="none" stroke="#2563EB" :stroke-dasharray="`${6 * unit} ${4 * unit}`" :stroke-width="strokeW"
          />
          <line
            v-for="edge in skeletonEdges" :key="`edit-${edge[0]}-${edge[1]}`"
            :x1="keypointMap(editor.keypoints).get(template.keypoint_names[edge[0]])?.x"
            :y1="keypointMap(editor.keypoints).get(template.keypoint_names[edge[0]])?.y"
            :x2="keypointMap(editor.keypoints).get(template.keypoint_names[edge[1]])?.x"
            :y2="keypointMap(editor.keypoints).get(template.keypoint_names[edge[1]])?.y"
            stroke="#2563EB" :stroke-width="skeletonW"
          />

          <!-- BBox handles -->
          <template v-if="activeTool === 'bbox'">
            <rect
              v-for="handle in handlePositions(editor.box)" :key="handle.id"
              :x="handle.x - handleHalf" :y="handle.y - handleHalf"
              :width="handleHalf * 2" :height="handleHalf * 2"
              fill="#ffffff" stroke="#2563EB" :stroke-width="strokeW" class="cursor-pointer"
              @pointerdown.stop="startHandleDrag(handle.id, $event)"
            />
          </template>

          <!-- Keypoint nodes -->
          <g v-for="kp in editor.keypoints" :key="kp.name">
            <circle
              :cx="kp.x" :cy="kp.y" :r="ringR"
              fill="none"
              :stroke="selectedKeypoint === kp.name ? '#2563EB' : '#ffffff'"
              :stroke-width="strokeW"
              :opacity="selectedKeypoint === kp.name ? 0.7 : hoverKeypoint === kp.name ? 0.5 : 0"
            />
            <circle
              :cx="kp.x" :cy="kp.y" :r="hitR" fill="transparent"
              :class="activeTool === 'move' ? 'cursor-grab' : activeTool === 'visibility' ? 'cursor-pointer' : 'cursor-default'"
              @pointerdown.stop="startKeypointDrag(kp.name, $event)"
              @pointerenter="hoverKeypoint = kp.name"
              @pointerleave="hoverKeypoint = null"
            />
            <circle
              :cx="kp.x" :cy="kp.y" :r="hoverKeypoint === kp.name || selectedKeypoint === kp.name ? selR : nodeR"
              :fill="visibilityColor(kp.visibility)" stroke="#ffffff" :stroke-width="strokeW * 0.75"
              class="pointer-events-none"
            />
            <text
              v-if="selectedKeypoint === kp.name"
              :x="kp.x + ringR + 2 * unit" :y="kp.y - ringR" :font-size="labelFont" fill="#2563EB"
              class="pointer-events-none select-none"
            >{{ kp.name }}</text>
          </g>
        </g>
      </svg>
    </div>

    <div class="dataset-zoom-toolbar" style="left: 10px; right: auto;" @pointerdown.stop @click.stop>
      <button type="button" aria-label="Zoom out" @click="zoomBy(-0.25)">-</button>
      <span>{{ zoomPercent }}</span>
      <button type="button" aria-label="Zoom in" @click="zoomBy(0.25)">+</button>
      <button type="button" aria-label="Reset zoom" @click="resetZoom">Reset</button>
    </div>

    <Teleport defer to="#pose-editor-sidebar">
      <section class="dataset-inspector-section flex min-h-[260px] max-h-[calc(100vh-230px)] flex-col overflow-hidden">
        <div class="dataset-field-row mb-2 shrink-0">
          <span class="dataset-field-label">Pose</span>
          <span class="dataset-field-value">{{ template.name }}</span>
        </div>
        <button v-if="!editing" class="dataset-primary-button w-full shrink-0" type="button" @click="createDraft">
          New Pose
        </button>
        <div v-else-if="editor" class="flex min-h-0 flex-1 flex-col">
          <input v-model="editor.label" class="dataset-text-input mb-2 !h-8 !text-[12px] shrink-0" placeholder="Label" />
          <div class="min-h-0 flex-1 overflow-y-auto pr-1 space-y-1">
            <div
              v-for="kp in editor.keypoints" :key="kp.name"
              class="grid grid-cols-[minmax(0,1fr)_120px] items-center gap-2 rounded px-1 py-0.5 text-[11px]"
              :class="{ 'bg-hairline/40': selectedKeypoint === kp.name || hoverKeypoint === kp.name }"
              @mouseenter="hoverKeypoint = kp.name"
              @mouseleave="hoverKeypoint = null"
              @click="selectedKeypoint = kp.name"
            >
              <span class="truncate text-ink cursor-pointer" :title="kp.name">{{ kp.name }}</span>
              <select
                :value="kp.visibility"
                class="dataset-text-input !h-7 !px-2 !py-0 !text-[11px]"
                @change="setVisibility(kp.name, ($event.target as HTMLSelectElement).value as PoseKeypointAnnotation['visibility'])"
              >
                <option v-for="visibility in visibilityOptions" :key="visibility" :value="visibility">{{ visibility }}</option>
              </select>
            </div>
          </div>
          <div class="mt-2 grid shrink-0 grid-cols-[1fr_auto_auto] gap-1.5 border-t border-hairline pt-2">
            <button class="dataset-primary-button flex-1" type="button" :disabled="saving" @click="saveEditor">
              {{ saving ? 'Saving...' : editor.sourceId === null ? 'Save' : 'Update' }}
            </button>
            <button v-if="editor.sourceId !== null" class="dataset-secondary-button" type="button" :disabled="saving" @click="deleteEditor">
              Delete
            </button>
            <button class="dataset-secondary-button" type="button" :disabled="saving" @click="closeEditor">
              Cancel
            </button>
          </div>
        </div>
      </section>
    </Teleport>
  </div>
</template>
