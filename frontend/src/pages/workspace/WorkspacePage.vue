<script setup lang="ts">
import AppHeader from './components/AppHeader.vue'
import Sidebar from './components/Sidebar.vue'
import Viewer from './components/Viewer.vue'

defineEmits<{ 'open-settings': [] }>()
</script>

<template>
  <AppHeader @open-settings="$emit('open-settings')" />
  <div class="flex flex-1 min-h-0 overflow-hidden">
    <Sidebar />
    <Viewer />
  </div>
</template>
