<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import { useInferenceStore } from '../../shared/stores/inference'
import type { DetectionAnnotation, DatasetOverlayDetection } from '../../shared/api/dataset'
import EditableAnnotationOverlay from './EditableAnnotationOverlay.vue'

const emit = defineEmits<{ back: [] }>()
const store = useDatasetStore()
const inferenceStore = useInferenceStore()
const imageSrc = ref('')
const showDeleteConfirm = ref(false)
const deletingImage = ref(false)
const selectedDetectionId = ref<number | null>(null)
const editorMode = ref<'idle' | 'add' | 'edit'>('idle')
const draftLabel = ref('')
const draftBox = ref<[number, number, number, number] | null>(null)
const savingAnnotation = ref(false)
let objectUrl = ''

type AssistedCandidate = DatasetOverlayDetection & { candidateId: number }

const inferNextLoading = ref(false)
const inferNextError = ref('')
const inferCandidates = ref<AssistedCandidate[]>([])
const selectedCandidateId = ref<number | null>(null)
const acceptingAllCandidates = ref(false)
const candidateBusyIds = ref<Set<number>>(new Set())
const deletingDetectionIds = ref<Set<number>>(new Set())
const promptDetectionIds = ref<Set<number>>(new Set())
const showDetectionDeleteConfirm = ref(false)
const pendingDeleteDetection = ref<DetectionAnnotation | null>(null)

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
const selectedPromptDetections = computed(() => detections.value.filter((det) => promptDetectionIds.value.has(det.id)))
const promptModelReady = computed(() => inferenceStore.modelLoaded && inferenceStore.inferenceMode === 'prompt')
const canInferNext = computed(() => Boolean(selectedPromptDetections.value.length && canNavigateNext.value && store.selectedImage && !inferNextLoading.value))
const visibleCandidates = computed(() => inferCandidates.value.filter((candidate) => !isDuplicateCandidate(candidate)))
const duplicateCandidateCount = computed(() => inferCandidates.value.length - visibleCandidates.value.length)
const candidateActionBusy = computed(() => acceptingAllCandidates.value || candidateBusyIds.value.size > 0)
const displayDetections = computed<DatasetOverlayDetection[]>(() => [
  ...detections.value.filter((d) => isVisible(d)),
  ...visibleCandidates.value.map((candidate) => ({
    ...candidate,
    id: candidate.candidateId,
    accepted: true,
  })),
])

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
  selectedCandidateId.value = null
  editorMode.value = 'idle'
  draftLabel.value = ''
  draftBox.value = null
}

function beginNewAnnotation(box: [number, number, number, number]) {
  selectedDetectionId.value = null
  selectedCandidateId.value = null
  editorMode.value = 'add'
  draftLabel.value = availableLabels.value[0] ?? ''
  draftBox.value = roundBox(box)
}

function selectDetection(id: number) {
  const det = detections.value.find((d) => d.id === id)
  if (!det) return
  selectedCandidateId.value = null
  selectedDetectionId.value = id
  editorMode.value = 'edit'
  draftLabel.value = det.label
  draftBox.value = roundBox(det.box)
}

function selectCandidate(id: number) {
  const candidate = visibleCandidates.value.find((item) => item.candidateId === id)
  if (!candidate) return
  resetEditor()
  selectedCandidateId.value = id
}

function handleOverlaySelect(id: number) {
  if (id < 0) {
    selectCandidate(id)
    return
  }
  selectDetection(id)
}

function replaceSet<T>(source: Set<T>, mutate: (next: Set<T>) => void): Set<T> {
  const next = new Set(source)
  mutate(next)
  return next
}

function isPromptSelected(id: number): boolean {
  return promptDetectionIds.value.has(id)
}

function togglePromptDetection(id: number) {
  promptDetectionIds.value = replaceSet(promptDetectionIds.value, (next) => {
    if (next.has(id)) next.delete(id)
    else next.add(id)
  })
}

