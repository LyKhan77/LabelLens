<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'
import type { DetectionAnnotation } from '../../shared/api/dataset'

const store = useDatasetStore()
const imageSrc = ref('')

const annotations = computed(() => store.currentAnnotations?.annotations)
const detections = computed(() => annotations.value?.detections ?? [])

const classes = computed(() => {
  const cls = new Map<string, number>()
  for (const d of detections.value) {
    cls.set(d.label, (cls.get(d.label) ?? 0) + 1)
  }
  return Array.from(cls.entries())
})

const acceptedCount = computed(() => detections.value.filter((d) => d.accepted).length)
const rejectedCount = computed(() => detections.value.filter((d) => !d.accepted).length)

// Load image when annotation changes
import { watch } from 'vue'
watch(
  () => store.selectedImage,
  async () => {
    if (!store.currentProject || !store.selectedImage) {
      imageSrc.value = ''
      return
    }
    try {
      const resp = await fetch(`/api/datasets/${store.currentProject}/images/${store.selectedImage}/file`)
      if (resp.ok) {
        const blob = await resp.blob()
        imageSrc.value = URL.createObjectURL(blob)
      }
    } catch {
      imageSrc.value = ''
    }
  },
  { immediate: true },
)

function toggleAccept(det: DetectionAnnotation) {
  if (!store.currentProject || !store.selectedImage) return
  store.reviewDetection(store.selectedImage, [{ id: det.id, accepted: !det.accepted }])
}

function isVisible(det: DetectionAnnotation): boolean {
  return store.isDetectionVisible(det)
}

function toggleClassVis(cls: string) {
  store.toggleClassVisibility(cls)
}

function toggleDetVis(id: number) {
  store.toggleDetectionVisibility(id)
}

function isClassHidden(cls: string): boolean {
  return store.overlayState.hiddenClasses.has(cls)
}

// Navigation
function navigateNext() {
  if (!store.currentProject) return
  const idx = store.images.findIndex((i) => i.img_id === store.selectedImage)
  if (idx >= 0 && idx < store.images.length - 1) {
    store.selectImage(store.images[idx + 1].img_id)
  }
}

function navigatePrev() {
  if (!store.currentProject) return
  const idx = store.images.findIndex((i) => i.img_id === store.selectedImage)
  if (idx > 0) {
    store.selectImage(store.images[idx - 1].img_id)
  }
}

// Box rendering
const boxStyle = computed(() => {
  const dets = detections.value
    .filter((d) => isVisible(d) && store.overlayState.showBbox)
    .map((d) => ({
      left: `${(d.box[0] / (annotations.value?.width ?? 1)) * 100}%`,
      top: `${(d.box[1] / (annotations.value?.height ?? 1)) * 100}%`,
      width: `${((d.box[2] - d.box[0]) / (annotations.value?.width ?? 1)) * 100}%`,
      height: `${((d.box[3] - d.box[1]) / (annotations.value?.height ?? 1)) * 100}%`,
      label: d.label,
      confidence: d.confidence,
      color: `hsl(${(d.id * 47) % 360}, 70%, 55%)`,
    }))
  return dets
})

const COLORS = [
  '#3ecf8e', '#f59e0b', '#3b82f6', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]

function detColor(idx: number): string {
  return COLORS[idx % COLORS.length]
}
</script>

