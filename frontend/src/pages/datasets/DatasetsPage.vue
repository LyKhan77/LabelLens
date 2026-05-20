<script setup lang="ts">
import { onMounted } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import { useBackendStatus } from '../../shared/composables/useBackendStatus'
import { useTheme } from '../../shared/composables/useTheme'
import DatasetList from './DatasetList.vue'
import DatasetDetail from './DatasetDetail.vue'

const datasetStore = useDatasetStore()
const inferenceStore = useInferenceStore()
const { connected } = useBackendStatus()
const { theme, toggle } = useTheme()

function goHome() {
  window.history.pushState({}, '', '/')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

onMounted(() => {
  datasetStore.fetchProjects()
})
</script>

<template>
  <div class="min-h-screen bg-canvas text-ink flex flex-col">
    <!-- Glassmorphic Topbar -->
    <header class="h-[60px] border-b border-hairline bg-canvas/70 backdrop-blur-xl flex items-center justify-between px-6 shrink-0 sticky top-0 z-50">
      <button class="flex items-center gap-2.5 cursor-pointer" @click="goHome">
        <div class="w-7 h-7 rounded-(--radius-sm) bg-gradient-to-br from-primary to-primary-deep grid place-items-center shadow-[0_0_12px_rgba(62,207,142,0.2)]">
          <span class="text-[10px] font-black text-on-primary leading-none">LL</span>
        </div>
        <span class="font-bold text-[17px] tracking-tight">
          <span class="text-ink">Label</span><span class="text-primary">Lens</span>
        </span>
      </button>

      <div class="flex items-center gap-2.5">
        <!-- CUDA Status Chip -->
        <span class="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono font-medium text-ink-mute border border-hairline rounded-(--radius-sm) bg-canvas-soft px-2.5 py-1.5">
          <span class="w-[7px] h-[7px] rounded-full animate-pulse" :class="connected ? 'bg-primary shadow-[0_0_8px_var(--color-primary)]' : 'bg-red-500'" />
          {{ connected ? 'CUDA: 0' : 'Offline' }}
        </span>
        <!-- Model Chip -->
        <span v-if="inferenceStore.modelLoaded" class="hidden md:inline-flex items-center text-[11px] font-mono font-medium text-ink-mute border border-hairline rounded-(--radius-sm) bg-canvas-soft px-2.5 py-1.5">
          YOLOE-26L
        </span>
        <button
          class="px-2.5 py-1.5 text-[12px] rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          @click="goHome"
        >
          Inference
        </button>
        <button
          class="w-8 h-8 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer flex items-center justify-center"
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

    <main class="flex-1 min-h-0 overflow-y-auto px-(--spacing-lg) py-(--spacing-xl)">
      <DatasetDetail v-if="datasetStore.currentProject" />
      <DatasetList v-else />
    </main>
  </div>
</template>
