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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

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

  const x1 = clamp(Math.min(det.box[0], det.box[2]), 0, width)
  const y1 = clamp(Math.min(det.box[1], det.box[3]), 0, height)
  const x2 = clamp(Math.max(det.box[0], det.box[2]), 0, width)
  const y2 = clamp(Math.max(det.box[1], det.box[3]), 0, height)

  return {
    left: `${(x1 / width) * 100}%`,
    top: `${(y1 / height) * 100}%`,
    width: `${((x2 - x1) / width) * 100}%`,
    height: `${((y2 - y1) / height) * 100}%`,
    borderColor: detColor(det.id),
  }
}

function labelStyle(det: DetectionAnnotation) {
  const height = annotations.value?.height ?? 1
  const y1 = clamp(Math.min(det.box[1], det.box[3]), 0, height)
  if (y1 < 22) {
    return {
      top: '0px',
      transform: 'translateY(0)',
    }
  }
  return {
    top: '0px',
    transform: 'translateY(calc(-100% - 2px))',
  }
}

function maskPoints(det: DetectionAnnotation) {
  const width = annotations.value?.width ?? 1
  const height = annotations.value?.height ?? 1
  return (det.mask ?? []).map(([x, y]) => `${clamp(x, 0, width)},${clamp(y, 0, height)}`).join(' ')
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
        <header class="dataset-review-header">
          <div class="min-w-0">
            <p class="text-[14px] font-medium text-ink truncate">{{ store.currentAnnotations?.filename || store.selectedImage }}</p>
            <p class="text-[11px] text-ink-mute font-mono truncate">
              <template v-if="annotations?.width">{{ annotations.width }}x{{ annotations.height }} px</template>
              <template v-else>{{ acceptedCount + rejectedCount }} detections</template>
            </p>
          </div>

          <div class="dataset-review-nav">
            <button :disabled="!canNavigatePrev" @click="navigatePrev">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6" /></svg>
              Previous
            </button>
            <span class="dataset-review-index">{{ currentImageIndex + 1 }} / {{ totalImages }}</span>
            <button :disabled="!canNavigateNext" @click="navigateNext">
              Next
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6" /></svg>
            </button>
            <button aria-label="Close review" @click="closePanel">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </header>

        <div class="dataset-review-body">
          <main class="dataset-review-stage">
            <div class="dataset-review-frame" :style="frameStyle">
              <img v-if="imageSrc" :src="imageSrc" :alt="store.currentAnnotations?.filename" />

              <svg
                v-if="annotations && store.overlayState.showMasks"
                class="dataset-review-mask-layer"
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
                  class="dataset-review-box absolute border-2 rounded-[3px] pointer-events-none transition-opacity"
                  :class="{ 'opacity-30': !det.accepted }"
                  :style="boxStyle(det)"
                >
                  <span
                    v-if="store.overlayState.showLabels"
                    class="dataset-review-box-label absolute left-0 text-[9px] font-medium px-1.5 py-[2px] rounded-[2px] text-white whitespace-nowrap"
                    :style="{ backgroundColor: detColor(det.id), ...labelStyle(det) }"
                  >
                    {{ det.label }} {{ (det.confidence * 100).toFixed(0) }}%
                  </span>
                </div>
              </template>
            </div>
          </main>

          <aside class="dataset-inspector">
            <section class="dataset-inspector-section dataset-inspector-summary">
              <div>
                <strong class="text-primary">{{ acceptedCount }}</strong>
                <span>Accepted</span>
              </div>
              <div>
                <strong>{{ rejectedCount }}</strong>
                <span>Rejected</span>
              </div>
              <div>
                <strong>{{ classCount }}</strong>
                <span>Classes</span>
              </div>
            </section>

            <section class="dataset-inspector-section">
              <div class="dataset-layer-controls">
                <button :class="{ 'is-active': store.overlayState.showBbox }" @click="store.toggleOverlay('showBbox')">BBoxes</button>
                <button :class="{ 'is-active': store.overlayState.showLabels }" @click="store.toggleOverlay('showLabels')">Labels</button>
                <button :class="{ 'is-active': store.overlayState.showMasks }" @click="store.toggleOverlay('showMasks')">Masks</button>
              </div>

              <div v-if="classes.length" class="dataset-class-filters">
                <button
                  v-for="([cls, count], i) in classes"
                  :key="cls"
                  :class="{ 'opacity-35 line-through': isClassHidden(cls) }"
                  @click="store.toggleClassVisibility(cls)"
                >
                  <span class="w-[6px] h-[6px] rounded-full" :style="{ backgroundColor: detColor(i) }" />
                  {{ cls }} ({{ count }})
                </button>
              </div>
            </section>

            <div class="dataset-detection-list">
              <div
                v-for="det in detections"
                :key="det.id"
                class="dataset-detection-row"
                :class="{ 'opacity-50': !det.accepted }"
              >
                <button
                  class="dataset-detection-toggle"
                  :class="{ 'opacity-30': !isVisible(det) }"
                  @click="store.toggleDetectionVisibility(det.id)"
                >
                  <svg v-if="isVisible(det)" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                  </svg>
                  <svg v-else class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                </button>

                <div class="min-w-0">
                  <p class="text-[13px] font-medium truncate" :class="det.accepted ? 'text-ink' : 'text-ink-faint line-through'">{{ det.label }}</p>
                  <p class="text-[11px] text-ink-faint font-mono truncate">{{ (det.confidence * 100).toFixed(0) }}% · [{{ det.box.map((v) => Math.round(v)).join(', ') }}]</p>
                </div>

                <button
                  class="dataset-accept-button"
                  :class="{ 'is-accepted': det.accepted }"
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
