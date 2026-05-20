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
  <div v-if="project" class="w-full max-w-[1200px] px-(--spacing-xl)">
    <!-- Header -->
    <div class="flex items-center justify-between mb-(--spacing-lg)">
      <div class="flex items-center gap-3">
        <button @click="goBack" class="text-ink-faint hover:text-ink transition-colors">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px]">{{ project.name }}</h2>
        <span class="text-[11px] px-2 py-0.5 rounded-(--radius-md) bg-ink/5 text-ink-mute">
          {{ project.stats.total_images }} images
        </span>
      </div>
      <div class="flex gap-2">
        <button
          @click="showBatch = true"
          class="px-3 py-1.5 text-[12px] font-medium text-ink-mute bg-ink/5 rounded-(--radius-md) hover:bg-ink/10 transition-colors"
        >
          Batch Upload
        </button>
        <button
          @click="showExport = true"
          class="px-3 py-1.5 text-[12px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 transition-colors"
        >
          Export
        </button>
      </div>
    </div>

    <!-- Split view -->
    <div class="flex gap-(--spacing-lg)">
      <!-- Image gallery -->
      <div class="flex-1">
        <div class="grid grid-cols-4 gap-2">
          <button
            v-for="img in store.images"
            :key="img.img_id"
            @click="selectImage(img.img_id)"
            class="aspect-square rounded-(--radius-md) border transition-colors relative overflow-hidden flex items-center justify-center text-[10px]"
            :class="[
              store.selectedImage === img.img_id
                ? 'border-primary'
                : 'border-hairline hover:border-hairline-strong',
              img.status === 'accepted' ? 'bg-primary/5' : img.status === 'review' ? 'bg-yellow-500/5' : 'bg-ink/5',
            ]"
          >
            <span :class="img.status === 'accepted' ? 'text-primary' : img.status === 'review' ? 'text-yellow-500' : 'text-ink-faint'">
              {{ img.status === 'accepted' ? '✓' : img.status === 'review' ? '⚠' : '○' }} {{ img.img_id }}
            </span>
            <span class="absolute bottom-1 right-1 text-[9px] text-ink-faint">
              {{ img.accepted + img.rejected }}
            </span>
          </button>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-(--spacing-md)">
          <button
            v-for="p in totalPages"
            :key="p"
            @click="changePage(p)"
            class="w-7 h-7 text-[11px] rounded-(--radius-md) transition-colors"
            :class="p === store.imagesPage ? 'bg-primary text-white' : 'text-ink-mute hover:bg-ink/5'"
          >
            {{ p }}
          </button>
        </div>
      </div>

      <!-- Review panel -->
      <ReviewPanel v-if="store.selectedImage" class="w-[320px] flex-shrink-0" />
      <div v-else class="w-[320px] flex-shrink-0 flex items-center justify-center text-[12px] text-ink-faint">
        Select an image to review
      </div>
    </div>

    <!-- Dialogs -->
    <ExportDialog v-if="showExport" @close="showExport = false" />
    <BatchUploadDialog v-if="showBatch" @close="showBatch = false" />
  </div>
</template>
