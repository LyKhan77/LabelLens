<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDatasetStore } from '../../../shared/stores/dataset'
import { useInferenceStore } from '../../../shared/stores/inference'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()

const selectedDataset = ref('')
const sampleFps = ref(1)
const rtspTimer = ref('')
const timerError = ref<string | null>(null)

const isRtspMode = computed(() => inferenceStore.mediaMode === 'rtsp')
const activeTimerLabel = computed(() => {
  const seconds = datasetStore.autoLabelRtspTimerSeconds
  if (!seconds || seconds <= 0) return null
  const mm = Math.floor(seconds / 60)
  const ss = seconds % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
})

onMounted(() => {
  datasetStore.fetchProjects()
  sampleFps.value = datasetStore.autoLabelFps
  selectedDataset.value = datasetStore.autoLabelDataset ?? ''
  if (datasetStore.autoLabelRtspTimerSeconds && datasetStore.autoLabelRtspTimerSeconds > 0) {
    const seconds = datasetStore.autoLabelRtspTimerSeconds
    const mm = Math.floor(seconds / 60)
    const ss = seconds % 60
    rtspTimer.value = `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
  }
})

function parseRtspTimerSeconds(): number | null {
  const raw = rtspTimer.value.trim()
  if (!raw) return null
  const match = raw.match(/^(\d{1,3}):([0-5]\d)$/)
  if (!match) return null
  const minutes = Number(match[1])
  const seconds = Number(match[2])
  return (minutes * 60) + seconds
}

function start() {
  if (!selectedDataset.value) return
  timerError.value = null

  let rtspTimerSeconds: number | null = null
  if (isRtspMode.value) {
    rtspTimerSeconds = parseRtspTimerSeconds()
    if (rtspTimer.value.trim() && rtspTimerSeconds === null) {
      timerError.value = 'Timer format must be MM:SS'
      return
    }
  }

  datasetStore.toggleAutoLabel(selectedDataset.value, sampleFps.value, rtspTimerSeconds)
  emit('close')
}

function stop() {
  datasetStore.disableAutoLabel()
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="emit('close')">
    <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[420px] border border-hairline">
      <h3 class="text-[16px] font-medium text-ink mb-(--spacing-lg)">Auto-Labelling</h3>

      <template v-if="!datasetStore.autoLabelActive">
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
          <p v-if="timerError" class="mt-1 text-[11px] text-red-500">{{ timerError }}</p>
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
        <div class="p-3 rounded-(--radius-md) bg-primary/10 text-primary text-[12px] mb-(--spacing-lg)">
          Auto-labelling is active -> {{ datasetStore.autoLabelDataset }}
          <br />
          <span class="text-ink-faint">{{ datasetStore.autoLabelFps }} fps sampling</span>
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
            Stop Auto-Label
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
