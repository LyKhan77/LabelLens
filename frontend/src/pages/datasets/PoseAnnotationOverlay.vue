<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
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
const panning = ref<{ x: number; y: number } | null>(null)
const view = reactive({ scale: 1, tx: 0, ty: 0 })

const viewBox = computed(() => `0 0 ${props.width || 1} ${props.height || 1}`)
const groupTransform = computed(() => `translate(${view.tx} ${view.ty}) scale(${view.scale})`)
const skeletonEdges = computed(() => props.template.skeleton ?? [])
const editing = computed(() => editor.value !== null)

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
  const w = props.width || 1
  const h = props.height || 1
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

function pointerPosition(event: PointerEvent) {
  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const svgX = ((event.clientX - rect.left) / rect.width) * props.width
  const svgY = ((event.clientY - rect.top) / rect.height) * props.height
  return { x: (svgX - view.tx) / view.scale, y: (svgY - view.ty) / view.scale, svgX, svgY }
}

function startKeypointDrag(name: string, event: PointerEvent) {
  if (props.activeTool === 'visibility') { cycleVisibility(name); return }
  if (props.activeTool !== 'move') return
  selectedKeypoint.value = name
  draggingKeypoint.value = name
  ;(event.target as Element).setPointerCapture?.(event.pointerId)
}

function startHandleDrag(handle: string, event: PointerEvent) {
  if (props.activeTool !== 'bbox') return
  draggingHandle.value = handle
  ;(event.target as Element).setPointerCapture?.(event.pointerId)
}

function onSvgPointerDown(event: PointerEvent) {
  if (props.activeTool === 'pan') {
    panning.value = { x: event.clientX, y: event.clientY }
    ;(event.currentTarget as Element).setPointerCapture?.(event.pointerId)
  }
}

function onPointerMove(event: PointerEvent) {
  if (!editor.value) {
    if (panning.value) doPan(event)
    return
  }
  if (draggingKeypoint.value) {
    const pos = pointerPosition(event)
    const box = editor.value.box
    const x = clamp(pos.x, box[0], box[2])
    const y = clamp(pos.y, box[1], box[3])
    editor.value.keypoints = editor.value.keypoints.map((kp) =>
      kp.name === draggingKeypoint.value ? { ...kp, x, y } : kp,
    )
  } else if (draggingHandle.value) {
    resizeBox(event)
  } else if (panning.value) {
    doPan(event)
  }
}

function doPan(event: PointerEvent) {
  if (!panning.value) return
  const rect = (event.currentTarget as SVGSVGElement).getBoundingClientRect()
  const dx = ((event.clientX - panning.value.x) / rect.width) * props.width
  const dy = ((event.clientY - panning.value.y) / rect.height) * props.height
  view.tx += dx
  view.ty += dy
  panning.value = { x: event.clientX, y: event.clientY }
}

function resizeBox(event: PointerEvent) {
  if (!editor.value) return
  const pos = pointerPosition(event)
  const box = [...editor.value.box]
  const x = clamp(pos.x, 0, props.width)
  const y = clamp(pos.y, 0, props.height)
  const h = draggingHandle.value as string
  if (h.includes('w')) box[0] = Math.min(x, box[2] - 4)
  if (h.includes('e')) box[2] = Math.max(x, box[0] + 4)
  if (h.includes('n')) box[1] = Math.min(y, box[3] - 4)
  if (h.includes('s')) box[3] = Math.max(y, box[1] + 4)
  editor.value.box = box
  editor.value.keypoints = editor.value.keypoints.map((kp) => ({
    ...kp,
    x: clamp(kp.x, box[0], box[2]),
    y: clamp(kp.y, box[1], box[3]),
  }))
}

function stopDrag() {
  draggingKeypoint.value = null
  draggingHandle.value = null
  panning.value = null
}

function onWheel(event: WheelEvent) {
  if (props.activeTool !== 'pan') return
  event.preventDefault()
  const rect = (event.currentTarget as SVGSVGElement).getBoundingClientRect()
  const svgX = ((event.clientX - rect.left) / rect.width) * props.width
  const svgY = ((event.clientY - rect.top) / rect.height) * props.height
  const imgX = (svgX - view.tx) / view.scale
  const imgY = (svgY - view.ty) / view.scale
  const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1
  const newScale = clamp(view.scale * factor, 1, 8)
  view.tx = svgX - imgX * newScale
  view.ty = svgY - imgY * newScale
  view.scale = newScale
}

