<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDatasetStore } from '../../../shared/stores/dataset'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()

const selectedDataset = ref('')
const sampleFps = ref(1)

onMounted(() => {
  datasetStore.fetchProjects()
})

function start() {
  if (!selectedDataset.value) return
  datasetStore.toggleAutoLabel(selectedDataset.value, sampleFps.value)
  emit('close')
}

function stop() {
  datasetStore.disableAutoLabel()
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="emit('close')">
    <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[400px] border border-hairline">
      <h3 class="text-[16px] font-medium text-ink mb-(--spacing-lg)">Auto-Labelling</h3>

      <template v-if="!datasetStore.autoLabelActive">
        <!-- Dataset selector -->
        <label class="block mb-(--spacing-md)">
          <span class="text-[12px] text-ink-mute uppercase tracking-wide">Target Dataset</span>
          <select
            v-model="selectedDataset"
            class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
          >
            <option value="" disabled>Select dataset...</option>
            <option v-for="p in datasetStore.projects" :key="p.name" :value="p.name">
              {{ p.name }} ({{ p.stats.total_images }} images)
            </option>
          </select>
        </label>

        <!-- Frame rate -->
        <label class="block mb-(--spacing-lg)">
          <div class="flex justify-between">
            <span class="text-[12px] text-ink-mute uppercase tracking-wide">Frame Rate (video/RTSP)</span>
            <span class="text-[12px] text-ink font-mono">{{ sampleFps }} fps</span>
          </div>
          <input
            type="range"
            v-model.number="sampleFps"
            min="0.5"
            max="10"
            step="0.5"
            class="w-full mt-1 accent-[#3ecf8e]"
          />
        </label>

        <div class="flex gap-3 justify-end">
          <button
            @click="emit('close')"
            class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5"
          >
            Cancel
          </button>
          <button
            @click="start"
            :disabled="!selectedDataset"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
          >
            Start Auto-Label
          </button>
        </div>
      </template>

      <template v-else>
        <!-- Active state -->
        <div class="p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px] mb-(--spacing-lg)">
          Auto-labelling is active → {{ datasetStore.autoLabelDataset }}
          <br />
          <span class="text-ink-faint">{{ sampleFps }} fps sampling for video/RTSP</span>
        </div>

        <div class="flex gap-3 justify-end">
          <button
            @click="stop"
            class="px-4 py-2 text-[13px] font-medium text-red-400 bg-red-500/10 rounded-(--radius-md) hover:bg-red-500/20"
          >
            Stop Auto-Label
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
