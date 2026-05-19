<script setup lang="ts">
import { computed } from 'vue'
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

const clearHint = computed(() => {
  if (store.isRunning) return 'Stop inference before clearing media'
  if (store.hasMediaInput) return 'Clear Media to switch input mode'
  return ''
})
</script>

<template>
  <div>
    <div class="mb-2 flex items-center justify-between gap-2">
      <p class="text-xs font-medium text-ink-mute uppercase tracking-wider">
        Step 2 — Media Input
      </p>
      <button
        type="button"
        class="px-2 py-1 text-xs font-medium rounded-(--radius-xs) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        :disabled="store.isRunning || !store.hasMediaInput"
        @click="store.clearMediaInput()"
      >
        Clear Media
      </button>
    </div>

    <!-- Tab toggle -->
    <div class="flex rounded-(--radius-sm) border border-hairline overflow-hidden mb-2">
      <button
        v-for="mode in modes"
        :key="mode.key"
        class="flex-1 px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45"
        :class="store.mediaMode === mode.key
          ? 'bg-primary text-on-primary'
          : 'bg-canvas text-ink-mute hover:text-ink'"
        :disabled="!store.canSwitchMediaMode && store.mediaMode !== mode.key"
        @click="store.selectMediaMode(mode.key)"
      >
        {{ mode.label }}
      </button>
    </div>

    <p v-if="clearHint" class="mb-2 text-xs text-ink-faint">{{ clearHint }}</p>

    <ImageUpload v-if="store.mediaMode === 'image'" />
    <VideoUpload v-else-if="store.mediaMode === 'video'" />
    <RtspInput v-else />
  </div>
</template>
