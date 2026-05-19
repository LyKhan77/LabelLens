<script setup lang="ts">
import DetectionLog from './DetectionLog.vue'
import StatsGrid from './StatsGrid.vue'
</script>

<template>
  <div class="border-t border-hairline bg-canvas p-(--spacing-lg)">
    <StatsGrid />
    <div class="mt-3">
      <DetectionLog />
    </div>
  </div>
</template>
