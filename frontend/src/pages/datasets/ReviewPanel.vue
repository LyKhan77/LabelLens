<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import type { DetectionAnnotation } from '../../shared/api/dataset'
import EditableAnnotationOverlay from './EditableAnnotationOverlay.vue'

const emit = defineEmits<{ close: [] }>()
const store = useDatasetStore()
const imageSrc = ref('')
const showDeleteConfirm = ref(false)
const deletingImage = ref(false)
const selectedDetectionId = ref<number | null>(null)
const editorMode = ref<'idle' | 'add' | 'edit'>('idle')
const draftLabel = ref('')
const draftBox = ref<[number, number, number, number] | null>(null)
const savingAnnotation = ref(false)
let objectUrl = ''

const annotations = computed(() => store.currentAnnotations?.annotations)
const detections = computed(() => annotations.value?.detections ?? [])
const acceptedCount = computed(() => detections.value.filter((d) => d.accepted).length)
const rejectedCount = computed(() => detections.value.filter((d) => !d.accepted).length)
const classCount = computed(() => classes.value.length)
const selectedDetection = computed(() => detections.value.find((d) => d.id === selectedDetectionId.value) ?? null)
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
const availableLabels = computed(() => {
  const labels = new Set<string>(Object.keys(store.currentProjectData?.class_to_id ?? {}))
  for (const d of detections.value) if (d.label) labels.add(d.label)
  return Array.from(labels).sort((a, b) => a.localeCompare(b))
})
const canSaveAnnotation = computed(() => Boolean(draftLabel.value.trim() && draftBox.value && store.selectedImage && editorMode.value !== 'idle'))

const COLORS = ['#3ecf8e', '#24b47e', '#707070', '#9a9a9a', '#6b01c2', '#644fc1', '#ffdb13', '#212121']
function detColor(idx: number): string { return COLORS[idx % COLORS.length] }


function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function normalizeBox(box: number[]): [number, number, number, number] {
  const width = annotations.value?.width ?? 1
  const height = annotations.value?.height ?? 1
  const x1 = clamp(Math.min(box[0] ?? 0, box[2] ?? 0), 0, width)
  const y1 = clamp(Math.min(box[1] ?? 0, box[3] ?? 0), 0, height)
  const x2 = clamp(Math.max(box[0] ?? 0, box[2] ?? 0), 0, width)
  const y2 = clamp(Math.max(box[1] ?? 0, box[3] ?? 0), 0, height)
  return [x1, y1, x2, y2]
}

function roundBox(box: number[]): [number, number, number, number] {
  return normalizeBox(box).map((v) => Math.round(v * 10) / 10) as [number, number, number, number]
}

function resetEditor() {
  selectedDetectionId.value = null
  editorMode.value = 'idle'
  draftLabel.value = ''
  draftBox.value = null
}

function beginNewAnnotation(box: [number, number, number, number]) {
  selectedDetectionId.value = null
  editorMode.value = 'add'
  draftLabel.value = availableLabels.value[0] ?? ''
  draftBox.value = roundBox(box)
}

function selectDetection(id: number) {
  const det = detections.value.find((d) => d.id === id)
  if (!det) return
  selectedDetectionId.value = id
  editorMode.value = 'edit'
  draftLabel.value = det.label
  draftBox.value = roundBox(det.box)
}

function updateDraftBox(box: [number, number, number, number]) {
  draftBox.value = roundBox(box)
}

function updateDraftCoord(index: number, value: string) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return
  const current = draftBox.value ?? [0, 0, 1, 1]
  const next = [...current] as [number, number, number, number]
  next[index] = numeric
  draftBox.value = roundBox(next)
}

function usePresetLabel(e: Event) {
  const value = (e.target as HTMLSelectElement).value
  if (value) draftLabel.value = value
}

async function saveAnnotation() {
  if (!store.selectedImage || !draftBox.value || !draftLabel.value.trim()) return
  savingAnnotation.value = true
  try {
    if (editorMode.value === 'add') {
      await store.addDetection(store.selectedImage, {
        label: draftLabel.value.trim(),
        box: draftBox.value,
        accepted: true,
      })
      resetEditor()
    } else if (editorMode.value === 'edit' && selectedDetectionId.value !== null) {
      await store.updateDetection(store.selectedImage, selectedDetectionId.value, {
        label: draftLabel.value.trim(),
        box: draftBox.value,
      })
      const id = selectedDetectionId.value
      selectDetection(id)
    }
  } finally {
    savingAnnotation.value = false
  }
}

