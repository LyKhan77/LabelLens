<script setup lang="ts">
import { ref } from 'vue'
import { useInferenceStore } from '../stores/inference'
import DetectionLog from './DetectionLog.vue'
import StatsGrid from './StatsGrid.vue'

const store = useInferenceStore()
const statsPanelOpen = ref(true)
</script>

<template>
  <div class="min-w-0 min-h-0 flex-1 flex items-center justify-center bg-canvas-soft relative overflow-hidden">
    <!-- Stats toggle pill (collapsed) -->
    <button
      v-if="store.stats && store.viewerState !== 'empty' && store.viewerState !== 'loading' && !statsPanelOpen"
      class="absolute right-3 top-3 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border border-hairline bg-canvas/95 shadow-md backdrop-blur text-[11px] font-medium uppercase tracking-wider text-ink-mute hover:text-ink hover:bg-canvas transition-colors cursor-pointer"
      aria-label="Show Inference Stats"
      @click="statsPanelOpen = true"
    >
      <span class="h-1.5 w-1.5 rounded-full bg-primary" />
      Stats
    </button>
    <!-- Stats panel (expanded) -->
    <aside
      v-if="store.stats && store.viewerState !== 'empty' && store.viewerState !== 'loading' && statsPanelOpen"
      class="absolute right-3 top-3 z-10 w-[260px] max-h-[calc(100%-1.5rem)] overflow-hidden rounded-(--radius-md) border border-hairline bg-canvas/95 p-2 shadow-lg backdrop-blur"
      aria-label="Inference Stats and Detection Log"
    >
      <div class="mb-1.5 flex items-center justify-between gap-2">
        <p class="text-[11px] font-medium uppercase tracking-wider text-ink-mute">Inference Stats</p>
        <button
          class="p-0.5 rounded hover:bg-canvas-soft transition-colors cursor-pointer text-ink-mute hover:text-ink"
          aria-label="Hide Inference Stats"
          @click="statsPanelOpen = false"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <StatsGrid />
      <div class="my-2 border-t border-hairline" />
      <DetectionLog />
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
    <div v-else-if="store.viewerState === 'result'" class="w-full h-full min-h-0 flex items-center justify-center p-3 sm:p-4">
      <div class="relative inline-flex max-w-full max-h-full overflow-hidden">
        <img
          :src="`data:image/jpeg;base64,${store.resultImage}`"
          alt="Detection result"
          class="max-w-full max-h-full rounded-lg shadow-lg object-contain"
        />
      </div>
    </div>

    <!-- Video result -->
    <div v-else-if="store.viewerState === 'video'" class="w-full h-full min-h-0 flex flex-col">
      <div class="min-h-0 flex-1 flex items-center justify-center p-3 sm:p-4">
        <div class="relative inline-flex max-w-full max-h-full overflow-hidden">
          <img
            :src="`data:image/jpeg;base64,${store.videoFrames[store.videoIndex]}`"
            alt="Video frame"
            class="max-w-full max-h-full rounded-lg shadow-lg object-contain"
          />
        </div>
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
    <div v-else-if="store.viewerState === 'rtsp'" class="w-full h-full min-h-0 flex flex-col">
      <div class="min-h-0 flex-1 flex items-center justify-center p-3 sm:p-4">
        <div v-if="store.rtspFrame" class="w-full h-full min-h-0 flex items-center justify-center">
          <div class="relative inline-flex max-w-full max-h-full overflow-hidden">
            <img
              :src="`data:image/jpeg;base64,${store.rtspFrame}`"
              alt="RTSP stream"
              class="max-w-full max-h-full rounded-lg object-contain"
            />
          </div>
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
