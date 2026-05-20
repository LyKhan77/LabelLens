<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import ReviewPanel from './ReviewPanel.vue'
import ExportDialog from './ExportDialog.vue'
import BatchUploadDialog from './BatchUploadDialog.vue'

const store = useDatasetStore()

const showExport = ref(false)
const showBatch = ref(false)

import { ref } from 'vue'

const project = computed(() => store.currentProjectData)
const totalPages = computed(() => Math.ceil(store.imagesTotal / store.imagesLimit))

function goBack() {
  store.currentProject = null
  store.clearSelection()
}

function selectImage(imgId: string) {
  store.selectImage(imgId)
}

async function changePage(page: number) {
  await store.fetchImages(page)
}
</script>

<template>
  <div v-if="project" class="w-full max-w-[1200px] px-(--spacing-md)">
    <!-- Header -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <button @click="goBack" class="text-ink-faint hover:text-ink transition-colors">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h2 class="text-[15px] font-medium text-ink tracking-[-0.3px]">{{ project.name }}</h2>
        <span class="text-[10px] px-1.5 py-0.5 rounded bg-ink/5 text-ink-mute">
          {{ project.stats.total_images }} img &middot; {{ project.stats.total_annotations }} ann
        </span>
      </div>
      <div class="flex gap-1.5">
        <button
          @click="showBatch = true"
          class="px-2.5 py-1 text-[11px] font-medium text-ink-mute bg-ink/5 rounded hover:bg-ink/10 transition-colors"
        >
          Upload
        </button>
        <button
          @click="showExport = true"
          class="px-2.5 py-1 text-[11px] font-medium text-white bg-primary rounded hover:opacity-90 transition-colors"
        >
          Export
        </button>
      </div>
    </div>

    <!-- Split view -->
    <div class="flex gap-3">
      <!-- Image gallery -->
      <div class="flex-1 min-w-0">
        <div class="grid grid-cols-5 gap-1.5">
          <button
            v-for="img in store.images"
            :key="img.img_id"
            @click="selectImage(img.img_id)"
            class="aspect-square rounded border transition-colors relative overflow-hidden flex items-center justify-center text-[9px]"
            :class="[
              store.selectedImage === img.img_id
                ? 'border-primary ring-1 ring-primary/30'
                : 'border-hairline hover:border-hairline-strong',
              img.status === 'accepted' ? 'bg-primary/5' : img.status === 'review' ? 'bg-yellow-500/5' : img.status === 'unlabeled' ? 'bg-ink/[0.03]' : 'bg-ink/5',
            ]"
          >
            <span :class="img.status === 'accepted' ? 'text-primary' : img.status === 'review' ? 'text-yellow-500' : 'text-ink-faint'">
              {{ img.status === 'accepted' ? '✓' : img.status === 'review' ? '⚠' : img.status === 'unlabeled' ? '—' : '○' }}
            </span>
            <span class="absolute bottom-0.5 right-1 text-[8px] text-ink-faint">
              {{ img.accepted + img.rejected }}
            </span>
          </button>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 mt-2">
          <button
            v-for="p in totalPages"
            :key="p"
            @click="changePage(p)"
            class="w-6 h-6 text-[10px] rounded transition-colors"
            :class="p === store.imagesPage ? 'bg-primary text-white' : 'text-ink-mute hover:bg-ink/5'"
          >
            {{ p }}
          </button>
        </div>
      </div>

      <!-- Review panel -->
      <ReviewPanel v-if="store.selectedImage" class="w-[280px] flex-shrink-0" @close="store.clearSelection()" />
      <div v-else class="w-[280px] flex-shrink-0 flex items-center justify-center text-[11px] text-ink-faint border border-dashed border-hairline rounded">
        Select an image to review
      </div>
    </div>

    <!-- Dialogs -->
    <ExportDialog v-if="showExport" @close="showExport = false" />
    <BatchUploadDialog v-if="showBatch" @close="showBatch = false" />
  </div>
</template>