<template>
  <div class="flex flex-col border border-hairline rounded-(--radius-lg) bg-canvas overflow-hidden h-fit">
    <!-- Image viewer -->
    <div class="relative bg-black/5 aspect-video overflow-hidden">
      <img v-if="imageSrc" :src="imageSrc" class="w-full h-full object-contain" />

      <!-- BBox overlays -->
      <template v-if="imageSrc && store.overlayState.showBbox">
        <div
          v-for="box in boxStyle"
          :key="box.label + box.left"
          class="absolute border-2 pointer-events-none"
          :style="{
            left: box.left,
            top: box.top,
            width: box.width,
            height: box.height,
            borderColor: box.color,
          }"
        >
          <span
            v-if="store.overlayState.showLabels"
            class="absolute -top-5 left-0 text-[9px] px-1 rounded-sm text-white whitespace-nowrap"
            :style="{ backgroundColor: box.color }"
          >
            {{ box.label }} {{ (box.confidence * 100).toFixed(0) }}%
          </span>
        </div>
      </template>

      <!-- Global overlay controls -->
      <div class="absolute top-2 left-2 flex gap-1">
        <button
          @click="store.toggleOverlay('showBbox')"
          class="text-[10px] px-1.5 py-0.5 rounded transition-colors"
          :class="store.overlayState.showBbox ? 'bg-primary/80 text-white' : 'bg-black/30 text-white/60'"
        >
          BBox
        </button>
        <button
          @click="store.toggleOverlay('showLabels')"
          class="text-[10px] px-1.5 py-0.5 rounded transition-colors"
          :class="store.overlayState.showLabels ? 'bg-primary/80 text-white' : 'bg-black/30 text-white/60'"
        >
          Labels
        </button>
        <button
          @click="store.toggleOverlay('showMasks')"
          class="text-[10px] px-1.5 py-0.5 rounded transition-colors"
          :class="store.overlayState.showMasks ? 'bg-primary/80 text-white' : 'bg-black/30 text-white/60'"
        >
          Mask
        </button>
      </div>
    </div>

    <!-- Class filters -->
    <div v-if="classes.length > 0" class="px-3 py-2 border-b border-hairline bg-ink/[0.02]">
      <div class="text-[10px] text-ink-faint uppercase tracking-wide mb-1.5">Class Filters</div>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="([cls, count], i) in classes"
          :key="cls"
          @click="toggleClassVis(cls)"
          class="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] transition-opacity"
          :style="{ opacity: isClassHidden(cls) ? 0.35 : 1 }"
        >
          <span>{{ isClassHidden(cls) ? '👁‍🗨' : '👁' }}</span>
          <span class="font-medium" :style="{ color: detColor(i) }">{{ cls }}</span>
          <span class="text-ink-faint">({{ count }})</span>
        </button>
      </div>
    </div>

    <!-- Detection list -->
    <div class="flex-1 overflow-y-auto max-h-[240px]">
      <div
        v-for="det in detections"
        :key="det.id"
        class="flex items-center gap-2 px-3 py-1.5 border-b border-hairline/50 transition-opacity"
        :class="{ 'opacity-40': !det.accepted }"
      >
        <!-- Per-object visibility toggle -->
        <button @click="toggleDetVis(det.id)" class="text-[12px]">
          {{ isVisible(det) ? '👁' : '👁‍🗨' }}
        </button>

        <!-- Color dot -->
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :style="{ backgroundColor: detColor(det.id) }"
        />

        <!-- Detection info -->
        <div class="flex-1 min-w-0">
          <div class="flex justify-between items-center">
            <span
              class="text-[12px] font-medium"
              :class="det.accepted ? '' : 'line-through text-ink-faint'"
              :style="{ color: det.accepted ? detColor(det.id) : undefined }"
            >
              {{ det.label }}
            </span>
            <span class="text-[11px] text-ink-faint">{{ (det.confidence * 100).toFixed(1) }}%</span>
          </div>
        </div>

        <!-- Accept/reject -->
        <button
          @click="toggleAccept(det)"
          class="text-[10px] px-1.5 py-0.5 rounded transition-colors"
          :class="det.accepted ? 'bg-primary/15 text-primary' : 'bg-red-500/15 text-red-400'"
        >
          {{ det.accepted ? '✓' : '✗' }}
        </button>
      </div>
    </div>

    <!-- Summary bar -->
    <div class="flex items-center justify-between px-3 py-2 border-t border-hairline bg-ink/[0.02] text-[11px]">
      <span class="text-primary">{{ acceptedCount }} accepted</span>
      <span class="text-red-400">{{ rejectedCount }} rejected</span>
      <div class="flex gap-1">
        <button @click="navigatePrev" class="text-ink-faint hover:text-ink">&larr;</button>
        <button @click="navigateNext" class="text-ink-faint hover:text-ink">&rarr;</button>
      </div>
    </div>
  </div>
</template>
