<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useTrainingStore } from '../../shared/stores/training'
import type { ModelVersion, TrainingTaskType } from '../../shared/api/training'

defineEmits<{ 'open-settings': [] }>()

const trainingStore = useTrainingStore()
const loading = ref(true)
const search = ref('')
const selectedId = ref<string | null>(null)

const taskMeta: Record<string, { label: string; badge: string; cls: string }> = {
  detect: { label: 'Detection', badge: 'DET', cls: 'bg-blue-500/10 text-blue-600' },
  segment: { label: 'Segmentation', badge: 'SEG', cls: 'bg-purple-500/10 text-purple-600' },
  pose: { label: 'Pose', badge: 'POSE', cls: 'bg-amber-500/10 text-amber-600' },
  classify_single: { label: 'Classification', badge: 'CLS', cls: 'bg-emerald-500/10 text-emerald-600' },
}

function meta(task: TrainingTaskType | string) {
  return taskMeta[task] ?? { label: 'Detection', badge: 'DET', cls: 'bg-blue-500/10 text-blue-600' }
}

const filtered = computed<ModelVersion[]>(() => {
  const q = search.value.trim().toLowerCase()
  const list = trainingStore.models
  if (!q) return list
  return list.filter((m) =>
    m.model_name.toLowerCase().includes(q) ||
    m.version_name.toLowerCase().includes(q) ||
    meta(m.task_type).label.toLowerCase().includes(q),
  )
})

const selected = computed<ModelVersion | null>(
  () => trainingStore.models.find((m) => m.id === selectedId.value) ?? null,
)

function bestMetric(m: ModelVersion): string {
  const b = m.metrics_best
  if (!b) return '—'
  if (b.map50 > 0) return `mAP50 ${b.map50.toFixed(2)}`
  if (b.precision > 0) return `P ${b.precision.toFixed(2)}`
  return '—'
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString()
}

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function testModel() {
  if (selected.value) navigate(`/train-tune/test/${selected.value.id}`)
}

onMounted(async () => {
  try {
    await trainingStore.refreshModels()
    selectedId.value = trainingStore.models[0]?.id ?? null
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas text-ink">
    <!-- Header -->
    <header class="flex items-center justify-between px-4 h-12 border-b border-hairline bg-canvas shrink-0">
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-1.5 text-xs font-medium text-primary-deep cursor-pointer hover:underline"
          @click="navigate('/')"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6" /></svg>
          <span>Home</span>
        </button>
        <span class="text-ink-mute">|</span>
        <span class="text-sm font-medium text-ink">Test Model</span>
      </div>
      <button
        class="p-1.5 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer"
        title="GPU Settings"
        @click="$emit('open-settings')"
      >
        <svg class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </button>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Empty -->
    <div v-else-if="trainingStore.models.length === 0" class="flex-1 flex flex-col items-center justify-center gap-3 text-center px-6">
      <p class="text-sm text-ink-mute">No model versions yet. Train a model first.</p>
      <button
        class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 cursor-pointer"
        @click="navigate('/train-tune')"
      >
        Go to Train Tune
      </button>
    </div>

    <!-- Master-detail -->
    <div v-else class="flex flex-1 min-h-0 overflow-hidden">
      <!-- List -->
      <aside class="w-72 shrink-0 border-r border-hairline bg-canvas flex flex-col">
        <div class="p-3 border-b border-hairline">
          <input
            v-model="search"
            type="text"
            placeholder="Search model versions..."
            class="w-full text-xs px-2.5 py-2 rounded-(--radius-md) border border-hairline bg-canvas text-ink focus:outline-none focus:border-primary"
          />
        </div>
        <div class="flex-1 overflow-y-auto p-2 space-y-1">
          <button
            v-for="m in filtered"
            :key="m.id"
            @click="selectedId = m.id"
            class="w-full text-left px-3 py-2.5 rounded-(--radius-md) border transition-colors cursor-pointer"
            :class="selectedId === m.id ? 'border-primary/50 bg-primary/5' : 'border-hairline hover:bg-canvas-soft'"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="min-w-0 truncate text-[13px] font-medium text-ink">{{ m.version_name }}</span>
              <span class="shrink-0 px-1.5 py-0.5 text-[10px] font-semibold rounded" :class="meta(m.task_type).cls">{{ meta(m.task_type).badge }}</span>
            </div>
            <div class="mt-1 flex items-center justify-between gap-2 text-[11px] text-ink-mute">
              <span class="font-mono">{{ m.family }}{{ m.size }}</span>
              <span>{{ bestMetric(m) }}</span>
            </div>
            <p class="mt-0.5 text-[10px] text-ink-faint">{{ fmtDate(m.created_at) }}</p>
          </button>
          <p v-if="filtered.length === 0" class="px-2 py-3 text-xs text-ink-faint">No matches.</p>
        </div>
      </aside>

      <!-- Detail -->
      <section class="flex-1 min-w-0 overflow-y-auto">
        <div v-if="selected" class="max-w-[640px] mx-auto p-6 space-y-5">
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-[20px] font-semibold text-ink tracking-[-0.4px]">{{ selected.version_name }}</h1>
              <span class="px-2 py-0.5 text-[11px] font-semibold rounded" :class="meta(selected.task_type).cls">{{ meta(selected.task_type).label }}</span>
            </div>
            <p class="mt-1 text-[12px] text-ink-mute font-mono">{{ selected.model_name }}</p>
          </div>

          <div class="grid grid-cols-2 gap-px overflow-hidden rounded-(--radius-md) border border-hairline bg-hairline">
            <div class="bg-canvas px-3 py-2.5">
              <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">Architecture</p>
              <p class="text-sm font-semibold text-ink">{{ selected.family }} {{ selected.size }}</p>
            </div>
            <div class="bg-canvas px-3 py-2.5">
              <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">Classes</p>
              <p class="text-sm font-semibold text-ink">{{ selected.class_names.length }}</p>
            </div>
            <div class="bg-canvas px-3 py-2.5">
              <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">mAP50</p>
              <p class="text-sm font-semibold text-ink">{{ selected.metrics_best ? selected.metrics_best.map50.toFixed(3) : '—' }}</p>
            </div>
            <div class="bg-canvas px-3 py-2.5">
              <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute">mAP50-95</p>
              <p class="text-sm font-semibold text-ink">{{ selected.metrics_best ? selected.metrics_best.map50_95.toFixed(3) : '—' }}</p>
            </div>
          </div>

          <div>
            <p class="text-[10px] font-medium uppercase tracking-wider text-ink-mute mb-1.5">Classes</p>
            <div class="flex flex-wrap gap-1">
              <span v-for="cls in selected.class_names" :key="cls" class="px-1.5 py-0.5 text-[11px] rounded bg-canvas-soft border border-hairline text-ink-mute">{{ cls }}</span>
              <span v-if="selected.class_names.length === 0" class="text-[12px] text-ink-faint">No classes recorded</span>
            </div>
          </div>

          <div class="text-[12px] text-ink-mute space-y-1">
            <p>Source dataset version: <span class="font-mono text-ink">{{ selected.dataset_version_id }}</span></p>
            <p>Created: <span class="text-ink">{{ fmtDate(selected.created_at) }}</span></p>
          </div>

          <button
            class="w-full py-2.5 text-sm font-medium rounded-(--radius-md) text-white bg-emerald-500 hover:bg-emerald-600 transition-colors cursor-pointer flex items-center justify-center gap-2"
            @click="testModel"
          >
            Test Model
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6" /></svg>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
