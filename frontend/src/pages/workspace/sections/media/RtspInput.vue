<script setup lang="ts">
import { useInferenceStore } from '../../../../shared/stores/inference'

const store = useInferenceStore()
</script>

<template>
  <div>
    <label class="text-sm font-medium text-ink mb-1 block">RTSP Stream URL</label>
    <div class="flex gap-1.5">
      <input
        v-model="store.rtspUrl"
        type="text"
        placeholder="rtsp://admin:password@192.168.1.100:554/stream"
        class="flex-1 px-(--spacing-sm) py-1.5 text-sm rounded-(--radius-sm) border border-hairline bg-canvas text-ink placeholder:text-ink-faint focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 font-mono"
      />
    </div>
    <p class="text-xs text-ink-faint mt-1">
      Enter a valid RTSP URL to connect to a live stream
    </p>
  </div>
</template>
