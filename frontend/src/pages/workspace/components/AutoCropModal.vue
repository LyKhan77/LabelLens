<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDatasetStore } from '../../../shared/stores/dataset'
import { useInferenceStore } from '../../../shared/stores/inference'
import type { DatasetTaskConfig, DatasetTaskType } from '../../../shared/types'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

const mode = ref<'existing' | 'new'>('existing')
const selectedDataset = ref('')
const newName = ref('')
const newTaskType = ref<DatasetTaskType>('classify_single')
const sampleFps = ref(1)
const rtspTimer = ref('')
const error = ref<string | null>(null)
const busy = ref(false)

const taskOptions: { value: DatasetTaskType; label: string }[] = [
  { value: 'classify_single', label: 'Classification · Single' },
  { value: 'classify_multi', label: 'Classification · Multi' },
  { value: 'detect', label: 'Detection' },
  { value: 'segment', label: 'Segmentation' },
]

const isRtspMode = computed(() => inferenceStore.mediaMode === 'rtsp')
const activeTimerLabel = computed(() => {
  const seconds = datasetStore.autoCropRtspTimerSeconds
  if (!seconds || seconds <= 0) return null
  const mm = Math.floor(seconds / 60)
  const ss = seconds % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
})

onMounted(() => {
  datasetStore.fetchProjects()
  sampleFps.value = datasetStore.autoCropFps
  selectedDataset.value = datasetStore.autoCropDataset ?? ''
})

function parseRtspTimerSeconds(): number | null {
  const raw = rtspTimer.value.trim()
  if (!raw) return null
  const match = raw.match(/^(\d{1,3}):([0-5]\d)$/)
  if (!match) return null
  return (Number(match[1]) * 60) + Number(match[2])
}

function buildTaskConfig(): DatasetTaskConfig {
  if (newTaskType.value === 'segment') return { requires_masks: true }
  if (newTaskType.value === 'classify_single') return { classification_mode: 'single' }
  if (newTaskType.value === 'classify_multi') return { classification_mode: 'multi' }
  return {}
}

async function start() {
  error.value = null

  let rtspTimerSeconds: number | null = null
  if (isRtspMode.value) {
    rtspTimerSeconds = parseRtspTimerSeconds()
    if (rtspTimer.value.trim() && rtspTimerSeconds === null) {
      error.value = 'Timer format must be MM:SS'
      return
    }
  }

  let target = selectedDataset.value
  if (mode.value === 'new') {
    const name = newName.value.trim()
    if (!name) {
      error.value = 'New dataset name is required'
      return
    }
    busy.value = true
    try {
      await datasetStore.createProject(name, newTaskType.value, buildTaskConfig())
      target = name
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to create dataset'
      busy.value = false
      return
    }
    busy.value = false
  }

  if (!target) {
    error.value = 'Select or create a target dataset'
    return
  }

  datasetStore.toggleAutoCrop(target, sampleFps.value, rtspTimerSeconds)
  emit('close')
}

function stop() {
  datasetStore.disableAutoCrop()
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="emit('close')">
    <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[420px] border border-hairline">
      <h3 class="text-[16px] font-medium text-ink mb-(--spacing-lg)">Auto-Crop Objects</h3>

      <template v-if="!datasetStore.autoCropActive">
        <p class="text-[12px] text-ink-faint mb-(--spacing-md)">
          Crops each detected object (bbox, HD PNG) into the target dataset as raw, unannotated images for later labeling. Detection / Segmentation only.
        </p>

        <!-- Existing vs New -->
        <div class="flex gap-1 mb-(--spacing-md)">
          <button
            v-for="m in (['existing', 'new'] as const)"
            :key="m"
            @click="mode = m"
            class="flex-1 px-2 py-1.5 text-[12px] font-medium rounded-(--radius-md) border transition-colors"
            :class="mode === m ? 'border-primary bg-primary/10 text-primary-deep' : 'border-hairline text-ink-mute hover:bg-canvas-soft'"
          >
            {{ m === 'existing' ? 'Existing Dataset' : 'New Dataset' }}
          </button>
        </div>

        <label v-if="mode === 'existing'" class="block mb-(--spacing-md)">
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

        <template v-else>
          <label class="block mb-(--spacing-md)">
            <span class="text-[12px] text-ink-mute uppercase tracking-wide">New Dataset Name</span>
            <input
              v-model="newName"
              type="text"
              placeholder="defect-crops"
              class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
            />
          </label>
          <label class="block mb-(--spacing-md)">
            <span class="text-[12px] text-ink-mute uppercase tracking-wide">Task Type</span>
            <select
              v-model="newTaskType"
              class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
            >
              <option v-for="t in taskOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </label>
        </template>

        <label class="block mb-(--spacing-md)">
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

        <label v-if="isRtspMode" class="block mb-(--spacing-lg)">
          <span class="text-[12px] text-ink-mute uppercase tracking-wide">RTSP Auto-Stop Timer (optional)</span>
          <input
            v-model="rtspTimer"
            type="text"
            placeholder="MM:SS"
            class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
          />
          <p class="mt-1 text-[11px] text-ink-faint">Example: 05:00. Empty means no timer.</p>
        </label>

        <p v-if="error" class="mb-(--spacing-md) text-[11px] text-red-500">{{ error }}</p>

        <div class="flex gap-3 justify-end">
          <button
            @click="emit('close')"
            class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5"
          >
            Cancel
          </button>
          <button
            @click="start"
            :disabled="busy"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
          >
            {{ busy ? 'Creating...' : 'Start Auto-Crop' }}
          </button>
        </div>
      </template>

      <template v-else>
        <div class="p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px] mb-(--spacing-lg)">
          Auto-crop is active -> {{ datasetStore.autoCropDataset }}
          <br />
          <span class="text-ink-faint">{{ datasetStore.autoCropFps }} fps sampling</span>
          <template v-if="activeTimerLabel">
            <br />
            <span class="text-ink-faint">RTSP timer: {{ activeTimerLabel }}</span>
          </template>
        </div>

        <div class="flex gap-3 justify-end">
          <button
            @click="stop"
            class="px-4 py-2 text-[13px] font-medium text-red-400 bg-red-500/10 rounded-(--radius-md) hover:bg-red-500/20"
          >
            Stop Auto-Crop
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
