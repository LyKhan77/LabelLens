<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PoseAnnotation, PoseKeypointAnnotation } from '../../shared/api/dataset'
import type { PoseTemplate } from '../../shared/types'

const props = defineProps<{
  imageSrc: string
  width: number
  height: number
  poses: PoseAnnotation[]
  template: PoseTemplate
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [payload: { label: string; box: number[]; keypoints: PoseKeypointAnnotation[]; confidence?: number; accepted?: boolean }]
}>()

// Anatomical default layout, normalized 0..1 within the bbox (x right, y down).
// Lets the template spawn as a recognizable skeleton instead of a generic blob.
const KEYPOINT_LAYOUT: Record<string, [number, number]> = {
  // box corners
  top_left: [0, 0],
  top_right: [1, 0],
  bottom_right: [1, 1],
  bottom_left: [0, 1],
  // COCO person 17
  nose: [0.5, 0.1],
  left_eye: [0.43, 0.07],
  right_eye: [0.57, 0.07],
  left_ear: [0.37, 0.09],
  right_ear: [0.63, 0.09],
  left_shoulder: [0.35, 0.25],
  right_shoulder: [0.65, 0.25],
  left_elbow: [0.28, 0.43],
  right_elbow: [0.72, 0.43],
  left_wrist: [0.25, 0.6],
  right_wrist: [0.75, 0.6],
  left_hip: [0.42, 0.58],
  right_hip: [0.58, 0.58],
  left_knee: [0.4, 0.78],
  right_knee: [0.6, 0.78],
  left_ankle: [0.39, 0.97],
  right_ankle: [0.61, 0.97],
}

const draftLabel = ref('pose')
const draftBox = ref<number[] | null>(null)
const draftKeypoints = ref<PoseKeypointAnnotation[]>([])
const draggingKeypoint = ref<string | null>(null)

const viewBox = computed(() => `0 0 ${props.width || 1} ${props.height || 1}`)
const skeletonEdges = computed(() => props.template.skeleton ?? [])
const hasDraft = computed(() => Boolean(draftBox.value && draftKeypoints.value.length))

function keypointMap(keypoints: PoseKeypointAnnotation[]) {
  return new Map(keypoints.map((keypoint) => [keypoint.name, keypoint]))
}

function draftKeypointMap() {
  return keypointMap(draftKeypoints.value)
}

function createDraft() {
  const w = props.width || 1
  const h = props.height || 1
  const box = [w * 0.25, h * 0.2, w * 0.75, h * 0.8]
  draftBox.value = box
  const boxW = box[2] - box[0]
  const boxH = box[3] - box[1]
  draftKeypoints.value = props.template.keypoint_names.map((name, index) => {
    const layout = KEYPOINT_LAYOUT[name]
    if (layout) {
      return { name, x: box[0] + layout[0] * boxW, y: box[1] + layout[1] * boxH, visibility: 'visible' }
    }
    // Unknown keypoint name: fall back to an even ring inside the bbox.
    const angle = (Math.PI * 2 * index) / Math.max(1, props.template.keypoint_names.length)
    const cx = box[0] + boxW / 2
    const cy = box[1] + boxH / 2
    return {
      name,
      x: cx + Math.cos(angle) * boxW * 0.35,
      y: cy + Math.sin(angle) * boxH * 0.35,
      visibility: 'visible',
    }
  })
}

function pointerPosition(event: PointerEvent) {
  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * props.width
  const y = ((event.clientY - rect.top) / rect.height) * props.height
  return {
    x: Math.min(Math.max(x, 0), props.width),
    y: Math.min(Math.max(y, 0), props.height),
  }
}

function startDrag(name: string, event: PointerEvent) {
  draggingKeypoint.value = name
  ;(event.target as Element).setPointerCapture?.(event.pointerId)
}

function drag(event: PointerEvent) {
  if (!draggingKeypoint.value) return
  const pos = pointerPosition(event)
  draftKeypoints.value = draftKeypoints.value.map((keypoint) => (
    keypoint.name === draggingKeypoint.value ? { ...keypoint, x: pos.x, y: pos.y } : keypoint
  ))
}

function stopDrag() {
  draggingKeypoint.value = null
}

function setVisibility(name: string, visibility: PoseKeypointAnnotation['visibility']) {
  draftKeypoints.value = draftKeypoints.value.map((keypoint) => (
    keypoint.name === name ? { ...keypoint, visibility } : keypoint
  ))
}

function saveDraft() {
  if (!draftBox.value || !draftKeypoints.value.length) return
  emit('save', {
    label: draftLabel.value.trim() || 'pose',
    box: draftBox.value,
    keypoints: draftKeypoints.value,
    confidence: 1,
    accepted: true,
  })
  draftBox.value = null
  draftKeypoints.value = []
}
</script>

