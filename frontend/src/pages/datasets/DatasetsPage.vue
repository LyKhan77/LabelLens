<script setup lang="ts">
import { onMounted } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import { useBackendStatus } from '../../shared/composables/useBackendStatus'
import { useTheme } from '../../shared/composables/useTheme'
import DatasetList from './DatasetList.vue'
import DatasetDetail from './DatasetDetail.vue'
import ReviewPage from './ReviewPage.vue'

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()
const { yoloeStatus, samStatus } = useBackendStatus()
const { theme, toggle } = useTheme()

const emit = defineEmits<{ 'open-settings': [] }>()

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function goInference() {
  navigate('/workspace')
}

function goTrainTune() {
  navigate('/train-tune')
}

function switchMode() {
  inferenceStore.switchMode()
  navigate('/')
}

onMounted(() => {
  datasetStore.fetchProjects()
})
</script>

<template>
  <div class="h-screen bg-canvas text-ink flex flex-col">
    <!-- Normal header (gallery / project list) -->
    <header v-if="!datasetStore.reviewingImageId" class="flex items-center justify-between px-(--spacing-lg) h-14 border-b border-hairline bg-canvas shrink-0">
      <button class="flex items-center gap-2 cursor-pointer" @click="switchMode">
        <img src="/favicon.png" alt="LabelLens" class="w-7 h-7 rounded-(--radius-sm)" />
        <span class="font-bold text-lg tracking-tight">
          <span class="text-ink">Label</span><span class="text-primary">Lens</span>
        </span>
      </button>

      <div class="flex items-center gap-3">
        <button
          class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="goInference"
        >
          Inference
        </button>
        <button
          class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="goTrainTune"
        >
          Train Tune
        </button>
        <button
          class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="switchMode"
        >
          Switch Mode
        </button>

        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="yoloeStatus === 'loaded' ? 'bg-primary' : yoloeStatus === 'no-model' ? 'bg-yellow-500' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ yoloeStatus === 'loaded' ? 'YOLOE Ready' : yoloeStatus === 'no-model' ? 'YOLOE Idle' : 'Offline' }}</span>
        </div>
        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="samStatus === 'loaded' ? 'bg-primary' : samStatus === 'available' ? 'bg-yellow-500' : samStatus === 'disabled' ? 'bg-gray-400' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ samStatus === 'loaded' ? 'SAM Ready' : samStatus === 'available' ? 'SAM Idle' : samStatus === 'disabled' ? 'SAM Off' : 'Offline' }}</span>
        </div>

        <button
          class="p-1.5 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer"
          :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggle()"
        >
          <svg v-if="theme === 'dark'" class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5" />
            <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
          <svg v-else class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </button>

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
      </div>
    </header>

    <!-- Review-mode header (compact toolbar) -->
    <header v-else class="flex items-center justify-between px-(--spacing-lg) h-12 border-b border-hairline bg-canvas shrink-0">
      <button
        class="flex items-center gap-2 text-[12px] text-primary font-medium cursor-pointer hover:text-primary-deep transition-colors"
        @click="datasetStore.exitReview()"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back to Gallery
      </button>

      <div class="flex items-center gap-3">
        <button
          class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="goInference"
        >
          Inference
        </button>
        <button
          class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="goTrainTune"
        >
          Train Tune
        </button>
        <button
          class="px-2 py-1 text-xs rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="switchMode"
        >
          Switch Mode
        </button>

        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="yoloeStatus === 'loaded' ? 'bg-primary' : yoloeStatus === 'no-model' ? 'bg-yellow-500' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ yoloeStatus === 'loaded' ? 'YOLOE Ready' : yoloeStatus === 'no-model' ? 'YOLOE Idle' : 'Offline' }}</span>
        </div>
        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="samStatus === 'loaded' ? 'bg-primary' : samStatus === 'available' ? 'bg-yellow-500' : samStatus === 'disabled' ? 'bg-gray-400' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ samStatus === 'loaded' ? 'SAM Ready' : samStatus === 'available' ? 'SAM Idle' : samStatus === 'disabled' ? 'SAM Off' : 'Offline' }}</span>
        </div>

        <button
          class="p-1.5 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer"
          :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggle()"
        >
          <svg v-if="theme === 'dark'" class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5" />
            <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
          <svg v-else class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </button>
      </div>
    </header>

    <!-- Gallery view (v-show preserves scroll + local state) -->
    <main class="dataset-page-main" v-show="!datasetStore.reviewingImageId">
      <DatasetDetail v-if="datasetStore.currentProject" />
      <DatasetList v-else />
    </main>

    <!-- Full-page review view -->
    <ReviewPage
      v-if="datasetStore.reviewingImageId"
      @back="datasetStore.exitReview()"
    />
  </div>
</template>
