<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ClassificationLabelAnnotation } from '../../shared/api/dataset'

const props = defineProps<{
  mode: 'single' | 'multi'
  labels: ClassificationLabelAnnotation[]
  knownLabels: string[]
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [labels: { label: string; confidence?: number; accepted?: boolean; source?: string }[]]
}>()

const selected = ref<Set<string>>(new Set())
const localLabels = ref<string[]>([])
const draftLabel = ref('')

watch(
  () => props.labels,
  () => {
    selected.value = new Set(props.labels.filter((label) => label.accepted).map((label) => label.label))
    localLabels.value = []
  },
  { immediate: true, deep: true },
)

const allLabels = computed(() => {
  const labels = new Set(props.knownLabels)
  for (const label of props.labels) labels.add(label.label)
  for (const label of localLabels.value) labels.add(label)
  return Array.from(labels).sort((a, b) => a.localeCompare(b))
})

const canSave = computed(() => selected.value.size > 0 && !props.saving)
const activeLabelText = computed(() => {
  if (!selected.value.size) return 'No active label'
  return Array.from(selected.value).join(', ')
})

function toggle(label: string) {
  const next = new Set(selected.value)
  if (props.mode === 'single') {
    next.clear()
    next.add(label)
  } else if (next.has(label)) {
    next.delete(label)
  } else {
    next.add(label)
  }
  selected.value = next
}

function addDraftLabel() {
  const label = draftLabel.value.trim()
  if (!label) return
  if (!localLabels.value.includes(label) && !allLabels.value.includes(label)) {
    localLabels.value = [...localLabels.value, label]
  }
  draftLabel.value = ''
}

function save() {
  emit('save', Array.from(selected.value).map((label) => ({
    label,
    confidence: 1,
    accepted: true,
    source: 'manual',
  })))
}
</script>

<template>
  <section class="dataset-inspector-section">
    <div class="dataset-field-row">
      <span class="dataset-field-label">Image Labels</span>
      <span class="dataset-field-value">{{ mode === 'single' ? 'Single-label' : 'Multi-label' }}</span>
    </div>

    <div class="dataset-panel-block !p-3">
      <span class="dataset-field-label">Active Label</span>
      <strong class="block mt-1 text-[14px] text-ink">{{ activeLabelText }}</strong>
      <p class="mt-1 text-[12px] text-ink-mute leading-relaxed">
        Add labels to the project list, select the active label for this image, then save.
      </p>
    </div>

    <div v-if="allLabels.length" class="dataset-class-filters">
      <button
        v-for="label in allLabels"
        :key="label"
        :class="{ 'is-active': selected.has(label) }"
        type="button"
        @click="toggle(label)"
      >
        {{ label }}
      </button>
    </div>
    <div v-else class="dataset-empty-note">
      No labels yet. Add the first label below.
    </div>

    <div class="dataset-canvas-label-row">
      <input
        v-model="draftLabel"
        type="text"
        placeholder="Type new label"
        @keydown.enter.prevent="addDraftLabel"
      />
      <button class="dataset-secondary-button" type="button" :disabled="!draftLabel.trim()" @click="addDraftLabel">Add</button>
    </div>

    <button class="dataset-primary-button w-full" :disabled="!canSave" @click="save">
      {{ saving ? 'Saving...' : 'Save Labels' }}
    </button>
  </section>
</template>
