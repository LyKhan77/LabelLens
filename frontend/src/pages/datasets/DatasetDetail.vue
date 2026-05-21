<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import ReviewPanel from './ReviewPanel.vue'
import ExportDialog from './ExportDialog.vue'
import BatchUploadDialog from './BatchUploadDialog.vue'
import DatasetMediaOverlay from './DatasetMediaOverlay.vue'

const store = useDatasetStore()
const showExport = ref(false)
const showBatch = ref(false)
const showReview = ref(false)
const galleryFilter = ref<'all' | 'review' | 'accepted' | 'unlabeled'>('all')
const gallerySearch = ref('')
const selectedImageIds = ref<Set<string>>(new Set())
const deleteTargetIds = ref<string[]>([])
const deleteTargetLabel = ref('')
const showImageDeleteConfirm = ref(false)
const deletingImages = ref(false)

const project = computed(() => store.currentProjectData)
const totalPages = computed(() => Math.max(1, Math.ceil(store.imagesTotal / store.imagesLimit)))
const pageStart = computed(() => (store.imagesTotal === 0 ? 0 : (store.imagesPage - 1) * store.imagesLimit + 1))
const pageEnd = computed(() => Math.min(store.imagesPage * store.imagesLimit, store.imagesTotal))
const hasGalleryFilter = computed(() => galleryFilter.value !== 'all' || gallerySearch.value.trim().length > 0)
const selectedCount = computed(() => selectedImageIds.value.size)
const allVisibleSelected = computed(() => filteredImages.value.length > 0 && filteredImages.value.every((img) => selectedImageIds.value.has(img.img_id)))
const pageButtons = computed(() => {
  const total = totalPages.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)

  const current = store.imagesPage
  const pages = new Set([1, total, current - 1, current, current + 1])
  if (current <= 3) {
    pages.add(2)
    pages.add(3)
    pages.add(4)
  }
  if (current >= total - 2) {
    pages.add(total - 3)
    pages.add(total - 2)
    pages.add(total - 1)
  }
  return Array.from(pages).filter((p) => p >= 1 && p <= total).sort((a, b) => a - b)
})

const filteredImages = computed(() => {
  let list = store.images
  if (galleryFilter.value !== 'all') {
    list = list.filter((img) => img.status === galleryFilter.value)
  }
  if (gallerySearch.value.trim()) {
    const q = gallerySearch.value.trim().toLowerCase()
    list = list.filter((img) =>
      img.filename.toLowerCase().includes(q) ||
      (img.source || '').toLowerCase().includes(q),
    )
  }
  return list
})

const metrics = computed(() => {
  const stats = project.value?.stats
  const totalAnnotations = stats?.total_annotations ?? 0
  const accepted = stats?.accepted ?? 0
  return {
    totalImages: stats?.total_images ?? 0,
    totalAnnotations,
    acceptRate: totalAnnotations > 0 ? Math.round((accepted / totalAnnotations) * 100) : 0,
    reviewQueue: stats?.rejected ?? 0,
    classes: stats?.classes.length ?? 0,
  }
})

function goBack() {
  store.currentProject = null
  store.clearSelection()
}

async function selectImage(imgId: string) {
  await store.selectImage(imgId)
  showReview.value = true
}

function isImageSelected(imgId: string) {
  return selectedImageIds.value.has(imgId)
}

function toggleImageSelection(imgId: string, checked: boolean) {
  const next = new Set(selectedImageIds.value)
  if (checked) next.add(imgId)
  else next.delete(imgId)
  selectedImageIds.value = next
}

function clearImageSelection() {
  selectedImageIds.value = new Set()
}

function toggleSelectAllVisible() {
  const next = new Set(selectedImageIds.value)
  if (allVisibleSelected.value) {
    for (const img of filteredImages.value) next.delete(img.img_id)
  } else {
    for (const img of filteredImages.value) next.add(img.img_id)
  }
  selectedImageIds.value = next
}

function requestDeleteImages(ids: string[], label: string) {
  if (!ids.length) return
  deleteTargetIds.value = ids
  deleteTargetLabel.value = label
  showImageDeleteConfirm.value = true
}

function requestDeleteSelected() {
  requestDeleteImages(Array.from(selectedImageIds.value), `${selectedImageIds.value.size} selected images`)
}

function closeImageDeleteDialog() {
  if (deletingImages.value) return
  showImageDeleteConfirm.value = false
  deleteTargetIds.value = []
  deleteTargetLabel.value = ''
}

async function confirmDeleteImages() {
  if (!deleteTargetIds.value.length) return
  deletingImages.value = true
  try {
    await store.removeImages(deleteTargetIds.value)
    clearImageSelection()
    if (store.selectedImage && deleteTargetIds.value.includes(store.selectedImage)) {
      closeReview()
    }
  } finally {
    deletingImages.value = false
    showImageDeleteConfirm.value = false
    deleteTargetIds.value = []
    deleteTargetLabel.value = ''
  }
}

function closeReview() {
  showReview.value = false
  store.clearSelection()
}

