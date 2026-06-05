<script setup lang="ts">
import { computed } from 'vue'
import type { PoseTemplate } from '../../shared/types'

const props = defineProps<{
  modelValue: PoseTemplate
}>()

const emit = defineEmits<{
  'update:modelValue': [template: PoseTemplate]
}>()

const presets: Record<string, PoseTemplate> = {
  box_corners: {
    name: 'Box Corners',
    keypoint_names: ['top_left', 'top_right', 'bottom_right', 'bottom_left'],
    skeleton: [[0, 1], [1, 2], [2, 3], [3, 0]],
    flip_idx: [1, 0, 3, 2],
    kpt_shape: [4, 3],
  },
  coco_person_17: {
    name: 'COCO Person 17',
    keypoint_names: ['nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear', 'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist', 'left_hip', 'right_hip', 'left_knee', 'right_knee', 'left_ankle', 'right_ankle'],
    skeleton: [[5, 6], [5, 7], [7, 9], [6, 8], [8, 10], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4]],
    flip_idx: [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15],
    kpt_shape: [17, 3],
  },
}

const selectedPreset = computed({
  get() {
    return Object.entries(presets).find(([, template]) => template.name === props.modelValue.name)?.[0] ?? 'custom'
  },
  set(key: string) {
    const preset = presets[key]
    if (preset) emit('update:modelValue', structuredClone(preset))
  },
})
</script>

<template>
  <div class="dataset-field-block">
    <span class="dataset-field-label">Pose Template</span>
    <select v-model="selectedPreset" class="dataset-text-input">
      <option value="box_corners">Box Corners</option>
      <option value="coco_person_17">COCO Person 17</option>
    </select>
    <p class="text-[12px] text-ink-mute leading-relaxed">
      {{ modelValue.keypoint_names.length }} keypoints · {{ modelValue.skeleton.length }} skeleton edges
    </p>
  </div>
</template>
