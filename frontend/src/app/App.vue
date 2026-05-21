<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useInferenceStore } from '../shared/stores/inference'
import ModeSelectPage from '../pages/mode-select/ModeSelectPage.vue'
import WorkspacePage from '../pages/workspace/WorkspacePage.vue'
import DatasetsPage from '../pages/datasets/DatasetsPage.vue'

const store = useInferenceStore()
const path = ref(window.location.pathname)

function syncPath() {
  path.value = window.location.pathname
}

onMounted(() => {
  store.loadModelStatus()
  window.addEventListener('popstate', syncPath)
})

onUnmounted(() => window.removeEventListener('popstate', syncPath))
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas">
    <DatasetsPage v-if="path === '/datasets'" />
    <WorkspacePage v-else-if="path === '/workspace' && store.modelLoaded" />
    <ModeSelectPage v-else />
  </div>
</template>
