<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'
import StatsGrid from './StatsGrid.vue'

const store = useInferenceStore()
</script>

<template>
  <div class="flex-1 flex items-center justify-center bg-canvas-soft relative overflow-hidden">
    <aside
      v-if="store.stats && store.viewerState !== 'empty' && store.viewerState !== 'loading'"
      class="absolute right-3 top-3 z-10 w-[210px] rounded-(--radius-md) border border-hairline bg-canvas/95 p-2 shadow-lg backdrop-blur"
      aria-label="Inference Stats"
    >
      <div class="mb-1.5 flex items-center justify-between gap-2">
        <p class="text-[11px] font-medium uppercase tracking-wider text-ink-mute">Inference Stats</p>
        <span class="h-1.5 w-1.5 rounded-full bg-primary" />
      </div>
      <StatsGrid />
    </aside>
    <!-- Empty state -->
    <div v-if="store.viewerState === 'empty'" class="text-center">
      <svg class="w-16 h-16 mx-auto mb-3 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <path d="m21 15-5-5L5 21" />
      </svg>
      <p class="text-ink-mute text-sm">Upload media and run inference to see results</p>
      <p v-if="store.error" class="text-red-500 text-xs mt-2">{{ store.error }}</p>
    </div>

    <!-- Loading state -->
    <div v-else-if="store.viewerState === 'loading'" class="text-center">
      <div class="w-10 h-10 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
      <p class="text-ink-mute text-sm mb-3">Running inference...</p>
      <button
        class="px-4 py-1.5 text-sm font-medium rounded-sm border border-hairline text-ink-mute hover:text-ink hover:bg-canvas transition-colors"
        @click="store.stopInference()"
      >
        Cancel
      </button>
    </div>

    <!-- Image result -->
    <div v-else-if="store.viewerState === 'result'" class="w-full h-full flex items-center justify-center p-4">
      <img
        :src="`data:image/jpeg;base64,${store.resultImage}`"
        alt="Detection result"
        class="max-w-full max-h-full rounded-lg shadow-lg object-contain"
      />
    </div>

    <!-- Video result -->
    <div v-else-if="store.viewerState === 'video'" class="w-full h-full flex flex-col">
      <div class="flex-1 flex items-center justify-center p-4">
        <img
          :src="`data:image/jpeg;base64,${store.videoFrames[store.videoIndex]}`"
          alt="Video frame"
          class="max-w-full max-h-full rounded-lg shadow-lg object-contain"
        />
      </div>
      <!-- Video controls -->
      <div class="flex items-center gap-2 px-4 py-2 border-t border-hairline bg-canvas">
        <button
          class="px-2 py-1 text-sm rounded-xs border border-hairline hover:bg-canvas-soft transition-colors"
          @click="store.videoPlaying ? store.stopVideo() : store.playVideo()"
        >
          {{ store.videoPlaying ? 'Pause' : 'Play' }}
        </button>
        <div class="flex-1">
          <input
            v-model.number="store.videoIndex"
            type="range"
            min="0"
            :max="store.videoFrames.length - 1"
            class="w-full h-1 rounded-full appearance-none bg-hairline-cool accent-primary cursor-pointer"
          />
        </div>
        <span class="text-xs text-ink-mute font-mono">
          {{ store.videoIndex + 1 }} / {{ store.videoFrames.length }}
        </span>
      </div>
    </div>

    <!-- RTSP result -->
    <div v-else-if="store.viewerState === 'rtsp'" class="w-full h-full flex flex-col">
      <div class="flex-1 flex items-center justify-center p-4">
        <div v-if="store.rtspFrame" class="w-full h-full flex items-center justify-center">
          <img
            :src="`data:image/jpeg;base64,${store.rtspFrame}`"
            alt="RTSP stream"
            class="max-w-full max-h-full rounded-lg object-contain"
          />
        </div>
        <div v-else class="text-center">
          <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p class="text-ink-mute text-sm">Connecting to stream...</p>
          <p v-if="store.error" class="text-red-500 text-xs mt-1">{{ store.error }}</p>
        </div>
      </div>
      <!-- RTSP status bar -->
      <div class="flex items-center gap-2 px-4 py-2 border-t border-hairline bg-canvas">
        <span
          class="w-2 h-2 rounded-full"
          :class="store.rtspConnected ? 'bg-primary animate-pulse' : 'bg-red-500'"
        />
        <span class="text-xs text-ink-mute">
          {{ store.rtspConnected ? 'Live' : 'Disconnected' }}
        </span>
        <span v-if="store.stats?.inference_ms" class="text-xs text-ink-faint font-mono ml-auto">
          {{ store.stats.inference_ms.toFixed(0) }} ms/frame
        </span>
      </div>
    </div>
  </div>
</template>
