<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useInferenceStore } from '../../shared/stores/inference'
import { useTestModel } from '../../shared/composables/useTestModel'
import TestSidebar from './components/TestSidebar.vue'
import Viewer from '../workspace/components/Viewer.vue'
import AutoLabelModal from '../workspace/components/AutoLabelModal.vue'

const props = defineProps<{ modelId: string }>()

const store = useInferenceStore()
const { loadTestModel, loaded, reset } = useTestModel()
const showAutoLabelModal = ref(false)

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

onMounted(async () => {
  store.reset()
  store.inferenceMode = 'free'
  await loadTestModel(props.modelId)
})

onUnmounted(() => {
  store.reset()
  reset()
})
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas text-ink">
    <!-- Header -->
    <header class="flex items-center justify-between px-4 h-12 border-b border-hairline bg-canvas shrink-0">
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-1.5 text-xs font-medium text-primary-deep cursor-pointer hover:underline"
          @click="navigate('/train-tune/results/' + props.modelId)"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6" /></svg>
          <span>Back to Results</span>
        </button>
        <span class="text-ink-mute">|</span>
        <span class="text-sm font-medium text-ink">Test Model</span>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full"
          :class="loaded ? 'bg-emerald-500' : 'bg-yellow-500'"
        />
        <span class="text-xs text-ink-mute">{{ loaded ? 'Model Ready' : 'Loading Model...' }}</span>
      </div>
    </header>

    <!-- Body: Sidebar + Viewer -->
    <div class="flex flex-1 min-h-0 overflow-hidden">
      <TestSidebar @open-auto-label="showAutoLabelModal = true" />
      <Viewer />
    </div>

    <!-- Auto-label modal (reused from workspace) -->
    <AutoLabelModal v-if="showAutoLabelModal" @close="showAutoLabelModal = false" />
  </div>
</template>
