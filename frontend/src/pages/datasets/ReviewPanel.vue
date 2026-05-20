<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import type { DetectionAnnotation } from '../../shared/api/dataset'

const emit = defineEmits<{ close: [] }>()
const store = useDatasetStore()
const imageSrc = ref('')
let objectUrl = ''

const annotations = computed(() => store.currentAnnotations?.annotations)
const detections = computed(() => annotations.value?.detections ?? [])
const acceptedCount = computed(() => detections.value.filter((d) => d.accepted).length)
const rejectedCount = computed(() => detections.value.filter((d) => !d.accepted).length)
const classCount = computed(() => classes.value.length)
const currentImageIndex = computed(() => store.images.findIndex((i) => i.img_id === store.selectedImage))
const totalImages = computed(() => store.images.length)
const canNavigatePrev = computed(() => currentImageIndex.value > 0)
const canNavigateNext = computed(() => currentImageIndex.value >= 0 && currentImageIndex.value < totalImages.value - 1)
const frameStyle = computed(() => ({
  aspectRatio: `${annotations.value?.width ?? 16} / ${annotations.value?.height ?? 9}`,
}))

const classes = computed(() => {
  const cls = new Map<string, number>()
  for (const d of detections.value) cls.set(d.label, (cls.get(d.label) ?? 0) + 1)
  return Array.from(cls.entries())
})

const COLORS = ['#3ecf8e', '#24b47e', '#707070', '#9a9a9a', '#6b01c2', '#644fc1', '#ffdb13', '#212121']
function detColor(idx: number): string { return COLORS[idx % COLORS.length] }

function closePanel() { emit('close') }

function navigateNext() {
  if (!canNavigateNext.value) return
  const idx = currentImageIndex.value
  store.selectImage(store.images[idx + 1].img_id)
}

function navigatePrev() {
  if (!canNavigatePrev.value) return
  const idx = currentImageIndex.value
  store.selectImage(store.images[idx - 1].img_id)
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
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = ''
    }
    if (!store.currentProject || !store.selectedImage) {
      imageSrc.value = ''
      return
    }
    try {
      const resp = await fetch(`/api/datasets/${store.currentProject}/images/${store.selectedImage}/file`)
      if (resp.ok) {
        const blob = await resp.blob()
        objectUrl = URL.createObjectURL(blob)
        imageSrc.value = objectUrl
      }
    } catch {
      imageSrc.value = ''
    }
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (objectUrl) URL.revokeObjectURL(objectUrl)
})
</script>

