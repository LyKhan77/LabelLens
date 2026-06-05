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
  draftKeypoints.value = props.template.keypoint_names.map((name, index) => {
    const cornerMap: Record<string, [number, number]> = {
      top_left: [box[0], box[1]],
      top_right: [box[2], box[1]],
      bottom_right: [box[2], box[3]],
      bottom_left: [box[0], box[3]],
    }
    const corner = cornerMap[name]
    if (corner) {
      return { name, x: corner[0], y: corner[1], visibility: 'visible' }
    }
    const angle = (Math.PI * 2 * index) / Math.max(1, props.template.keypoint_names.length)
    const cx = (box[0] + box[2]) / 2
    const cy = (box[1] + box[3]) / 2
    return {
      name,
      x: cx + Math.cos(angle) * (box[2] - box[0]) * 0.35,
      y: cy + Math.sin(angle) * (box[3] - box[1]) * 0.35,
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
