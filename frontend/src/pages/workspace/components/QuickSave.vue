<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatasetStore } from '../../../shared/stores/dataset'
import { useInferenceStore } from '../../../shared/stores/inference'

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

const selectedDataset = ref('')
const saving = ref(false)
const saved = ref(false)

onMounted(() => {
  datasetStore.fetchProjects()
})

async function save() {
  if (!selectedDataset.value || !inferenceStore.file) return

  saving.value = true
  saved.value = false

  try {
    await datasetStore.saveToDataset(
      selectedDataset.value,
      inferenceStore.file,
      inferenceStore.detections,
      inferenceStore.mediaMode,
    )
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="inferenceStore.detections.length > 0" class="flex items-center gap-2 p-2 bg-ink/[0.02] rounded-(--radius-md)">
    <select
      v-model="selectedDataset"
      class="flex-1 px-2 py-1 text-[12px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
    >
      <option value="" disabled>Save to...</option>
      <option v-for="p in datasetStore.projects" :key="p.name" :value="p.name">
        {{ p.name }}
      </option>
    </select>

    <button
      @click="save"
      :disabled="!selectedDataset || saving"
      class="px-3 py-1 text-[12px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50 whitespace-nowrap"
    >
      <span v-if="saving">Saving...</span>
      <span v-else-if="saved" class="text-white">✓ Saved</span>
      <span v-else>Save</span>
    </button>
  </div>
</template>
