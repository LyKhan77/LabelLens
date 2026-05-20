<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useInferenceStore } from '../../shared/stores/inference'
import { useDatasetStore } from '../../shared/stores/dataset'
import type { InferenceMode } from '../../shared/types'
import DatasetList from '../datasets/DatasetList.vue'
import DatasetDetail from '../datasets/DatasetDetail.vue'

const store = useInferenceStore()
const datasetStore = useDatasetStore()

const activeTab = ref<'inference' | 'datasets'>('inference')

interface ModeCard {
  mode: InferenceMode
  title: string
  desc: string
  model: string
}

const MODES: ModeCard[] = [
  {
    mode: 'free',
    title: 'Free Inference',
    desc: 'Detect all visible objects automatically using YOLOE\'s internal vocabulary — 1,200+ LVIS categories. No prompts needed.',
    model: 'yoloe-26l-seg-pf.pt',
  },
  {
    mode: 'prompt',
    title: 'Prompt Inference',
    desc: 'Detect specific objects using text labels or visual reference images with bounding box annotations via SAVPE encoder.',
    model: 'yoloe-26l-seg.pt',
  },
]

function select(mode: InferenceMode) {
  if (store.modelLoading) return
  store.selectMode(mode)
}

function isLoading(m: ModeCard) {
  return store.modelLoading && store.loadingMode === m.mode
}

function switchTab(tab: 'inference' | 'datasets') {
  activeTab.value = tab
  if (tab === 'datasets') {
    datasetStore.fetchProjects()
    datasetStore.currentProject = null
    datasetStore.clearSelection()
  }
}

onMounted(() => {
  datasetStore.fetchProjects()
})
</script>

<template>
  <div class="flex items-center justify-center min-h-screen bg-canvas">
    <div class="w-full max-w-[1200px] px-(--spacing-xl)">
      <!-- Header -->
      <div class="text-center mb-(--spacing-lg)">
        <div class="flex items-center justify-center gap-3 mb-(--spacing-md)">
          <img src="/favicon.png" alt="LabelLens" class="w-12 h-12 rounded-(--radius-md)" />
          <span class="text-[36px] font-bold tracking-[-0.72px]">
            <span class="text-ink">Label</span><span class="text-primary">Lens</span>
          </span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex justify-center gap-0 mb-(--spacing-lg) border-b border-hairline">
        <button
          @click="switchTab('inference')"
          class="px-6 py-3 text-[14px] font-medium transition-colors relative"
          :class="activeTab === 'inference' ? 'text-primary' : 'text-ink-faint hover:text-ink-mute'"
        >
          Inference
          <span v-if="activeTab === 'inference'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
        </button>
        <button
          @click="switchTab('datasets')"
          class="px-6 py-3 text-[14px] font-medium transition-colors relative"
          :class="activeTab === 'datasets' ? 'text-primary' : 'text-ink-faint hover:text-ink-mute'"
        >
          Datasets
          <span v-if="activeTab === 'datasets'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
        </button>
      </div>

      <!-- Tab content -->
      <div class="flex justify-center">
        <!-- Inference tab -->
        <template v-if="activeTab === 'inference'">
          <div class="w-full max-w-[680px]">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-(--spacing-lg)">
              <button
                v-for="m in MODES"
                :key="m.mode"
                @click="select(m.mode)"
                :disabled="store.modelLoading"
                class="group relative flex flex-col items-start p-(--spacing-xxl) rounded-(--radius-lg) border border-hairline bg-canvas transition-all duration-150 text-left cursor-pointer"
                :class="[
                  isLoading(m)
                    ? 'border-primary/50'
                    : 'hover:border-hairline-strong hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)]'
                ]"
              >
                <!-- Loading overlay -->
                <div
                  v-if="isLoading(m)"
                  class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/95 rounded-(--radius-lg) z-10"
                >
                  <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mb-(--spacing-md)" />
                  <p class="text-[12px] text-ink-mute font-mono">{{ m.model }}</p>
                </div>

                <!-- Error overlay -->
                <div
                  v-if="store.modelError && store.loadingMode === null && !store.modelLoaded && !isLoading(m)"
                  class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/95 rounded-(--radius-lg) z-10 px-(--spacing-lg)"
                >
                  <svg class="w-5 h-5 text-red-500 mb-(--spacing-sm)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="15" y1="9" x2="9" y2="15" />
                    <line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  <p class="text-[12px] text-ink-mute text-center leading-[1.45]">{{ store.modelError }}</p>
                  <p class="text-[12px] text-primary mt-(--spacing-xs)">Click to retry</p>
                </div>

                <!-- Icon: Free mode — scan/eye -->
                <div v-if="m.mode === 'free'" class="mb-(--spacing-lg)">
                  <svg class="w-6 h-6 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </div>

                <!-- Icon: Prompt mode — target/crosshair -->
                <div v-else class="mb-(--spacing-lg)">
                  <svg class="w-6 h-6 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <circle cx="12" cy="12" r="6" />
                    <circle cx="12" cy="12" r="2" />
                  </svg>
                </div>

                <!-- Card content -->
                <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-xs)">
                  {{ m.title }}
                </h2>
                <p class="text-[13px] text-ink-mute leading-[1.45] mb-(--spacing-lg)">
                  {{ m.desc }}
                </p>
                <span class="text-[12px] font-mono text-ink-faint">{{ m.model }}</span>
              </button>
            </div>

            <!-- Footer hint -->
            <p class="text-center text-[12px] text-ink-faint mt-(--spacing-xxl) leading-[1.45]">
              Model loads into GPU memory. Switch modes anytime via the header.
            </p>
          </div>
        </template>

        <!-- Datasets tab -->
        <template v-if="activeTab === 'datasets'">
          <DatasetDetail v-if="datasetStore.currentProject" />
          <DatasetList v-else />
        </template>
      </div>
    </div>
  </div>
</template>
