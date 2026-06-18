<script setup lang="ts">
import { useInferenceStore } from '../../shared/stores/inference'
import type { InferenceMode } from '../../shared/types'

const store = useInferenceStore()
const emit = defineEmits<{ 'open-settings': [] }>()
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

async function select(mode: InferenceMode) {
  if (store.modelLoading) return
  await store.selectMode(mode)
  if (store.modelLoaded) {
    window.history.pushState({}, '', '/workspace')
    window.dispatchEvent(new PopStateEvent('popstate'))
  }
}

function isLoading(m: ModeCard) {
  return store.modelLoading && store.loadingMode === m.mode
}

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}
</script>

<template>
  <div class="flex items-center justify-center min-h-screen bg-canvas">
    <div class="w-full max-w-[1240px] px-(--spacing-xl)">
      <div class="text-center mb-(--spacing-lg)">
        <div class="flex items-center justify-center gap-3 mb-(--spacing-md)">
          <img src="/favicon.png" alt="LabelLens" class="w-12 h-12 rounded-(--radius-md)" />
          <span class="text-[36px] font-bold tracking-[-0.72px]">
            <span class="text-ink">Label</span><span class="text-primary">Lens</span>
          </span>
        </div>
      </div>

      <div class="flex justify-center gap-3 mb-(--spacing-lg) flex-wrap">
        <button class="px-3 py-1.5 text-[13px] rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer" @click="navigate('/datasets')">
          Open Dataset Manager
        </button>
        <button class="px-3 py-1.5 text-[13px] rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer flex items-center gap-1.5" @click="$emit('open-settings')">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          Settings
        </button>
      </div>

      <div class="flex justify-center">
        <div class="w-full max-w-[1240px]">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-(--spacing-lg)">
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
              <div
                v-if="isLoading(m)"
                class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/95 rounded-(--radius-lg) z-10"
              >
                <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mb-(--spacing-md)" />
                <p class="text-[12px] text-ink-mute font-mono">{{ m.model }}</p>
              </div>

              <div
                v-if="store.modelError && store.loadingMode === null && !store.modelLoaded && !isLoading(m)"
                class="absolute inset-0 flex flex-col items-center justify-center bg-canvas/95 rounded-(--radius-lg) z-10 px-(--spacing-lg)"
              >
                <svg class="w-5 h-5 text-red-500 mb-(--spacing-sm)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                <p class="text-[12px] text-ink-mute text-center leading-[1.45]">{{ store.modelError }}</p>
                <p class="text-[12px] text-primary mt-(--spacing-xs)">Click to retry</p>
              </div>

              <div v-if="m.mode === 'free'" class="mb-(--spacing-lg)">
                <svg class="w-6 h-6 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              </div>

              <div v-else class="mb-(--spacing-lg)">
                <svg class="w-6 h-6 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <circle cx="12" cy="12" r="6" />
                  <circle cx="12" cy="12" r="2" />
                </svg>
              </div>

              <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-xs)">
                {{ m.title }}
              </h2>
              <p class="text-[13px] text-ink-mute leading-[1.45] mb-(--spacing-lg)">
                {{ m.desc }}
              </p>
              <span class="text-[12px] font-mono text-ink-faint">{{ m.model }}</span>
            </button>

            <button
              @click="navigate('/train-tune')"
              class="group relative flex flex-col items-start p-(--spacing-xxl) rounded-(--radius-lg) border border-primary/20 bg-primary/5 transition-all duration-150 text-left cursor-pointer hover:border-primary/40 hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
            >
              <div class="mb-(--spacing-lg)">
                <svg class="w-6 h-6 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2v6" />
                  <path d="M12 16v6" />
                  <path d="M4.93 4.93l4.24 4.24" />
                  <path d="M14.83 14.83l4.24 4.24" />
                  <path d="M2 12h6" />
                  <path d="M16 12h6" />
                  <path d="M4.93 19.07l4.24-4.24" />
                  <path d="M14.83 9.17l4.24-4.24" />
                </svg>
              </div>
              <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-xs)">Train Tune</h2>
              <p class="text-[13px] text-ink-mute leading-[1.45] mb-(--spacing-lg)">
                Build immutable dataset versions, configure YOLO training, queue fine-tune jobs, and monitor live metrics history in one workspace.
              </p>
              <span class="text-[12px] font-mono text-primary">YOLO11 / YOLO26</span>
            </button>

            <button
              @click="navigate('/test')"
              class="group relative flex flex-col items-start p-(--spacing-xxl) rounded-(--radius-lg) border border-primary/20 bg-primary/5 transition-all duration-150 text-left cursor-pointer hover:border-primary/40 hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
            >
              <div class="mb-(--spacing-lg)">
                <svg class="w-6 h-6 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 3h6" />
                  <path d="M10 3v6.5L5.5 17a2 2 0 0 0 1.7 3h9.6a2 2 0 0 0 1.7-3L14 9.5V3" />
                  <path d="M7.5 14h9" />
                </svg>
              </div>
              <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-xs)">Test Model</h2>
              <p class="text-[13px] text-ink-mute leading-[1.45] mb-(--spacing-lg)">
                Pick a trained model version, review its task, classes, and metrics, then run live inference on image, video, or RTSP.
              </p>
              <span class="text-[12px] font-mono text-primary">Detect / Segment / Pose / Classify</span>
            </button>
          </div>

          <p class="text-center text-[12px] text-ink-faint mt-(--spacing-xxl) leading-[1.45]">
            Model loads into GPU memory. Switch modes anytime via the header.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
