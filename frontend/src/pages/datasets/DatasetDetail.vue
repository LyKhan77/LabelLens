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

const project = computed(() => store.currentProjectData)
const totalPages = computed(() => Math.ceil(store.imagesTotal / store.imagesLimit))

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
  <section v-if="project" class="w-full max-w-[1440px] mx-auto">
    <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-(--spacing-xl)">
      <div class="min-w-0">
        <button
          class="inline-flex items-center gap-1.5 text-[12px] text-ink-mute hover:text-ink transition-colors cursor-pointer mb-3"
          @click="goBack"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Datasets
        </button>
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-[28px] leading-tight font-medium tracking-[-0.42px] text-ink truncate">
            {{ project.name }}
          </h1>
          <span class="text-[12px] px-2 py-1 rounded-(--radius-sm) bg-canvas-soft border border-hairline text-ink-mute">
            {{ project.stats.total_images }} images · {{ project.stats.total_annotations }} annotations
          </span>
        </div>
      </div>

      <div class="flex gap-2">
        <button
          class="px-3 py-2 text-[13px] font-medium text-ink border border-hairline rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer"
          @click="showBatch = true"
        >
          Upload + Auto-Label
        </button>
        <button
          class="px-3 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep transition-colors cursor-pointer"
          @click="showExport = true"
        >
          Export
        </button>
      </div>
    </div>

    <div v-if="store.images.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-3">
      <button
        v-for="img in store.images"
        :key="img.img_id"
        class="group text-left rounded-(--radius-md) border border-hairline bg-canvas overflow-hidden hover:border-hairline-strong hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)] focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all cursor-pointer"
        @click="selectImage(img.img_id)"
      >
        <div class="relative aspect-[4/3] bg-canvas-soft overflow-hidden">
          <img
            :src="img.image_url"
            :alt="img.filename"
            loading="lazy"
            class="absolute inset-0 w-full h-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
          />
          <div class="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/55 to-transparent" />
          <span
            class="absolute top-2 left-2 px-1.5 py-0.5 rounded-(--radius-xs) text-[10px] font-medium border backdrop-blur-sm"
            :class="[
              img.status === 'accepted' ? 'bg-primary/90 text-on-primary border-primary/30' :
              img.status === 'review' ? 'bg-yellow-400/90 text-ink border-yellow-300/40' :
              img.status === 'unlabeled' ? 'bg-canvas/90 text-ink-mute border-hairline' :
              'bg-canvas/90 text-ink-mute border-hairline'
            ]"
          >
            {{ statusLabel(img.status) }}
          </span>
          <span class="absolute bottom-2 left-2 text-[11px] text-white/90 font-mono">
            {{ img.accepted + img.rejected }} ann
          </span>
        </div>
        <div class="p-2 min-w-0">
          <p class="text-[12px] font-medium text-ink truncate">{{ img.filename }}</p>
          <p class="text-[10px] text-ink-faint truncate">
            {{ img.source || 'image' }}<template v-if="img.width && img.height"> · {{ img.width }}×{{ img.height }}</template>
          </p>
        </div>
      </button>
    </div>

    <div v-else class="min-h-[320px] border border-dashed border-hairline rounded-(--radius-lg) flex flex-col items-center justify-center text-center px-4">
      <p class="text-[15px] font-medium text-ink mb-1">No images yet</p>
      <p class="text-[12px] text-ink-mute mb-4">Upload images or a video, then run Auto-Label.</p>
      <button
        class="px-3 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep transition-colors cursor-pointer"
        @click="showBatch = true"
      >
        Upload Data
      </button>
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 mt-(--spacing-xl)">
      <button
        v-for="p in totalPages"
        :key="p"
        class="w-8 h-8 text-[12px] rounded-(--radius-sm) transition-colors cursor-pointer"
        :class="p === store.imagesPage ? 'bg-primary text-on-primary' : 'text-ink-mute hover:bg-canvas-soft'"
        @click="changePage(p)"
      >
        {{ p }}
      </button>
    </div>

    <ReviewPanel v-if="showReview && store.selectedImage" @close="closeReview" />
    <ExportDialog v-if="showExport" @close="showExport = false" />
    <BatchUploadDialog v-if="showBatch" @close="showBatch = false" />
  </section>
</template>