<template>
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0 scale-[0.98]"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition ease-in duration-150"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-[0.98]"
  >
    <div class="dataset-dialog-backdrop" @click.self="closePanel">
      <section class="dataset-review-dialog">
        <header class="h-[60px] px-4 md:px-5 border-b border-hairline flex items-center justify-between gap-4 shrink-0 bg-canvas">
          <div class="min-w-0">
            <p class="text-[14px] font-medium text-ink truncate">{{ store.currentAnnotations?.filename || store.selectedImage }}</p>
            <p class="text-[11px] text-ink-mute font-mono truncate">
              <template v-if="annotations?.width">{{ annotations.width }}x{{ annotations.height }} px</template>
              <template v-else>{{ acceptedCount + rejectedCount }} detections</template>
            </p>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <button
              class="h-8 px-2.5 md:px-3 text-[12px] rounded-(--radius-sm) border border-hairline bg-canvas text-ink-mute hover:bg-canvas-soft hover:text-ink transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
              :disabled="!canNavigatePrev"
              @click="navigatePrev"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6" /></svg>
              Previous
            </button>
            <span class="text-[12px] font-mono text-ink-mute min-w-[54px] text-center">{{ currentImageIndex + 1 }} / {{ totalImages }}</span>
            <button
              class="h-8 px-2.5 md:px-3 text-[12px] rounded-(--radius-sm) border border-hairline bg-canvas text-ink-mute hover:bg-canvas-soft hover:text-ink transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
              :disabled="!canNavigateNext"
              @click="navigateNext"
            >
              Next
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6" /></svg>
            </button>
            <button class="w-8 h-8 rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer flex items-center justify-center ml-1 text-ink-mute hover:text-ink" @click="closePanel">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </header>

        <div class="dataset-review-body">
          <main class="dataset-review-stage">
            <div class="dataset-review-frame" :style="frameStyle">
              <img v-if="imageSrc" :src="imageSrc" :alt="store.currentAnnotations?.filename"  />

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
                  class="absolute border-2 rounded-[3px] pointer-events-none transition-opacity"
                  :class="{ 'opacity-30': !det.accepted }"
                  :style="boxStyle(det)"
                >
                  <span
                    v-if="store.overlayState.showLabels"
                    class="absolute -top-[20px] left-0 text-[9px] font-medium px-1.5 py-[2px] rounded-[2px] text-white whitespace-nowrap"
                    :style="{ backgroundColor: detColor(det.id) }"
                  >
                    {{ det.label }} {{ (det.confidence * 100).toFixed(0) }}%
                  </span>
                </div>
              </template>
            </div>
          </main>

          <aside class="min-h-0 border-t lg:border-t-0 lg:border-l border-hairline bg-canvas flex flex-col">
            <div class="grid grid-cols-3 gap-2 p-4 border-b border-hairline bg-canvas-soft">
              <div class="border border-hairline rounded-(--radius-sm) bg-canvas p-2 text-center">
                <strong class="block text-[16px] font-medium text-primary">{{ acceptedCount }}</strong>
                <span class="block text-[9px] text-ink-mute uppercase tracking-[0.05em] mt-0.5">Accepted</span>
              </div>
              <div class="border border-hairline rounded-(--radius-sm) bg-canvas p-2 text-center">
                <strong class="block text-[16px] font-medium text-ink">{{ rejectedCount }}</strong>
                <span class="block text-[9px] text-ink-mute uppercase tracking-[0.05em] mt-0.5">Rejected</span>
              </div>
              <div class="border border-hairline rounded-(--radius-sm) bg-canvas p-2 text-center">
                <strong class="block text-[16px] font-medium text-ink">{{ classCount }}</strong>
                <span class="block text-[9px] text-ink-mute uppercase tracking-[0.05em] mt-0.5">Classes</span>
              </div>
            </div>

            <div class="p-4 border-b border-hairline flex flex-col gap-3">
              <div class="grid grid-cols-3 gap-2">
                <button
                  class="h-8 text-[11px] font-medium rounded-(--radius-sm) transition-colors cursor-pointer border inline-flex items-center justify-center gap-1"
                  :class="store.overlayState.showBbox ? 'bg-primary/10 text-primary border-primary/30' : 'border-hairline bg-canvas-soft text-ink-mute hover:text-ink'"
                  @click="store.toggleOverlay('showBbox')"
                >BBoxes</button>
                <button
                  class="h-8 text-[11px] font-medium rounded-(--radius-sm) transition-colors cursor-pointer border inline-flex items-center justify-center gap-1"
                  :class="store.overlayState.showLabels ? 'bg-primary/10 text-primary border-primary/30' : 'border-hairline bg-canvas-soft text-ink-mute hover:text-ink'"
                  @click="store.toggleOverlay('showLabels')"
                >Labels</button>
                <button
                  class="h-8 text-[11px] font-medium rounded-(--radius-sm) transition-colors cursor-pointer border inline-flex items-center justify-center gap-1"
                  :class="store.overlayState.showMasks ? 'bg-primary/10 text-primary border-primary/30' : 'border-hairline bg-canvas-soft text-ink-mute hover:text-ink'"
                  @click="store.toggleOverlay('showMasks')"
                >Masks</button>
              </div>

              <div v-if="classes.length" class="flex flex-wrap gap-1.5">
                <button
                  v-for="([cls, count], i) in classes"
                  :key="cls"
                  class="h-[26px] rounded-full border border-hairline bg-canvas-soft px-2.5 text-[11px] font-medium text-ink cursor-pointer inline-flex items-center gap-1.5 transition-opacity"
                  :class="{ 'opacity-35 line-through': isClassHidden(cls) }"
                  @click="store.toggleClassVisibility(cls)"
                >
                  <span class="w-[6px] h-[6px] rounded-full" :style="{ backgroundColor: detColor(i) }" />
                  {{ cls }} ({{ count }})
                </button>
              </div>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto">
              <div
                v-for="det in detections"
                :key="det.id"
                class="grid grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3 px-5 py-3 border-b border-hairline/50 hover:bg-canvas-soft transition-colors"
                :class="{ 'opacity-50': !det.accepted }"
              >
                <button
                  class="w-7 h-7 rounded-(--radius-sm) border border-hairline bg-canvas-soft flex items-center justify-center cursor-pointer hover:border-hairline-strong hover:text-ink transition-colors"
                  :class="{ 'opacity-30': !isVisible(det) }"
                  @click="store.toggleDetectionVisibility(det.id)"
                >
                  <svg v-if="isVisible(det)" class="w-3.5 h-3.5 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                  </svg>
                  <svg v-else class="w-3.5 h-3.5 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                </button>

                <div class="min-w-0">
                  <p class="text-[13px] font-medium truncate" :class="det.accepted ? 'text-ink' : 'text-ink-faint line-through'">{{ det.label }}</p>
                  <p class="text-[11px] text-ink-faint font-mono truncate">{{ (det.confidence * 100).toFixed(0) }}% · [{{ det.box.map((v) => Math.round(v)).join(', ') }}]</p>
                </div>

                <button
                  class="h-7 px-3 rounded-(--radius-sm) text-[11px] font-medium cursor-pointer border transition-colors"
                  :class="det.accepted ? 'border-primary/30 bg-primary/10 text-primary hover:bg-primary hover:text-on-primary' : 'border-hairline bg-canvas-soft text-ink-mute hover:border-hairline-strong hover:text-ink'"
                  @click="toggleAccept(det)"
                >
                  {{ det.accepted ? 'Accepted' : 'Rejected' }}
                </button>
              </div>

              <div v-if="!detections.length" class="p-8 text-center text-[12px] text-ink-faint">
                No detections for this image.
              </div>
            </div>

            <footer class="px-5 py-3 border-t border-hairline flex items-center justify-between bg-canvas-soft shrink-0">
              <span class="text-[11px] text-ink-faint font-mono">Esc close | Arrows navigate</span>
              <span class="text-[11px] text-ink-faint font-mono">Auto-saved</span>
            </footer>
          </aside>
        </div>
      </section>
    </div>
  </Transition>
</template>