function setPromptDetections(ids: number[]) {
  promptDetectionIds.value = new Set(ids)
}

function isCandidateBusy(candidateId: number): boolean {
  return candidateBusyIds.value.has(candidateId)
}

function setCandidateBusy(candidateId: number, busy: boolean) {
  candidateBusyIds.value = replaceSet(candidateBusyIds.value, (next) => {
    if (busy) next.add(candidateId)
    else next.delete(candidateId)
  })
}

function isDeletingDetection(id: number): boolean {
  return deletingDetectionIds.value.has(id)
}

function setDeletingDetection(id: number, deleting: boolean) {
  deletingDetectionIds.value = replaceSet(deletingDetectionIds.value, (next) => {
    if (deleting) next.add(id)
    else next.delete(id)
  })
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

function asBox(box: number[]): [number, number, number, number] {
  return [box[0] ?? 0, box[1] ?? 0, box[2] ?? 0, box[3] ?? 0]
}

function boxArea(box: number[]): number {
  const [x1, y1, x2, y2] = normalizeBox(box)
  return Math.max(0, x2 - x1) * Math.max(0, y2 - y1)
}

function boxIou(a: number[], b: number[]): number {
  const [ax1, ay1, ax2, ay2] = normalizeBox(a)
  const [bx1, by1, bx2, by2] = normalizeBox(b)
  const x1 = Math.max(ax1, bx1)
  const y1 = Math.max(ay1, by1)
  const x2 = Math.min(ax2, bx2)
  const y2 = Math.min(ay2, by2)
  const intersection = Math.max(0, x2 - x1) * Math.max(0, y2 - y1)
  const union = boxArea(a) + boxArea(b) - intersection
  return union > 0 ? intersection / union : 0
}

function isDuplicateCandidate(candidate: DatasetOverlayDetection): boolean {
  return detections.value.some((det) => boxIou(candidate.box, det.box) >= 0.7)
}

async function loadPromptModel() {
  inferNextError.value = ''
  await inferenceStore.selectMode('prompt')
  if (!promptModelReady.value && inferenceStore.modelError) {
    inferNextError.value = inferenceStore.modelError
  }
}

async function nextImageId(): Promise<string | null> {
  const idx = currentImageIndex.value
  const nextOnPage = store.images[idx + 1]
  if (nextOnPage) return nextOnPage.img_id
  if (store.imagesPage >= totalPages.value) return null
  await store.fetchImages(store.imagesPage + 1)
  return store.images[0]?.img_id ?? null
}

async function runInferNext() {
  if (!selectedPromptDetections.value.length || !store.selectedImage) return
  if (!promptModelReady.value) {
    await loadPromptModel()
    if (!promptModelReady.value) return
  }

  const sourceImgId = store.selectedImage
  const prompts = selectedPromptDetections.value.map((det) => ({
    box: asBox(det.box),
    label: det.label,
  }))

  inferNextLoading.value = true
  inferNextError.value = ''
  inferCandidates.value = []
  try {
    const targetImgId = await nextImageId()
    if (!targetImgId) {
      inferNextError.value = 'No next image available.'
      return
    }
    const result = await store.inferNextVisualPrompt(sourceImgId, targetImgId, prompts)
    await store.selectImage(targetImgId)
    setPromptDetections([])
    inferCandidates.value = (result?.candidates ?? []).map((candidate, idx) => ({
      ...candidate,
      candidateId: -1000 - idx,
      assisted: true,
      source: 'visual_prompt',
    }))
  } catch (e) {
    inferNextError.value = e instanceof Error ? e.message : 'Infer Next failed'
  } finally {
    inferNextLoading.value = false
  }
}

function rejectCandidate(candidateId: number) {
  inferCandidates.value = inferCandidates.value.filter((item) => item.candidateId !== candidateId)
  if (selectedCandidateId.value === candidateId) selectedCandidateId.value = null
}

function visualAssistPromptIds(annotationsResult: { detections: DetectionAnnotation[] } | null | undefined): number[] {
  return (annotationsResult?.detections ?? [])
    .filter((det) => det.assisted && det.source === 'visual_prompt')
    .map((det) => det.id)
}

async function acceptCandidate(candidate: AssistedCandidate) {
  if (!store.selectedImage || isCandidateBusy(candidate.candidateId) || acceptingAllCandidates.value) return
  setCandidateBusy(candidate.candidateId, true)
  inferNextError.value = ''
  try {
    const result = await store.addDetection(store.selectedImage, {
      label: candidate.label,
      box: asBox(candidate.box),
      accepted: true,
      confidence: candidate.confidence,
      assisted: true,
      source: 'visual_prompt',
    })
    rejectCandidate(candidate.candidateId)
    const promptIds = visualAssistPromptIds(result)
    if (promptIds.length) {
      promptDetectionIds.value = replaceSet(promptDetectionIds.value, (next) => {
        next.add(promptIds[promptIds.length - 1])
      })
    }
  } catch (e) {
    inferNextError.value = e instanceof Error ? e.message : 'Candidate save failed'
  } finally {
    setCandidateBusy(candidate.candidateId, false)
  }
}

async function acceptAllCandidatesAndContinue() {
  if (!store.selectedImage || acceptingAllCandidates.value || !visibleCandidates.value.length || !canNavigateNext.value) return
  const imgId = store.selectedImage
  const candidates = [...visibleCandidates.value]
  acceptingAllCandidates.value = true
  candidateBusyIds.value = new Set(candidates.map((candidate) => candidate.candidateId))
  inferNextError.value = ''
  try {
    let latestResult: { detections: DetectionAnnotation[] } | null | undefined
    for (const candidate of candidates) {
      latestResult = await store.addDetection(imgId, {
        label: candidate.label,
        box: asBox(candidate.box),
        accepted: true,
        confidence: candidate.confidence,
        assisted: true,
        source: 'visual_prompt',
      })
      rejectCandidate(candidate.candidateId)
    }
    const promptIds = visualAssistPromptIds(latestResult)
    setPromptDetections(promptIds)
    await runInferNext()
  } catch (e) {
    inferNextError.value = e instanceof Error ? e.message : 'Candidate save failed'
  } finally {
    acceptingAllCandidates.value = false
    candidateBusyIds.value = new Set()
  }
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

function requestDeleteDetection(det: DetectionAnnotation) {
  pendingDeleteDetection.value = det
  showDetectionDeleteConfirm.value = true
}

function closeDetectionDeleteDialog() {
  if (pendingDeleteDetection.value && isDeletingDetection(pendingDeleteDetection.value.id)) return
  showDetectionDeleteConfirm.value = false
  pendingDeleteDetection.value = null
}

async function confirmDeleteDetection() {
  const det = pendingDeleteDetection.value
  if (!det || !store.selectedImage || isDeletingDetection(det.id)) return
  setDeletingDetection(det.id, true)
  try {
    await store.deleteDetection(store.selectedImage, det.id)
    promptDetectionIds.value = replaceSet(promptDetectionIds.value, (next) => next.delete(det.id))
    if (selectedDetectionId.value === det.id) resetEditor()
    showDetectionDeleteConfirm.value = false
    pendingDeleteDetection.value = null
  } finally {
    setDeletingDetection(det.id, false)
  }
}

async function deleteSelectedAnnotation() {
  if (!selectedDetection.value) return
  requestDeleteDetection(selectedDetection.value)
}

function closePanel() { emit('back') }

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
  if (showDetectionDeleteConfirm.value) {
    if (e.key === 'Escape') closeDetectionDeleteDialog()
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
    inferCandidates.value = []
    candidateBusyIds.value = new Set()
    setPromptDetections([])
    inferNextError.value = ''
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
  const validIds = new Set(detections.value.map((det) => det.id))
  promptDetectionIds.value = new Set(Array.from(promptDetectionIds.value).filter((id) => validIds.has(id)))
  if (selectedDetectionId.value !== null && !validIds.has(selectedDetectionId.value)) {
    resetEditor()
  }
})

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  if (store.reviewingImageId && (!store.selectedImage || store.selectedImage !== store.reviewingImageId)) {
    await store.selectImage(store.reviewingImageId)
  }
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (objectUrl) URL.revokeObjectURL(objectUrl)
})
</script>

