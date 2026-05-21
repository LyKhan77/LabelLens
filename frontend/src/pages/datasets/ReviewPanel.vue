<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import type { DetectionAnnotation } from '../../shared/api/dataset'
import DatasetMediaOverlay from './DatasetMediaOverlay.vue'

const emit = defineEmits<{ close: [] }>()
const store = useDatasetStore()
const imageSrc = ref('')
const showDeleteConfirm = ref(false)
const deletingImage = ref(false)
let objectUrl = ''

const annotations = computed(() => store.currentAnnotations?.annotations)
const detections = computed(() => annotations.value?.detections ?? [])
const acceptedCount = computed(() => detections.value.filter((d) => d.accepted).length)
const rejectedCount = computed(() => detections.value.filter((d) => !d.accepted).length)
const classCount = computed(() => classes.value.length)
const currentImageIndex = computed(() => store.images.findIndex((i) => i.img_id === store.selectedImage))
const totalImages = computed(() => store.images.length)
const totalPages = computed(() => Math.max(1, Math.ceil(store.imagesTotal / store.imagesLimit)))
const canNavigatePrev = computed(() => currentImageIndex.value > 0 || store.imagesPage > 1)
const canNavigateNext = computed(() => (
  (currentImageIndex.value >= 0 && currentImageIndex.value < totalImages.value - 1) ||
  store.imagesPage < totalPages.value
))
const globalImageIndex = computed(() => {
  if (currentImageIndex.value < 0) return 0
  return (store.imagesPage - 1) * store.imagesLimit + currentImageIndex.value + 1
})
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

async function navigateNext() {
  if (!canNavigateNext.value) return
  const idx = currentImageIndex.value
  const nextOnPage = store.images[idx + 1]
  if (nextOnPage) {
    await store.selectImage(nextOnPage.img_id)
    return
  }
  if (store.imagesPage < totalPages.value) {
    await store.fetchImages(store.imagesPage + 1)
    const first = store.images[0]
    if (first) await store.selectImage(first.img_id)
  }
}

async function navigatePrev() {
  if (!canNavigatePrev.value) return
  const idx = currentImageIndex.value
  const prevOnPage = store.images[idx - 1]
  if (prevOnPage) {
    await store.selectImage(prevOnPage.img_id)
    return
  }
  if (store.imagesPage > 1) {
    await store.fetchImages(store.imagesPage - 1)
    const last = store.images[store.images.length - 1]
    if (last) await store.selectImage(last.img_id)
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (showDeleteConfirm.value) {
    if (e.key === 'Escape') closeDeleteDialog()
    return
  }
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

function requestDeleteCurrent() {
  showDeleteConfirm.value = true
}

function closeDeleteDialog() {
  if (deletingImage.value) return
  showDeleteConfirm.value = false
}

async function confirmDeleteCurrent() {
  if (!store.selectedImage) return
  const imgId = store.selectedImage
  const idx = currentImageIndex.value
  const nextId = store.images[idx + 1]?.img_id ?? store.images[idx - 1]?.img_id ?? null
  deletingImage.value = true
  try {
    await store.removeImage(imgId)
    showDeleteConfirm.value = false
    if (nextId) {
      await store.selectImage(nextId)
    } else {
      closePanel()
    }
  } finally {
    deletingImage.value = false
  }
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
            <span class="dataset-review-index">{{ globalImageIndex }} / {{ store.imagesTotal }}</span>
            <button :disabled="!canNavigateNext" @click="navigateNext">
              Next
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6" /></svg>
            </button>
            <button class="dataset-review-delete-button" :disabled="deletingImage" aria-label="Delete image" @click="requestDeleteCurrent">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
              </svg>
              Delete
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
            <DatasetMediaOverlay
              v-if="imageSrc && annotations"
              class="dataset-review-frame"
              :style="frameStyle"
              :image-src="imageSrc"
              :alt="store.currentAnnotations?.filename || ''"
              :width="annotations.width"
              :height="annotations.height"
              :detections="detections.filter((d) => isVisible(d))"
              :show-bbox="store.overlayState.showBbox"
              :show-labels="store.overlayState.showLabels"
              :show-masks="store.overlayState.showMasks"
            />

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

        <div v-if="showDeleteConfirm" class="dataset-review-confirm">
          <section class="dataset-delete-dialog">
            <header class="dataset-modal-header">
              <div>
                <h3 class="dataset-modal-title">Delete Image</h3>
                <p class="dataset-modal-copy">This action cannot be undone.</p>
              </div>
              <button class="dataset-modal-close" :disabled="deletingImage" @click="closeDeleteDialog" aria-label="Close delete image dialog">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
              </button>
            </header>

            <div class="dataset-modal-body dataset-form-stack">
              <p class="text-[13px] text-ink-mute leading-relaxed">
                Delete image <span class="font-medium text-ink">{{ store.currentAnnotations?.filename || store.selectedImage }}</span> and its annotations?
              </p>
            </div>

            <footer class="dataset-modal-footer">
              <button class="dataset-secondary-button" :disabled="deletingImage" @click="closeDeleteDialog">Cancel</button>
              <button class="dataset-primary-button" :disabled="deletingImage" @click="confirmDeleteCurrent">
                {{ deletingImage ? 'Deleting...' : 'Delete' }}
              </button>
            </footer>
          </section>
        </div>
      </section>
    </div>
  </Transition>
</template>
