<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'
import ImageUpload from './ImageUpload.vue'
import VideoUpload from './VideoUpload.vue'
import RtspInput from './RtspInput.vue'

const store = useInferenceStore()

const modes = [
  { key: 'image' as const, label: 'Image' },
  { key: 'video' as const, label: 'Video' },
  { key: 'rtsp' as const, label: 'RTSP' },
]
</script>

<template>
  <div>
    <p class="text-xs font-medium text-ink-mute uppercase tracking-wider mb-2">
      Step 2 — Media Input
    </p>

    <!-- Tab toggle -->
    <div class="flex rounded-(--radius-sm) border border-hairline overflow-hidden mb-3">
      <button
        v-for="mode in modes"
        :key="mode.key"
        class="flex-1 px-3 py-1.5 text-sm font-medium transition-colors"
        :class="store.mediaMode === mode.key
          ? 'bg-canvas-night text-on-dark'
          : 'bg-canvas text-ink-mute hover:text-ink'"
        @click="store.mediaMode = mode.key"
      >
        {{ mode.label }}
      </button>
    </div>

    <ImageUpload v-if="store.mediaMode === 'image'" />
    <VideoUpload v-else-if="store.mediaMode === 'video'" />
    <RtspInput v-else />
  </div>
</template>