<template>
  <section class="dataset-review-fullpage">
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
              :detections="displayDetections"
              :show-bbox="store.overlayState.showBbox"
              :show-labels="store.overlayState.showLabels"
              :show-masks="store.overlayState.showMasks"
              :selected-id="selectedCandidateId ?? selectedDetectionId"
              :draft-box="draftBox"
              :editor-open="editorMode !== 'idle'"
              @select="handleOverlaySelect"
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

            <Transition name="prompt-bar">
              <div v-if="selectedPromptDetections.length > 0" class="dataset-prompt-action-bar">
                <span>{{ selectedPromptDetections.length }} prompt{{ selectedPromptDetections.length > 1 ? 's' : '' }} selected</span>
                <button
                  v-if="!promptModelReady"
                  class="dataset-secondary-button"
                  :disabled="inferenceStore.modelLoading"
                  @click="loadPromptModel"
                >
                  {{ inferenceStore.modelLoading ? 'Loading...' : 'Load Model' }}
                </button>
                <button
                  v-else
                  class="dataset-primary-button"
                  :disabled="!canInferNext || inferNextLoading"
                  @click="runInferNext"
                >
                  {{ inferNextLoading ? 'Running...' : 'Infer Next ▸' }}
                </button>
                <div v-if="inferNextError" style="position: absolute; top: 100%; left: 0; right: 0; text-align: center; margin-top: 4px; color: #b42318; font-size: 11px;">
                  {{ inferNextError }}
                </div>
              </div>
            </Transition>
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
                  <span class="w-[5px] h-[5px] rounded-full" :style="{ backgroundColor: detColor(i) }" />
                  {{ cls }} ({{ count }})
                </button>
              </div>
            </section>

            <section v-if="inferCandidates.length" class="dataset-candidate-panel">
              <header>
                <div>
                  <strong>Candidates</strong>
                  <small>{{ visibleCandidates.length }} new<span v-if="duplicateCandidateCount"> · {{ duplicateCandidateCount }} hidden duplicate</span></small>
                </div>
                <button
                  v-if="visibleCandidates.length"
                  class="dataset-primary-button dataset-candidate-continue"
                  :disabled="candidateActionBusy || !canNavigateNext"
                  @click="acceptAllCandidatesAndContinue"
                >
                  {{ acceptingAllCandidates ? 'Saving...' : 'Accept All & Continue' }}
                </button>
              </header>

              <div v-if="visibleCandidates.length" class="dataset-candidate-list">
                <div
                  v-for="candidate in visibleCandidates"
                  :key="candidate.candidateId"
                  class="dataset-candidate-row"
                  :class="{ 'is-selected': candidate.candidateId === selectedCandidateId }"
                  @click="selectCandidate(candidate.candidateId)"
                >
                  <div class="min-w-0">
                    <p class="text-[12px] font-medium truncate">{{ candidate.label }}</p>
                    <p class="text-[10px] text-ink-faint font-mono truncate">{{ (candidate.confidence * 100).toFixed(0) }}% · [{{ candidate.box.map((v) => Math.round(v)).join(', ') }}]</p>
                  </div>
                  <button class="dataset-accept-button" :disabled="isCandidateBusy(candidate.candidateId)" @click.stop="acceptCandidate(candidate)">
                    {{ isCandidateBusy(candidate.candidateId) ? 'Saving...' : 'Accept' }}
                  </button>
                  <button
                    class="dataset-secondary-button dataset-candidate-reject"
                    :disabled="isCandidateBusy(candidate.candidateId) || acceptingAllCandidates"
                    @click.stop="rejectCandidate(candidate.candidateId)"
                  >
                    Reject
                  </button>
                </div>
              </div>
              <p v-else class="dataset-candidate-empty">All candidates overlap existing annotations.</p>
            </section>

            <div class="dataset-detection-list">
              <div
                v-for="det in detections"
                :key="det.id"
                class="dataset-detection-row"
                :class="{ 'opacity-50': !det.accepted, 'is-selected': det.id === selectedDetectionId, 'is-prompt': isPromptSelected(det.id) }"
                @click="selectDetection(det.id)"
              >
                <input type="checkbox" class="dataset-prompt-check" :checked="isPromptSelected(det.id)" @change="togglePromptDetection(det.id)" title="Use as Visual Assist prompt" @click.stop />

                <button
                  class="dataset-detection-toggle"
                  :class="{ 'opacity-30': !isVisible(det) }"
                  @click.stop="store.toggleDetectionVisibility(det.id)"
                >
                  <svg v-if="isVisible(det)" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                  </svg>
                  <svg v-else class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                </button>

                <div class="min-w-0">
                  <p class="text-[12px] font-medium truncate" :class="det.accepted ? 'text-ink' : 'text-ink-faint line-through'">{{ det.label }}</p>
                  <p class="text-[10px] text-ink-faint font-mono truncate">{{ det.assisted ? 'Visual assist' : det.manual ? 'Manual' : `${(det.confidence * 100).toFixed(0)}%` }} · [{{ det.box.map((v) => Math.round(v)).join(', ') }}]</p>
                </div>

                <button
                  class="dataset-status-toggle"
                  :class="{ 'is-accepted': det.accepted }"
                  :title="det.accepted ? 'Accepted' : 'Rejected'"
                  @click.stop="toggleAccept(det)"
                >
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </button>

                <button
                  class="dataset-row-delete-button"
                  :disabled="isDeletingDetection(det.id)"
                  aria-label="Delete annotation"
                  @click.stop="requestDeleteDetection(det)"
                >
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                  </svg>
                </button>
              </div>

              <div v-if="!detections.length" class="p-8 text-center text-[12px] text-ink-faint">
                No detections for this image.
              </div>
            </div>

            <footer class="px-4 py-2 border-t border-hairline flex items-center justify-between bg-canvas-soft shrink-0">
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

    <div v-if="showDetectionDeleteConfirm && pendingDeleteDetection" class="dataset-review-confirm">
      <section class="dataset-delete-dialog">
        <header class="dataset-modal-header">
          <div>
            <h3 class="dataset-modal-title">Delete Annotation</h3>
            <p class="dataset-modal-copy">This action cannot be undone.</p>
          </div>
          <button class="dataset-modal-close" :disabled="isDeletingDetection(pendingDeleteDetection.id)" @click="closeDetectionDeleteDialog" aria-label="Close delete annotation dialog">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </header>

        <div class="dataset-modal-body dataset-form-stack">
          <p class="text-[13px] text-ink-mute leading-relaxed">
            Delete annotation <span class="font-medium text-ink">"{{ pendingDeleteDetection.label }}"</span>?
          </p>
        </div>

        <footer class="dataset-modal-footer">
          <button class="dataset-secondary-button" :disabled="isDeletingDetection(pendingDeleteDetection.id)" @click="closeDetectionDeleteDialog">Cancel</button>
          <button class="dataset-primary-button" :disabled="isDeletingDetection(pendingDeleteDetection.id)" @click="confirmDeleteDetection">
            {{ isDeletingDetection(pendingDeleteDetection.id) ? 'Deleting...' : 'Delete' }}
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>
