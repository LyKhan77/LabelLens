<script setup lang="ts">
import { onMounted } from 'vue'
import { useInferenceStore } from './stores/inference'
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/Sidebar.vue'
import Viewer from './components/Viewer.vue'
import FeatureModes from './components/FeatureModes.vue'

const store = useInferenceStore()

onMounted(() => {
  store.loadModelStatus()
})
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas">
    <template v-if="store.modelLoaded">
      <AppHeader />
      <div class="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar />
        <Viewer />
      </div>
    </template>
    <FeatureModes v-else />
  </div>
</template>
