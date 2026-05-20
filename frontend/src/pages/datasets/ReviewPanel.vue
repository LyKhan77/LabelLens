<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import type { DetectionAnnotation } from '../../shared/api/dataset'

const emit = defineEmits<{ close: [] }>()
const store = useDatasetStore()
const imageSrc = ref('')

const annotations = computed(() => store.currentAnnotations?.annotations)
const detections = computed(() => annotations.value?.detections ?? [])
const acceptedCount = computed(() => detections.value.filter((d) => d.accepted).length)
const rejectedCount = computed(() => detections.value.filter((d) => !d.accepted).length)
const frameStyle = computed(() => ({
  aspectRatio: `${annotations.value?.width ?? 16} / ${annotations.value?.height ?? 9}`,
}))

const classes = computed(() => {
  const cls = new Map<string, number>()
  for (const d of detections.value) cls.set(d.label, (cls.get(d.label) ?? 0) + 1)
  return Array.from(cls.entries())
})

const COLORS = ['#3ecf8e', '#f59e0b', '#3b82f6', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']
function detColor(idx: number): string { return COLORS[idx % COLORS.length] }

function closePanel() { emit('close') }

function navigateNext() {
  const idx = store.images.findIndex((i) => i.img_id === store.selectedImage)
  if (idx >= 0 && idx < store.images.length - 1) store.selectImage(store.images[idx + 1].img_id)
}

function navigatePrev() {
  const idx = store.images.findIndex((i) => i.img_id === store.selectedImage)
  if (idx > 0) store.selectImage(store.images[idx - 1].img_id)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closePanel()
  if (e.key === 'ArrowRight') navigateNext()
  if (e.key === 'ArrowLeft') navigatePrev()
}

function isVisible(det: DetectionAnnotation): boolean {
  return store.isDetectionVisible(det)
}

function isClassHidden(cls: string): boolean {
  return store.overlayState.hiddenClasses.has(cls)
}

function boxStyle(det: DetectionAnnotation) {
  const width = annotations.value?.width ?? 1
  const height = annotations.value?.height ?? 1
  return {
    left: `${(det.box[0] / width) * 100}%`,
    top: `${(det.box[1] / height) * 100}%`,
    width: `${((det.box[2] - det.box[0]) / width) * 100}%`,
    height: `${((det.box[3] - det.box[1]) / height) * 100}%`,
    borderColor: detColor(det.id),
  }
}

function maskPoints(det: DetectionAnnotation) {
  return (det.mask ?? []).map(([x, y]) => `${x},${y}`).join(' ')
}

async function toggleAccept(det: DetectionAnnotation) {
  if (!store.selectedImage) return
  await store.reviewDetection(store.selectedImage, [{ id: det.id, accepted: !det.accepted }])
}

watch(
  () => store.selectedImage,
  async () => {
    if (!store.currentProject || !store.selectedImage) {
      imageSrc.value = ''
      return
    }
    try {
      const resp = await fetch(`/api/datasets/${store.currentProject}/images/${store.selectedImage}/file`)
      if (resp.ok) {
        const blob = await resp.blob()
        imageSrc.value = URL.createObjectURL(blob)
      }
    } catch {
      imageSrc.value = ''
    }
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition ease-in duration-150"
    leave-to-class="opacity-0"
  >
    <div v-if="true" class="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-3 md:p-6" @click.self="closePanel">
    <section class="w-full max-w-[1280px] max-h-[92vh] bg-canvas border border-hairline rounded-(--radius-xl) shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)] overflow-hidden flex flex-col">
      <header class="h-12 px-4 border-b border-hairline flex items-center justify-between shrink-0">
        <div class="min-w-0">
          <p class="text-[13px] font-medium text-ink truncate">{{ store.currentAnnotations?.filename || store.selectedImage }}</p>
          <p class="text-[11px] text-ink-faint">{{ acceptedCount }} accepted · {{ rejectedCount }} rejected</p>
        </div>
        <button class="p-1.5 rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer" @click="closePanel">
          <svg class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </header>

      <div class="min-h-0 flex-1 grid grid-cols-1 lg:grid-cols-[1fr_360px]">
        <main class="min-h-0 bg-canvas-soft p-3 md:p-5 flex items-center justify-center overflow-auto">
          <div class="relative w-full max-w-[920px] max-h-full bg-black rounded-(--radius-lg) overflow-hidden" :style="frameStyle">
            <img v-if="imageSrc" :src="imageSrc" :alt="store.currentAnnotations?.filename" class="absolute inset-0 w-full h-full object-contain" />

            <svg
              v-if="annotations && store.overlayState.showMasks"
              class="absolute inset-0 w-full h-full pointer-events-none"
              :viewBox="`0 0 ${annotations.width} ${annotations.height}`"
              preserveAspectRatio="none"
            >
              <polygon
                v-for="det in detections.filter((d) => isVisible(d) && d.mask && d.mask.length)"
                :key="`mask-${det.id}`"
                :points="maskPoints(det)"
                :fill="detColor(det.id)"
                fill-opacity="0.22"
                :stroke="detColor(det.id)"
                stroke-opacity="0.55"
                stroke-width="2"
              />
            </svg>

            <template v-if="store.overlayState.showBbox">
              <div
                v-for="det in detections.filter((d) => isVisible(d))"
                :key="`box-${det.id}`"
                class="absolute border-2 pointer-events-none"
                :class="{ 'opacity-40': !det.accepted }"
                :style="boxStyle(det)"
              >
                <span
                  v-if="store.overlayState.showLabels"
                  class="absolute -top-5 left-0 text-[11px] px-1.5 py-0.5 rounded-(--radius-xs) text-white whitespace-nowrap"
                  :style="{ backgroundColor: detColor(det.id) }"
                >
                  {{ det.label }} {{ (det.confidence * 100).toFixed(0) }}%
                </span>
              </div>
            </template>
          </div>
        </main>

        <aside class="min-h-0 border-t lg:border-t-0 lg:border-l border-hairline bg-canvas flex flex-col">
          <div class="p-4 border-b border-hairline">
            <div class="grid grid-cols-3 gap-2">
              <button
                class="px-3 py-2 text-[11px] font-medium rounded-(--radius-sm) transition-colors cursor-pointer"
                :class="store.overlayState.showBbox ? 'bg-primary text-on-primary' : 'bg-canvas-soft text-ink-mute'"
                @click="store.toggleOverlay('showBbox')"
              >BBoxes</button>
              <button
                class="px-3 py-2 text-[11px] font-medium rounded-(--radius-sm) transition-colors cursor-pointer"
                :class="store.overlayState.showLabels ? 'bg-primary text-on-primary' : 'bg-canvas-soft text-ink-mute'"
                @click="store.toggleOverlay('showLabels')"
              >Labels</button>
              <button
                class="px-3 py-2 text-[11px] font-medium rounded-(--radius-sm) transition-colors cursor-pointer"
                :class="store.overlayState.showMasks ? 'bg-primary text-on-primary' : 'bg-canvas-soft text-ink-mute'"
                @click="store.toggleOverlay('showMasks')"
              >Masks</button>
            </div>
          </div>

          <div v-if="classes.length" class="p-4 border-b border-hairline">
            <p class="text-[11px] uppercase tracking-wide text-ink-faint mb-2.5">Classes</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="([cls, count], i) in classes"
                :key="cls"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-canvas-soft text-[11px] transition-opacity cursor-pointer"
                :style="{ opacity: isClassHidden(cls) ? 0.35 : 1 }"
                @click="store.toggleClassVisibility(cls)"
              >
                <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: detColor(i) }" />
                <span class="text-ink">{{ cls }}</span>
                <span class="text-ink-faint">{{ count }}</span>
              </button>
            </div>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto">
            <div
              v-for="det in detections"
              :key="det.id"
              class="grid grid-cols-[28px_1fr_auto_auto] items-center gap-3 px-4 py-3 border-b border-hairline/50"
              :class="{ 'opacity-40': !det.accepted }"
            >
              <button class="p-1 rounded hover:bg-canvas-soft cursor-pointer" @click="store.toggleDetectionVisibility(det.id)">
                <svg v-if="isVisible(det)" class="w-3.5 h-3.5 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                <svg v-else class="w-3.5 h-3.5 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
              </button>
              <div class="min-w-0">
                <p class="text-[13px] font-medium truncate" :class="det.accepted ? 'text-ink' : 'text-ink-faint line-through'">{{ det.label }}</p>
                <p class="text-[10px] text-ink-faint font-mono truncate">{{ det.box.map((v) => Math.round(v)).join(', ') }}</p>
              </div>
              <span class="text-[11px] text-ink-mute font-mono">{{ (det.confidence * 100).toFixed(0) }}%</span>
              <button
                class="w-8 h-8 rounded-(--radius-sm) text-[12px] font-semibold transition-colors cursor-pointer"
                :class="det.accepted ? 'bg-primary/15 text-primary hover:bg-primary/25' : 'bg-red-500/15 text-red-400 hover:bg-red-500/25'"
                @click="toggleAccept(det)"
              >
                {{ det.accepted ? 'OK' : 'NO' }}
              </button>
            </div>

            <div v-if="!detections.length" class="p-6 text-center text-[12px] text-ink-faint">
              No detections yet.
            </div>
          </div>

          <footer class="p-4 border-t border-hairline flex items-center justify-between">
            <button class="px-3 py-1.5 text-[12px] text-ink-mute hover:text-ink rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer" @click="navigatePrev">← Previous</button>
            <span class="text-[11px] text-ink-faint font-mono hidden sm:inline">Esc close · ← → navigate</span>
            <button class="px-3 py-1.5 text-[12px] text-ink-mute hover:text-ink rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer" @click="navigateNext">Next →</button>
          </footer>
        </aside>
      </div>
    </section>
  </div>
  </Transition>
</template>