async function deleteSelectedAnnotation() {
  if (!store.selectedImage || selectedDetectionId.value === null) return
  if (!window.confirm('Delete selected annotation?')) return
  savingAnnotation.value = true
  try {
    await store.deleteDetection(store.selectedImage, selectedDetectionId.value)
    resetEditor()
  } finally {
    savingAnnotation.value = false
  }
}

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
    resetEditor()
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

watch(detections, () => {
  if (selectedDetectionId.value !== null && !detections.value.some((d) => d.id === selectedDetectionId.value)) {
    resetEditor()
  }
})

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
            <EditableAnnotationOverlay
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
              :selected-id="selectedDetectionId"
              :draft-box="draftBox"
              :editor-open="editorMode !== 'idle'"
              @select="selectDetection"
              @draft-change="updateDraftBox"
              @create-draft="beginNewAnnotation"
            >
              <template #editor>
                <div v-if="editorMode !== 'idle'" class="dataset-canvas-editor">
                  <header class="dataset-canvas-editor-header">
                    <strong>{{ editorMode === 'add' ? 'New BBox' : 'Edit BBox' }}</strong>
                    <button type="button" aria-label="Close annotation editor" @click="resetEditor">
                      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                    </button>
                  </header>

                  <div class="dataset-canvas-label-row">
                    <select :value="availableLabels.includes(draftLabel) ? draftLabel : ''" @change="usePresetLabel">
                      <option value="">Custom</option>
                      <option v-for="label in availableLabels" :key="label" :value="label">{{ label }}</option>
                    </select>
                    <input v-model="draftLabel" type="text" placeholder="Label" @keydown.enter="saveAnnotation" @keydown.escape="resetEditor" />
                  </div>

                  <details class="dataset-canvas-coords">
                    <summary>Coordinates</summary>
                    <div class="dataset-editor-coords">
                      <label>
                        X1
                        <input :value="draftBox?.[0] ?? ''" type="number" min="0" step="1" @input="updateDraftCoord(0, ($event.target as HTMLInputElement).value)" />
                      </label>
                      <label>
                        Y1
                        <input :value="draftBox?.[1] ?? ''" type="number" min="0" step="1" @input="updateDraftCoord(1, ($event.target as HTMLInputElement).value)" />
                      </label>
                      <label>
                        X2
                        <input :value="draftBox?.[2] ?? ''" type="number" min="0" step="1" @input="updateDraftCoord(2, ($event.target as HTMLInputElement).value)" />
                      </label>
                      <label>
                        Y2
                        <input :value="draftBox?.[3] ?? ''" type="number" min="0" step="1" @input="updateDraftCoord(3, ($event.target as HTMLInputElement).value)" />
                      </label>
                    </div>
                  </details>

                  <div class="dataset-canvas-editor-actions">
                    <button class="dataset-primary-button" :disabled="!canSaveAnnotation || savingAnnotation" @click="saveAnnotation">
                      {{ savingAnnotation ? 'Saving...' : 'Save' }}
                    </button>
                    <button
                      v-if="editorMode === 'edit'"
                      class="dataset-secondary-button dataset-danger-button"
                      :disabled="savingAnnotation || !selectedDetection"
                      @click="deleteSelectedAnnotation"
                    >
                      Delete
                    </button>
                    <button class="dataset-secondary-button" :disabled="savingAnnotation" @click="resetEditor">Cancel</button>
                  </div>
                </div>
              </template>
            </EditableAnnotationOverlay>

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
                :class="{ 'opacity-50': !det.accepted, 'is-selected': det.id === selectedDetectionId }"
                @click="selectDetection(det.id)"
              >
                <button
                  class="dataset-detection-toggle"
                  :class="{ 'opacity-30': !isVisible(det) }"
                  @click.stop="store.toggleDetectionVisibility(det.id)"
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
                  <p class="text-[11px] text-ink-faint font-mono truncate">{{ det.manual ? 'Manual' : `${(det.confidence * 100).toFixed(0)}%` }} · [{{ det.box.map((v) => Math.round(v)).join(', ') }}]</p>
                </div>

                <button
                  class="dataset-accept-button"
                  :class="{ 'is-accepted': det.accepted }"
                  @click.stop="toggleAccept(det)"
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
