<script setup lang="ts">
import { ref } from 'vue'
import { useDatasetStore } from '../../../shared/stores/dataset'
import GroundingInput from '../sections/grounding/GroundingInput.vue'
import MediaInput from '../sections/media/MediaInput.vue'
import SettingsPanel from '../sections/settings/SettingsPanel.vue'
import AutoLabelModal from './AutoLabelModal.vue'

const collapsed = ref(false)
const showAutoLabelModal = ref(false)
const datasetStore = useDatasetStore()
</script>

<template>
  <aside
    class="shrink-0 border-r border-hairline bg-canvas h-full transition-[width] duration-200 overflow-hidden"
    :class="collapsed ? 'w-12' : 'w-[380px]'"
  >
    <div v-show="collapsed" class="h-full flex flex-col items-center py-3">
      <button
        type="button"
        class="w-9 h-9 flex items-center justify-center rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
        aria-label="Expand controls"
        title="Expand controls"
        @click="collapsed = false"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m9 18 6-6-6-6" />
        </svg>
      </button>
      <span class="mt-3 rotate-180 text-[11px] font-medium uppercase tracking-wider text-ink-mute" style="writing-mode: vertical-rl;">
        Controls
      </span>
    </div>

    <div v-show="!collapsed" class="h-full overflow-y-auto">
      <div class="p-(--spacing-lg) space-y-(--spacing-xl)">
        <div class="flex items-center justify-between gap-3">
          <p class="text-xs font-medium text-ink-mute uppercase tracking-wider">Controls</p>
          <button
            type="button"
            class="w-8 h-8 flex items-center justify-center rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
            aria-label="Collapse controls"
            title="Collapse controls"
            @click="collapsed = true"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m15 18-6-6 6-6" />
            </svg>
          </button>
        </div>

        <GroundingInput />

        <hr class="border-hairline" />

        <MediaInput />

        <hr class="border-hairline" />

        <SettingsPanel />

        <hr class="border-hairline" />

        <!-- Auto-Labelling -->
        <div>
          <p class="text-xs font-medium text-ink-mute uppercase tracking-wider mb-2">Dataset</p>
          <button
            @click="showAutoLabelModal = true"
            class="w-full flex items-center justify-between px-3 py-2 text-[12px] rounded-(--radius-md) border transition-colors"
            :class="datasetStore.autoLabelActive ? 'border-primary/50 bg-primary/5 text-primary' : 'border-hairline text-ink-mute hover:border-hairline-strong'"
          >
            <span>{{ datasetStore.autoLabelActive ? `Auto-Label → ${datasetStore.autoLabelDataset}` : 'Auto-Label' }}</span>
            <span v-if="datasetStore.autoLabelActive" class="w-2 h-2 rounded-full bg-primary animate-pulse" />
          </button>
        </div>
      </div>
    </div>

    <AutoLabelModal v-if="showAutoLabelModal" @close="showAutoLabelModal = false" />
  </aside>
</template>
