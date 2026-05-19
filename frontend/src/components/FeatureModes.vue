<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'
import type { InferenceMode } from '../types'

const store = useInferenceStore()

const MODES: { mode: InferenceMode; icon: string; title: string; desc: string; model: string }[] = [
  {
    mode: 'free',
    icon: '🔍',
    title: 'Free Inference',
    desc: 'Detect all visible objects automatically using YOLOE\'s internal vocabulary (1200+ LVIS categories). No prompts needed.',
    model: 'yoloe-26l-seg-pf.pt',
  },
  {
    mode: 'prompt',
    icon: '🎯',
    title: 'Prompt Inference',
    desc: 'Detect specific objects using text labels or visual reference images with bounding box annotations.',
    model: 'yoloe-26l-seg.pt',
  },
]

function select(mode: InferenceMode) {
  if (store.modelLoading) return
  store.selectMode(mode)
}
</script>

<template>
  <div class="flex items-center justify-center min-h-screen bg-canvas p-8">
    <div class="w-full max-w-2xl">
      <div class="text-center mb-12">
        <h1 class="text-3xl font-bold text-ink mb-2">LabelLens</h1>
        <p class="text-ink-mute">Select an inference mode to get started</p>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <button
          v-for="m in MODES"
          :key="m.mode"
          @click="select(m.mode)"
          :disabled="store.modelLoading"
          class="group relative flex flex-col items-start p-6 rounded-xl border-2 transition-all duration-200 text-left cursor-pointer"
          :class="[
            store.modelLoading && store.inferenceMode !== m.mode
              ? 'border-hairline opacity-40 cursor-not-allowed'
              : 'border-hairline hover:border-primary hover:shadow-lg'
          ]"
        >
          <!-- Loading state -->
          <div v-if="store.modelLoading && store.inferenceMode === m.mode" class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/90 rounded-xl z-10">
            <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-3" />
            <p class="text-sm text-ink-mute">Loading {{ m.model }}...</p>
          </div>

          <!-- Error state -->
          <div v-if="store.modelError && store.inferenceMode === m.mode" class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/90 rounded-xl z-10">
            <p class="text-sm text-red-500 text-center px-4 mb-2">{{ store.modelError }}</p>
            <p class="text-xs text-ink-mute">Click to retry</p>
          </div>

          <span class="text-2xl mb-3">{{ m.icon }}</span>
          <h2 class="text-lg font-semibold text-ink mb-1">{{ m.title }}</h2>
          <p class="text-sm text-ink-mute leading-relaxed">{{ m.desc }}</p>
          <span class="mt-3 text-xs font-mono text-ink-faint">{{ m.model }}</span>
        </button>
      </div>

      <p class="text-center text-xs text-ink-faint mt-8">
        Model loads into GPU memory. Switching modes requires returning to this page.
      </p>
    </div>
  </div>
</template>
