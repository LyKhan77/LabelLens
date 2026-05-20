<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import ReviewPanel from './ReviewPanel.vue'
import ExportDialog from './ExportDialog.vue'
import BatchUploadDialog from './BatchUploadDialog.vue'

const store = useDatasetStore()
const showExport = ref(false)
const showBatch = ref(false)
const showReview = ref(false)
const galleryFilter = ref<'all' | 'review' | 'accepted' | 'unlabeled'>('all')
const gallerySearch = ref('')

const project = computed(() => store.currentProjectData)
const totalPages = computed(() => Math.ceil(store.imagesTotal / store.imagesLimit))

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
  const imgs = store.images
  const totalAnnotations = imgs.reduce((sum, img) => sum + img.accepted + img.rejected, 0)
  const totalAccepted = imgs.reduce((sum, img) => sum + img.accepted, 0)
  const reviewCount = imgs.filter((img) => img.status === 'review').length
  const allClasses = new Set<string>()
  const p = project.value
  if (p?.stats.classes) p.stats.classes.forEach((c) => allClasses.add(c))
  return {
    totalImages: imgs.length,
    totalAnnotations,
    acceptRate: totalAnnotations > 0 ? Math.round((totalAccepted / totalAnnotations) * 100) : 0,
    reviewQueue: reviewCount,
    classes: allClasses.size,
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

function closeReview() {
  showReview.value = false
  store.clearSelection()
}

async function changePage(page: number) {
  await store.fetchImages(page)
}

function statusLabel(status: string) {
  if (status === 'unlabeled') return 'Unlabeled'
  if (status === 'review') return 'Review'
  if (status === 'accepted') return 'Accepted'
  return 'New'
}
</script>

<template>
  <section v-if="project" class="w-full max-w-[1400px] mx-auto">

    <!-- Hero Header -->
    <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-8">
      <div class="min-w-0">
        <button
          class="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-primary font-semibold hover:text-primary-deep transition-colors cursor-pointer mb-3"
          @click="goBack"
        >
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Dataset Workspace
        </button>
        <h1 class="text-[32px] leading-[1.1] font-bold tracking-[-0.03em] text-ink">{{ project.name }}</h1>
        <p class="text-[13px] text-ink-mute mt-2 max-w-[640px] leading-relaxed">
          Review-ready dataset for YOLO fine-tuning. Inspect detections, accept or reject annotations, then export.
        </p>
      </div>

      <div class="flex gap-2 shrink-0">
        <button
          class="h-9 px-4 text-[13px] font-medium text-ink border border-hairline rounded-(--radius-sm) bg-canvas hover:bg-canvas-soft hover:border-hairline-strong hover:-translate-y-px transition-all cursor-pointer"
          @click="showBatch = true"
        >
          Upload + Auto-Label
        </button>
        <button
          class="h-9 px-4 text-[13px] font-semibold text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep shadow-[0_4px_12px_rgba(62,207,142,0.2)] hover:shadow-[0_6px_18px_rgba(62,207,142,0.3)] hover:-translate-y-px transition-all cursor-pointer"
          @click="showExport = true"
        >
          Export
        </button>
      </div>
    </div>

    <!-- Metrics Row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="relative overflow-hidden border border-hairline rounded-(--radius-md) p-5 bg-canvas shadow-[0_4px_16px_rgba(0,0,0,0.04)] before:content-[''] before:absolute before:left-0 before:top-0 before:bottom-0 before:w-[3px] before:bg-primary">
        <label class="block text-[11px] text-ink-faint uppercase tracking-[0.06em] font-semibold mb-1.5">Total Images</label>
        <strong class="block text-[28px] font-bold tracking-[-0.02em] text-ink leading-tight">{{ metrics.totalImages }}</strong>
        <small class="block text-[12px] text-ink-mute mt-1.5">{{ project?.stats.total_images ?? 0 }} in project</small>
      </div>
      <div class="relative overflow-hidden border border-hairline rounded-(--radius-md) p-5 bg-canvas shadow-[0_4px_16px_rgba(0,0,0,0.04)] before:content-[''] before:absolute before:left-0 before:top-0 before:bottom-0 before:w-[3px] before:bg-blue-500">
        <label class="block text-[11px] text-ink-faint uppercase tracking-[0.06em] font-semibold mb-1.5">Annotations</label>
        <strong class="block text-[28px] font-bold tracking-[-0.02em] text-ink leading-tight">{{ metrics.totalAnnotations }}</strong>
        <small class="block text-[12px] text-ink-mute mt-1.5">{{ metrics.acceptRate }}% approved confidence</small>
      </div>
      <div class="relative overflow-hidden border border-hairline rounded-(--radius-md) p-5 bg-canvas shadow-[0_4px_16px_rgba(0,0,0,0.04)] before:content-[''] before:absolute before:left-0 before:top-0 before:bottom-0 before:w-[3px] before:bg-amber-400">
        <label class="block text-[11px] text-ink-faint uppercase tracking-[0.06em] font-semibold mb-1.5">Review Queue</label>
        <strong class="block text-[28px] font-bold tracking-[-0.02em] text-amber-500 leading-tight">{{ metrics.reviewQueue }}</strong>
        <small class="block text-[12px] text-ink-mute mt-1.5">Needs verification decision</small>
      </div>
      <div class="relative overflow-hidden border border-hairline rounded-(--radius-md) p-5 bg-canvas shadow-[0_4px_16px_rgba(0,0,0,0.04)]">
        <label class="block text-[11px] text-ink-faint uppercase tracking-[0.06em] font-semibold mb-1.5">Distinct Classes</label>
        <strong class="block text-[28px] font-bold tracking-[-0.02em] text-primary leading-tight">{{ metrics.classes }}</strong>
        <small class="block text-[12px] text-ink-mute mt-1.5">{{ (project?.stats.classes ?? []).join(', ') || '—' }}</small>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="bg-canvas border border-hairline rounded-(--radius-md) p-3 md:p-4 shadow-[0_4px_16px_rgba(0,0,0,0.04)] flex flex-col sm:flex-row gap-3 items-stretch sm:items-center mb-4">
      <div class="relative flex-1">
        <svg class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
        <input v-model="gallerySearch" type="text" placeholder="Filter by filename or source..." class="w-full h-[38px] pl-10 pr-4 text-[13px] bg-canvas-soft border border-hairline rounded-(--radius-sm) text-ink focus:outline-none focus:border-primary focus:shadow-[0_0_0_2px_rgba(62,207,142,0.15)] transition-all" />
      </div>
      <div class="flex border border-hairline rounded-(--radius-sm) overflow-hidden bg-canvas-soft p-[2px] shrink-0">
        <button
          class="px-3.5 py-1.5 text-[12px] font-medium rounded-[4px] cursor-pointer transition-colors"
          :class="galleryFilter === 'all' ? 'bg-canvas text-ink shadow-[0_2px_6px_rgba(0,0,0,0.08)] font-semibold' : 'text-ink-mute hover:text-ink'"
          @click="galleryFilter = 'all'"
        >All</button>
        <button
          class="px-3.5 py-1.5 text-[12px] font-medium rounded-[4px] cursor-pointer transition-colors inline-flex items-center gap-1.5"
          :class="galleryFilter === 'review' ? 'bg-canvas text-ink shadow-[0_2px_6px_rgba(0,0,0,0.08)] font-semibold' : 'text-ink-mute hover:text-ink'"
          @click="galleryFilter = 'review'"
        ><span class="w-[5px] h-[5px] rounded-full bg-amber-400" />Review</button>
        <button
          class="px-3.5 py-1.5 text-[12px] font-medium rounded-[4px] cursor-pointer transition-colors inline-flex items-center gap-1.5"
          :class="galleryFilter === 'accepted' ? 'bg-canvas text-ink shadow-[0_2px_6px_rgba(0,0,0,0.08)] font-semibold' : 'text-ink-mute hover:text-ink'"
          @click="galleryFilter = 'accepted'"
        ><span class="w-[5px] h-[5px] rounded-full bg-primary" />Accepted</button>
        <button
          class="px-3.5 py-1.5 text-[12px] font-medium rounded-[4px] cursor-pointer transition-colors"
          :class="galleryFilter === 'unlabeled' ? 'bg-canvas text-ink shadow-[0_2px_6px_rgba(0,0,0,0.08)] font-semibold' : 'text-ink-mute hover:text-ink'"
          @click="galleryFilter = 'unlabeled'"
        >Unlabeled</button>
      </div>
    </div>

    <!-- Gallery -->
    <template v-if="store.images.length">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-[16px] font-semibold text-ink">Project Files</h2>
        <span class="text-[12px] text-ink-mute font-mono">Showing {{ filteredImages.length }} of {{ store.images.length }} files</span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-5">
        <div
          v-for="img in filteredImages"
          :key="img.img_id"
          class="group text-left rounded-(--radius-md) border border-hairline bg-canvas overflow-hidden shadow-[0_4px_16px_rgba(0,0,0,0.04)] hover:border-hairline-strong hover:shadow-[0_16px_32px_rgba(0,0,0,0.1)] hover:-translate-y-1 transition-all duration-200 cursor-pointer"
          tabindex="0"
          role="button"
          @click="selectImage(img.img_id)"
          @keydown.enter="selectImage(img.img_id)"
        >
          <div class="relative aspect-4/3 bg-canvas-soft overflow-hidden">
            <img
              :src="img.image_url"
              :alt="img.filename"
              loading="lazy"
              class="absolute inset-0 w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.04]"
            />

            <!-- Bbox overlays when image has detections -->
            <template v-if="img.accepted + img.rejected > 0">
              <div class="absolute border border-primary/50 rounded-[2px] pointer-events-none" style="top: 25%; left: 18%; width: 38%; height: 32%"></div>
              <div v-if="img.accepted + img.rejected > 1" class="absolute border border-amber-400/50 rounded-[2px] pointer-events-none" style="top: 55%; left: 52%; width: 28%; height: 22%"></div>
            </template>

            <div class="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/60 to-transparent" />

            <!-- Status badge -->
            <span
              class="absolute top-2.5 left-2.5 px-2 py-[3px] rounded-[4px] text-[9px] font-bold uppercase tracking-[0.05em] border backdrop-blur-sm"
              :class="[
                img.status === 'accepted' ? 'bg-primary/90 text-on-primary border-primary/30' :
                img.status === 'review' ? 'bg-amber-400/90 text-ink border-amber-300/40' :
                img.status === 'unlabeled' ? 'bg-canvas/90 text-ink-mute border-hairline' :
                'bg-canvas/90 text-ink-mute border-hairline'
              ]"
            >
              {{ img.status === 'accepted' ? '✓ Accepted' : img.status === 'review' ? '⚠ Review' : statusLabel(img.status) }}
            </span>

            <!-- Annotations count -->
            <span class="absolute bottom-2.5 left-2.5 text-[10px] text-white/90 font-mono bg-black/60 border border-white/10 px-2 py-[3px] rounded-(--radius-sm) backdrop-blur-[4px]">
              {{ img.accepted + img.rejected }} bbox
            </span>
          </div>

          <div class="p-3.5 min-w-0">
            <p class="text-[13px] font-semibold text-ink truncate">{{ img.filename }}</p>
            <p class="text-[11px] text-ink-mute font-mono mt-0.5 truncate">
              {{ (img.source || 'image').toUpperCase() }}<template v-if="img.width && img.height"> · {{ img.width }}×{{ img.height }}</template>
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else class="min-h-[360px] border border-dashed border-hairline rounded-(--radius-lg) flex flex-col items-center justify-center text-center px-4">
      <div class="w-12 h-12 rounded-(--radius-lg) border border-hairline bg-canvas-soft flex items-center justify-center mb-4">
        <svg class="w-6 h-6 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>
      <p class="text-[15px] font-semibold text-ink mb-1">No images yet</p>
      <p class="text-[12px] text-ink-mute mb-5">Upload images or a video, then run Auto-Label.</p>
      <button
        class="px-4 py-2.5 text-[13px] font-semibold text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep shadow-[0_4px_12px_rgba(62,207,142,0.2)] transition-all cursor-pointer"
        @click="showBatch = true"
      >
        Upload Data
      </button>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-1.5 mt-8">
      <button
        class="h-9 px-3.5 text-[12px] rounded-(--radius-sm) border border-hairline bg-canvas text-ink-mute hover:bg-canvas-soft transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="store.imagesPage <= 1"
        @click="changePage(store.imagesPage - 1)"
      >Previous</button>
      <button
        v-for="p in totalPages"
        :key="p"
        class="w-9 h-9 text-[12px] rounded-(--radius-sm) transition-colors cursor-pointer"
        :class="p === store.imagesPage ? 'bg-ink text-canvas font-semibold' : 'border border-hairline bg-canvas text-ink-mute hover:bg-canvas-soft'"
        @click="changePage(p)"
      >{{ p }}</button>
      <button
        class="h-9 px-3.5 text-[12px] rounded-(--radius-sm) border border-hairline bg-canvas text-ink-mute hover:bg-canvas-soft transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="store.imagesPage >= totalPages"
        @click="changePage(store.imagesPage + 1)"
      >Next</button>
    </div>

    <ReviewPanel v-if="showReview && store.selectedImage" @close="closeReview" />
    <ExportDialog v-if="showExport" @close="showExport = false" />
    <BatchUploadDialog v-if="showBatch" @close="showBatch = false" />
  </section>
</template>
