<script setup lang="ts">
import DetectionLog from './DetectionLog.vue'
import StatsGrid from './StatsGrid.vue'
</script>

<template>
  <div class="border-t border-hairline bg-canvas px-3 py-2">
    <div class="flex flex-col gap-2 lg:flex-row lg:items-start">
      <div class="shrink-0 lg:w-[360px]">
        <StatsGrid />
      </div>
      <div class="min-w-0 flex-1">
        <DetectionLog />
      </div>
    </div>
  </div>
</template>