function cycleVisibility(name: string) {
  if (!editor.value) return
  const order: PoseKeypointAnnotation['visibility'][] = ['visible', 'occluded', 'missing']
  editor.value.keypoints = editor.value.keypoints.map((kp) => {
    if (kp.name !== name) return kp
    const next = order[(order.indexOf(kp.visibility) + 1) % order.length]
    return { ...kp, visibility: next }
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
</script>

<template>
  <div class="dataset-review-frame relative overflow-hidden">
    <img :src="imageSrc" alt="" class="absolute inset-0 w-full h-full object-contain" />
    <svg
      class="absolute inset-0 w-full h-full"
      :class="{ 'cursor-grab': activeTool === 'pan' }"
      :viewBox="viewBox"
      @pointerdown="onSvgPointerDown"
      @pointermove="onPointerMove"
      @pointerup="stopDrag"
      @pointerleave="stopDrag"
      @wheel="onWheel"
    >
      <g :transform="groupTransform">
        <!-- Saved poses (read-only unless being edited) -->
        <g v-for="pose in poses" :key="pose.id">
          <template v-if="editor?.sourceId !== pose.id">
            <rect
              :x="pose.box[0]" :y="pose.box[1]"
              :width="pose.box[2] - pose.box[0]" :height="pose.box[3] - pose.box[1]"
              fill="none" stroke="#3ECF8E" stroke-width="2"
              class="cursor-pointer" @pointerdown.stop="editExisting(pose)"
            />
            <line
              v-for="edge in skeletonEdges" :key="`${pose.id}-${edge[0]}-${edge[1]}`"
              :x1="keypointMap(pose.keypoints).get(template.keypoint_names[edge[0]])?.x"
              :y1="keypointMap(pose.keypoints).get(template.keypoint_names[edge[0]])?.y"
              :x2="keypointMap(pose.keypoints).get(template.keypoint_names[edge[1]])?.x"
              :y2="keypointMap(pose.keypoints).get(template.keypoint_names[edge[1]])?.y"
              stroke="#3ECF8E" stroke-width="2" opacity="0.7"
            />
            <circle
              v-for="kp in pose.keypoints" :key="`${pose.id}-${kp.name}`"
              :cx="kp.x" :cy="kp.y" r="4"
              :fill="kp.visibility === 'missing' ? '#9CA3AF' : '#3ECF8E'"
              stroke="#ffffff" stroke-width="1.5"
            />
          </template>
        </g>

        <!-- Editor -->
        <g v-if="editor">
          <rect
            :x="editor.box[0]" :y="editor.box[1]"
            :width="editor.box[2] - editor.box[0]" :height="editor.box[3] - editor.box[1]"
            fill="none" stroke="#2563EB" stroke-dasharray="6 4" stroke-width="2"
          />
          <line
            v-for="edge in skeletonEdges" :key="`edit-${edge[0]}-${edge[1]}`"
            :x1="keypointMap(editor.keypoints).get(template.keypoint_names[edge[0]])?.x"
            :y1="keypointMap(editor.keypoints).get(template.keypoint_names[edge[0]])?.y"
            :x2="keypointMap(editor.keypoints).get(template.keypoint_names[edge[1]])?.x"
            :y2="keypointMap(editor.keypoints).get(template.keypoint_names[edge[1]])?.y"
            stroke="#2563EB" stroke-width="2"
          />

          <!-- BBox handles -->
          <template v-if="activeTool === 'bbox'">
            <rect
              v-for="handle in handlePositions(editor.box)" :key="handle.id"
              :x="handle.x - 5" :y="handle.y - 5" width="10" height="10"
              fill="#ffffff" stroke="#2563EB" stroke-width="2" class="cursor-pointer"
              @pointerdown.stop="startHandleDrag(handle.id, $event)"
            />
          </template>

          <!-- Keypoint nodes -->
          <g v-for="kp in editor.keypoints" :key="kp.name">
            <circle
              :cx="kp.x" :cy="kp.y"
              :r="selectedKeypoint === kp.name ? 9 : hoverKeypoint === kp.name ? 8 : 6"
              fill="none"
              :stroke="selectedKeypoint === kp.name ? '#2563EB' : 'transparent'"
              stroke-width="2"
              :opacity="selectedKeypoint === kp.name ? 0.6 : hoverKeypoint === kp.name ? 0.4 : 0"
            />
            <circle
              :cx="kp.x" :cy="kp.y" r="12" fill="transparent"
              :class="activeTool === 'move' ? 'cursor-grab' : activeTool === 'visibility' ? 'cursor-pointer' : 'cursor-default'"
              @pointerdown.stop="startKeypointDrag(kp.name, $event)"
              @pointerenter="hoverKeypoint = kp.name"
              @pointerleave="hoverKeypoint = null"
            />
            <circle
              :cx="kp.x" :cy="kp.y" r="5"
              :fill="visibilityColor(kp.visibility)" stroke="#ffffff" stroke-width="1.5"
              class="pointer-events-none"
            />
            <text
              v-if="selectedKeypoint === kp.name"
              :x="kp.x + 10" :y="kp.y - 8" font-size="11" fill="#2563EB"
              class="pointer-events-none select-none"
            >{{ kp.name }}</text>
          </g>
        </g>
      </g>
    </svg>

    <aside class="absolute right-3 top-3 w-[260px] rounded-(--radius-md) border border-hairline bg-canvas/95 p-3 shadow-lg">
      <div class="dataset-field-row mb-2">
        <span class="dataset-field-label">Pose</span>
        <span class="dataset-field-value">{{ template.name }}</span>
      </div>
      <button v-if="!editing" class="dataset-primary-button w-full" type="button" @click="createDraft">
        New Pose
      </button>
      <template v-else-if="editor">
        <input v-model="editor.label" class="dataset-text-input mb-2" placeholder="Label" />
        <div class="max-h-[220px] overflow-auto space-y-1">
          <div
            v-for="kp in editor.keypoints" :key="kp.name"
            class="flex items-center justify-between gap-2 text-[11px] rounded px-1 py-0.5"
            :class="{ 'bg-hairline/40': selectedKeypoint === kp.name || hoverKeypoint === kp.name }"
            @mouseenter="hoverKeypoint = kp.name"
            @mouseleave="hoverKeypoint = null"
            @click="selectedKeypoint = kp.name"
          >
            <span class="truncate text-ink cursor-pointer">{{ kp.name }}</span>
            <select
              :value="kp.visibility" class="dataset-text-input !h-7 !text-[11px]"
              @change="setVisibility(kp.name, ($event.target as HTMLSelectElement).value as PoseKeypointAnnotation['visibility'])"
            >
              <option value="visible">visible</option>
              <option value="occluded">occluded</option>
              <option value="missing">missing</option>
            </select>
          </div>
        </div>
        <div class="flex gap-2 mt-3">
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
      </template>
    </aside>
  </div>
</template>
