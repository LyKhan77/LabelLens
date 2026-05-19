<script setup lang="ts">
import { onMounted } from 'vue'
import { useInferenceStore } from '../shared/stores/inference'
import ModeSelectPage from '../pages/mode-select/ModeSelectPage.vue'
import WorkspacePage from '../pages/workspace/WorkspacePage.vue'

const store = useInferenceStore()

onMounted(() => {
  store.loadModelStatus()
})
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas">
    <WorkspacePage v-if="store.modelLoaded" />
    <ModeSelectPage v-else />
  </div>
</template>
