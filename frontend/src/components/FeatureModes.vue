<script setup lang="ts">
import { useInferenceStore } from '../stores/inference'
import type { InferenceMode } from '../types'

const store = useInferenceStore()

interface ModeCard {
  mode: InferenceMode
  title: string
  desc: string
  model: string
}

const MODES: ModeCard[] = [
  {
    mode: 'free',
    title: 'Free Inference',
    desc: 'Detect all visible objects automatically using YOLOE\'s internal vocabulary — 1,200+ LVIS categories. No prompts needed.',
    model: 'yoloe-26l-seg-pf.pt',
  },
  {
    mode: 'prompt',
    title: 'Prompt Inference',
    desc: 'Detect specific objects using text labels or visual reference images with bounding box annotations via SAVPE encoder.',
    model: 'yoloe-26l-seg.pt',
  },
]

function select(mode: InferenceMode) {
  if (store.modelLoading) return
  store.selectMode(mode)
}

function isLoading(m: ModeCard) {
  return store.modelLoading && store.loadingMode === m.mode
}

function hasError(m: ModeCard) {
  return store.modelError && store.loadingMode === null && store.inferenceMode === null
    // Show error on the card that was last attempted
    && !store.modelLoaded
}
</script>

<template>
  <div class="flex items-center justify-center min-h-screen bg-canvas">
    <div class="w-full max-w-[680px] px-(--spacing-xl)">
      <!-- Header -->
      <div class="text-center mb-(--spacing-huge)">
        <h1 class="text-[28px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-sm)">
          LabelLens
        </h1>
        <p class="text-[13px] text-ink-mute leading-[1.45]">
          Select an inference mode to continue
        </p>
      </div>

      <!-- Mode cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-(--spacing-lg)">
        <button
          v-for="m in MODES"
          :key="m.mode"
          @click="select(m.mode)"
          :disabled="store.modelLoading"
          class="group relative flex flex-col items-start p-(--spacing-xxl) rounded-(--radius-lg) border border-hairline bg-canvas transition-all duration-150 text-left cursor-pointer"
          :class="[
            isLoading(m)
              ? 'border-primary/50'
              : 'hover:border-hairline-strong hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)]'
          ]"
        >
          <!-- Loading overlay -->
          <div
            v-if="isLoading(m)"
            class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/95 rounded-(--radius-lg) z-10"
          >
            <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mb-(--spacing-md)" />
            <p class="text-[12px] text-ink-mute font-mono">{{ m.model }}</p>
          </div>

          <!-- Error overlay -->
          <div
            v-if="store.modelError && store.loadingMode === null && !store.modelLoaded && !isLoading(m)"
            class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/95 rounded-(--radius-lg) z-10 px-(--spacing-lg)"
          >
            <!-- Error icon -->
            <svg class="w-5 h-5 text-red-500 mb-(--spacing-sm)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            <p class="text-[12px] text-ink-mute text-center leading-[1.45]">{{ store.modelError }}</p>
            <p class="text-[12px] text-primary mt-(--spacing-xs)">Click to retry</p>
          </div>

          <!-- Icon: Free mode — scan/eye -->
          <div v-if="m.mode === 'free'" class="mb-(--spacing-lg)">
            <svg class="w-6 h-6 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>

          <!-- Icon: Prompt mode — target/crosshair -->
          <div v-else class="mb-(--spacing-lg)">
            <svg class="w-6 h-6 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
          </div>

          <!-- Card content -->
          <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-xs)">
            {{ m.title }}
          </h2>
          <p class="text-[13px] text-ink-mute leading-[1.45] mb-(--spacing-lg)">
            {{ m.desc }}
          </p>
          <span class="text-[12px] font-mono text-ink-faint">{{ m.model }}</span>
        </button>
      </div>

      <!-- Footer hint -->
      <p class="text-center text-[12px] text-ink-faint mt-(--spacing-xxl) leading-[1.45]">
        Model loads into GPU memory. Switch modes anytime via the header.
      </p>
    </div>
  </div>
</template>
