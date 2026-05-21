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
const { connected } = useBackendStatus()
const { theme, toggle } = useTheme()

function goInference() {
  window.history.pushState({}, '', '/')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function switchMode() {
  inferenceStore.switchMode()
  goInference()
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
          @click="switchMode"
        >
          Switch Mode
        </button>

        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="connected ? 'bg-primary' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ connected ? 'Backend Connected' : 'Backend Offline' }}</span>
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
          @click="switchMode"
        >
          Switch Mode
        </button>

        <div class="hidden sm:flex items-center gap-2">
          <span class="w-2 h-2 rounded-full transition-colors" :class="connected ? 'bg-primary' : 'bg-red-500'" />
          <span class="text-xs text-ink-mute">{{ connected ? 'Backend Connected' : 'Backend Offline' }}</span>
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
