<script setup lang="ts">
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/Sidebar.vue'
import Viewer from './components/Viewer.vue'
import MetricsBar from './components/MetricsBar.vue'
</script>

<template>
  <div class="h-screen flex flex-col bg-canvas">
    <AppHeader />
    <div class="flex flex-1 overflow-hidden">
      <Sidebar />
      <div class="flex-1 flex flex-col">
        <Viewer />
        <MetricsBar />
      </div>
    </div>
  </div>
</template>