async function changePage(page: number) {
  if (page < 1 || page > totalPages.value || page === store.imagesPage) return
  await store.fetchImages(page)
}

function statusLabel(status: string) {
  if (status === 'unlabeled') return 'Unlabeled'
  if (status === 'review') return 'Review'
  if (status === 'accepted') return 'Accepted'
  return 'New'
}

function statusBadgeClass(status: string) {
  if (status === 'accepted') return 'accepted'
  if (status === 'review') return 'review'
  return 'unlabeled'
}

function statusDotClass(status: string) {
  if (status === 'accepted') return 'bg-primary'
  if (status === 'review') return 'bg-ink'
  return 'bg-ink-faint'
}

watch(
  () => store.images.map((img) => img.img_id),
  (ids) => {
    const visible = new Set(ids)
    selectedImageIds.value = new Set(Array.from(selectedImageIds.value).filter((id) => visible.has(id)))
  },
)
</script>

<template>
  <section v-if="project" class="dataset-workspace">
    <div class="dataset-hero">
      <div class="min-w-0">
        <button
          class="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-primary font-medium hover:text-primary-deep transition-colors cursor-pointer mb-3"
          @click="goBack"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Dataset Workspace
        </button>
        <h1 class="text-[32px] leading-[1.1] font-medium tracking-[-0.72px] text-ink">{{ project.name }}</h1>
        <p class="text-[13px] text-ink-mute mt-2 max-w-[640px] leading-relaxed">
          Review-ready dataset for YOLO fine-tuning. Inspect detections, accept or reject annotations, then export.
        </p>
      </div>

      <div class="dataset-actions">
        <button
          class="h-9 px-4 text-[13px] font-medium text-ink border border-hairline rounded-(--radius-sm) bg-canvas hover:bg-canvas-soft hover:border-hairline-strong hover:-translate-y-px transition-all cursor-pointer"
          @click="showBatch = true"
        >
          Rapid Inference
        </button>
        <button
          class="h-9 px-4 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep shadow-[0_1px_3px_rgba(0,0,0,0.06)] hover:-translate-y-px transition-all cursor-pointer"
          @click="showExport = true"
        >
          Export
        </button>
      </div>
    </div>

    <div class="dataset-metrics">
      <div class="dataset-metric-card is-primary">
        <label >Total Images</label>
        <strong >{{ metrics.totalImages }}</strong>
        <small >{{ pageStart }}-{{ pageEnd }} visible on this page</small>
      </div>
      <div class="dataset-metric-card">
        <label >Annotations</label>
        <strong >{{ metrics.totalAnnotations }}</strong>
        <small >{{ metrics.acceptRate }}% approved confidence</small>
      </div>
      <div class="dataset-metric-card is-dark">
        <label >Review Queue</label>
        <strong >{{ metrics.reviewQueue }}</strong>
        <small >Rejected or pending verification</small>
      </div>
      <div class="dataset-metric-card">
        <label >Distinct Classes</label>
        <strong class="text-primary">{{ metrics.classes }}</strong>
        <small >{{ (project?.stats.classes ?? []).join(', ') || 'No classes yet' }}</small>
      </div>
    </div>

    <div class="dataset-filter-bar">
      <div class="dataset-search-field">
        <svg  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
        <input v-model="gallerySearch" type="text" placeholder="Filter by filename or source..."  />
      </div>
      <div class="dataset-segments">
        <button
          :class="{ 'is-active': galleryFilter === 'all' }"
          @click="galleryFilter = 'all'"
        >All</button>
        <button
          :class="{ 'is-active': galleryFilter === 'review' }"
          @click="galleryFilter = 'review'"
        ><span class="w-[5px] h-[5px] rounded-full bg-ink" />Review</button>
        <button
          :class="{ 'is-active': galleryFilter === 'accepted' }"
          @click="galleryFilter = 'accepted'"
        ><span class="w-[5px] h-[5px] rounded-full bg-primary" />Accepted</button>
        <button
          :class="{ 'is-active': galleryFilter === 'unlabeled' }"
          @click="galleryFilter = 'unlabeled'"
        >Unlabeled</button>
      </div>
    </div>

    <template v-if="store.images.length">
      <div class="dataset-gallery-section">
      <div class="dataset-gallery-header">
        <h2 class="text-[16px] font-medium text-ink">Project Files</h2>
        <div class="dataset-gallery-header-actions">
          <button
            class="dataset-select-all-button"
            :disabled="!filteredImages.length"
            @click="toggleSelectAllVisible"
          >
            {{ allVisibleSelected ? 'Clear Selection' : 'Select All Files' }}
          </button>
          <button
            v-if="selectedCount"
            class="dataset-delete-selected-button"
            :disabled="deletingImages"
            @click="requestDeleteSelected"
          >
            Delete Selected ({{ selectedCount }})
          </button>
          <span class="text-[12px] text-ink-mute font-mono">
            <template v-if="hasGalleryFilter">{{ filteredImages.length }} matches · </template>
            Showing {{ pageStart }}-{{ pageEnd }} of {{ store.imagesTotal }} files
          </span>
        </div>
      </div>

      <div class="dataset-gallery-grid">
        <div
          v-for="img in filteredImages"
          :key="img.img_id"
          class="dataset-gallery-card"
          :class="{ 'is-selected': isImageSelected(img.img_id) }"
          tabindex="0"
          role="button"
          @click="selectImage(img.img_id)"
          @keydown.enter="selectImage(img.img_id)"
        >
          <div class="dataset-thumbnail">
            <DatasetMediaOverlay
              :image-src="img.image_url"
              :alt="img.filename"
              :width="img.width"
              :height="img.height"
              :detections="img.detections_preview ?? []"
              :show-bbox="true"
              :show-labels="false"
              :show-masks="true"
            />

            <label class="dataset-card-select" @click.stop>
              <input
                type="checkbox"
                :checked="isImageSelected(img.img_id)"
                :aria-label="`Select ${img.filename}`"
                @change="toggleImageSelection(img.img_id, ($event.target as HTMLInputElement).checked)"
              />
              <span />
            </label>

            <button
              class="dataset-card-delete"
              :aria-label="`Delete ${img.filename}`"
              @click.stop="requestDeleteImages([img.img_id], img.filename)"
            >
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
              </svg>
            </button>

            <div class="dataset-card-shade" />

            <span
              :class="['dataset-status-badge', statusBadgeClass(img.status)]"
            >
              <span class="inline-flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full" :class="statusDotClass(img.status)" />
                {{ statusLabel(img.status) }}
              </span>
            </span>

            <span class="dataset-count-badge">
              {{ img.accepted + img.rejected }} bbox
            </span>
          </div>

          <div class="dataset-card-meta">
            <strong>{{ img.filename }}</strong>
            <span>
              {{ (img.source || 'image').toUpperCase() }}<template v-if="img.width && img.height"> · {{ img.width }}x{{ img.height }}</template>
            </span>
          </div>
        </div>
      </div>
      </div>

      <div v-if="!filteredImages.length" class="mt-5 border border-dashed border-hairline rounded-(--radius-lg) bg-canvas-soft py-12 text-center">
        <p class="text-[14px] font-medium text-ink">No files match this filter</p>
        <p class="text-[12px] text-ink-mute mt-1">Try a different filename, source, or status.</p>
      </div>
    </template>

    <div v-else class="min-h-[360px] border border-dashed border-hairline rounded-(--radius-lg) flex flex-col items-center justify-center text-center px-4">
      <div class="w-12 h-12 rounded-(--radius-lg) border border-hairline bg-canvas-soft flex items-center justify-center mb-4">
        <svg class="w-6 h-6 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>
      <p class="text-[15px] font-medium text-ink mb-1">No images yet</p>
      <p class="text-[12px] text-ink-mute mb-5">Upload images or a video, then run Rapid Inference.</p>
      <button
        class="px-4 py-2.5 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-all cursor-pointer"
        @click="showBatch = true"
      >
        Upload Data
      </button>
    </div>

    <div v-if="totalPages > 1" class="dataset-pager">
      <button
        class="dataset-page-nav-button"
        :disabled="store.imagesPage <= 1"
        @click="changePage(store.imagesPage - 1)"
      >Previous</button>
      <button
        v-for="p in pageButtons"
        :key="p"
        class="dataset-page-button"
        :class="{ 'is-active': p === store.imagesPage }"
        @click="changePage(p)"
      >{{ p }}</button>
      <button
        class="dataset-page-nav-button"
        :disabled="store.imagesPage >= totalPages"
        @click="changePage(store.imagesPage + 1)"
      >Next</button>
    </div>

    <ReviewPanel v-if="showReview && store.selectedImage" @close="closeReview" />
    <ExportDialog v-if="showExport" @close="showExport = false" />
    <BatchUploadDialog v-if="showBatch" @close="showBatch = false" />

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 scale-[0.98]"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-[0.98]"
    >
      <div v-if="showImageDeleteConfirm" class="dataset-dialog-backdrop" @click.self="closeImageDeleteDialog">
        <section class="dataset-delete-dialog">
          <header class="dataset-modal-header">
            <div>
              <h3 class="dataset-modal-title">Delete Image</h3>
              <p class="dataset-modal-copy">This action cannot be undone.</p>
            </div>
            <button class="dataset-modal-close" :disabled="deletingImages" @click="closeImageDeleteDialog" aria-label="Close delete image dialog">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </header>

          <div class="dataset-modal-body dataset-form-stack">
            <p class="text-[13px] text-ink-mute leading-relaxed">
              Delete <span class="font-medium text-ink">{{ deleteTargetLabel }}</span> and their annotations?
            </p>
          </div>

          <footer class="dataset-modal-footer">
            <button class="dataset-secondary-button" :disabled="deletingImages" @click="closeImageDeleteDialog">Cancel</button>
            <button class="dataset-primary-button" :disabled="deletingImages" @click="confirmDeleteImages">
              {{ deletingImages ? 'Deleting...' : 'Delete' }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </section>
</template>