<template>
  <div class="dataset-review-frame relative overflow-hidden">
    <img :src="imageSrc" alt="" class="absolute inset-0 w-full h-full object-contain" />
    <svg
      class="absolute inset-0 w-full h-full"
      :viewBox="viewBox"
      @pointermove="drag"
      @pointerup="stopDrag"
      @pointerleave="stopDrag"
    >
      <g v-for="pose in poses" :key="pose.id">
        <rect
          :x="pose.box[0]"
          :y="pose.box[1]"
          :width="pose.box[2] - pose.box[0]"
          :height="pose.box[3] - pose.box[1]"
          fill="none"
          stroke="#3ECF8E"
          stroke-width="2"
        />
        <line
          v-for="edge in skeletonEdges"
          :key="`${pose.id}-${edge[0]}-${edge[1]}`"
          :x1="keypointMap(pose.keypoints).get(template.keypoint_names[edge[0]])?.x"
          :y1="keypointMap(pose.keypoints).get(template.keypoint_names[edge[0]])?.y"
          :x2="keypointMap(pose.keypoints).get(template.keypoint_names[edge[1]])?.x"
          :y2="keypointMap(pose.keypoints).get(template.keypoint_names[edge[1]])?.y"
          stroke="#3ECF8E"
          stroke-width="2"
          opacity="0.75"
        />
        <circle
          v-for="keypoint in pose.keypoints"
          :key="`${pose.id}-${keypoint.name}`"
          :cx="keypoint.x"
          :cy="keypoint.y"
          r="4"
          :fill="keypoint.visibility === 'missing' ? '#9CA3AF' : '#3ECF8E'"
          stroke="#ffffff"
          stroke-width="1.5"
        />
      </g>

      <g v-if="hasDraft && draftBox">
        <rect
          :x="draftBox[0]"
          :y="draftBox[1]"
          :width="draftBox[2] - draftBox[0]"
          :height="draftBox[3] - draftBox[1]"
          fill="none"
          stroke="#2563EB"
          stroke-dasharray="6 4"
          stroke-width="2"
        />
        <line
          v-for="edge in skeletonEdges"
          :key="`draft-${edge[0]}-${edge[1]}`"
          :x1="draftKeypointMap().get(template.keypoint_names[edge[0]])?.x"
          :y1="draftKeypointMap().get(template.keypoint_names[edge[0]])?.y"
          :x2="draftKeypointMap().get(template.keypoint_names[edge[1]])?.x"
          :y2="draftKeypointMap().get(template.keypoint_names[edge[1]])?.y"
          stroke="#2563EB"
          stroke-width="2"
        />
        <circle
          v-for="keypoint in draftKeypoints"
          :key="keypoint.name"
          :cx="keypoint.x"
          :cy="keypoint.y"
          r="5"
          :fill="keypoint.visibility === 'missing' ? '#9CA3AF' : keypoint.visibility === 'occluded' ? '#F59E0B' : '#2563EB'"
          stroke="#ffffff"
          stroke-width="1.5"
          class="cursor-grab"
          @pointerdown.stop="startDrag(keypoint.name, $event)"
        />
      </g>
    </svg>

    <aside class="absolute right-3 top-3 w-[260px] rounded-(--radius-md) border border-hairline bg-canvas/95 p-3 shadow-lg">
      <div class="dataset-field-row mb-2">
        <span class="dataset-field-label">Pose</span>
        <span class="dataset-field-value">{{ template.name }}</span>
      </div>
      <button v-if="!hasDraft" class="dataset-primary-button w-full" type="button" @click="createDraft">
        New Pose
      </button>
      <template v-else>
        <input v-model="draftLabel" class="dataset-text-input mb-2" placeholder="Label" />
        <div class="max-h-[220px] overflow-auto space-y-1">
          <div v-for="keypoint in draftKeypoints" :key="keypoint.name" class="flex items-center justify-between gap-2 text-[11px]">
            <span class="truncate text-ink">{{ keypoint.name }}</span>
            <select :value="keypoint.visibility" class="dataset-text-input !h-7 !text-[11px]" @change="setVisibility(keypoint.name, ($event.target as HTMLSelectElement).value as PoseKeypointAnnotation['visibility'])">
              <option value="visible">visible</option>
              <option value="occluded">occluded</option>
              <option value="missing">missing</option>
            </select>
          </div>
        </div>
        <div class="flex gap-2 mt-3">
          <button class="dataset-primary-button flex-1" type="button" :disabled="saving" @click="saveDraft">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
          <button class="dataset-secondary-button" type="button" :disabled="saving" @click="draftBox = null; draftKeypoints = []">
            Cancel
          </button>
        </div>
      </template>
    </aside>
  </div>
</template>
