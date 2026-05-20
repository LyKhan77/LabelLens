<script setup lang="ts">
import { ref } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'

const store = useDatasetStore()

const showCreate = ref(false)
const newName = ref('')
const newClasses = ref('')
const creating = ref(false)

async function createProject() {
  if (!newName.value.trim()) return
  creating.value = true
  const classes = newClasses.value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  try {
    await store.createProject(newName.value.trim(), classes)
    showCreate.value = false
    newName.value = ''
    newClasses.value = ''
  } finally {
    creating.value = false
  }
}

function openProject(name: string) {
  store.currentProject = name
  store.fetchImages(1)
}

async function deleteProject(name: string) {
  if (!confirm(`Delete dataset "${name}"? This cannot be undone.`)) return
  await store.deleteProject(name)
}
</script>

<template>
  <section class="w-full max-w-[1180px] mx-auto">
    <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-8">
      <div>
        <p class="text-[12px] uppercase tracking-wide text-ink-faint mb-2">Dataset Manager</p>
        <h1 class="text-[32px] leading-tight font-medium tracking-[-0.72px] text-ink">Review-ready datasets for YOLO fine-tuning</h1>
        <p class="text-[13px] text-ink-mute mt-2 max-w-[620px]">Upload images or sampled video frames, auto-label with YOLOE grounding, review detections, then export YOLO or COCO.</p>
      </div>
      <button
        class="px-3 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep transition-colors cursor-pointer"
        @click="showCreate = true"
      >
        New Dataset
      </button>
    </div>

    <div v-if="store.projects.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
      <div
        v-for="p in store.projects"
        :key="p.name"
        class="group relative text-left p-6 rounded-(--radius-lg) border border-hairline bg-canvas shadow-[0_4px_16px_rgba(0,0,0,0.04)] hover:border-hairline-strong hover:shadow-[0_16px_32px_rgba(0,0,0,0.1)] hover:-translate-y-1 transition-all duration-200 cursor-pointer"
        tabindex="0"
        role="button"
        @click="openProject(p.name)"
        @keydown.enter="openProject(p.name)"
      >
        <button
          class="absolute top-4 right-4 p-1.5 rounded-(--radius-sm) opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity text-ink-faint hover:text-red-500 hover:bg-red-500/10 cursor-pointer"
          @click.stop="deleteProject(p.name)"
          title="Delete dataset"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
          </svg>
        </button>

        <div class="w-10 h-10 rounded-(--radius-md) border border-hairline bg-canvas-soft flex items-center justify-center mb-4">
          <svg class="w-5 h-5 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></svg>
        </div>
        <h2 class="text-[16px] font-semibold text-ink truncate pr-8">{{ p.name }}</h2>
        <p class="text-[13px] text-ink-mute mt-1">{{ p.stats.total_images }} images · {{ p.stats.total_annotations }} annotations</p>
        <div class="flex flex-wrap gap-2 mt-4">
          <span class="text-[11px] px-2.5 py-1 rounded-full bg-primary/10 text-primary font-medium">{{ p.stats.accepted }} accepted</span>
          <span v-if="p.stats.rejected" class="text-[11px] px-2.5 py-1 rounded-full bg-red-500/10 text-red-400 font-medium">{{ p.stats.rejected }} rejected</span>
          <span v-if="p.stats.classes.length" class="text-[11px] px-2.5 py-1 rounded-full bg-canvas-soft text-ink-mute font-medium">{{ p.stats.classes.length }} classes</span>
        </div>
      </div>
    </div>

    <div v-else class="min-h-[360px] border border-dashed border-hairline rounded-(--radius-lg) flex flex-col items-center justify-center text-center px-4">
      <div class="w-11 h-11 rounded-(--radius-lg) border border-hairline bg-canvas-soft flex items-center justify-center mb-3">
        <svg class="w-6 h-6 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
      </div>
      <p class="text-[15px] font-medium text-ink mb-1">No datasets yet</p>
      <p class="text-[12px] text-ink-mute mb-4">Create a dataset to start collecting labeled images.</p>
      <button class="px-3 py-2 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep transition-colors cursor-pointer" @click="showCreate = true">
        New Dataset
      </button>
    </div>

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition ease-in duration-150"
      leave-to-class="opacity-0"
    >
      <div v-if="showCreate" class="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" @click.self="showCreate = false">
        <div class="bg-canvas rounded-(--radius-xl) w-full max-w-[440px] border border-hairline shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]">
          <div class="flex items-start justify-between p-6 pb-0">
            <div>
              <h3 class="text-[18px] font-medium text-ink tracking-[-0.3px]">New Dataset</h3>
              <p class="text-[12px] text-ink-mute mt-1">Create a new labeling project</p>
            </div>
            <button class="w-8 h-8 rounded-(--radius-sm) flex items-center justify-center text-ink-faint hover:bg-canvas-soft hover:text-ink transition-colors cursor-pointer" @click="showCreate = false">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>

          <div class="p-6">
            <label class="block mb-4">
              <span class="text-[11px] text-ink-mute uppercase tracking-wide">Name</span>
              <input v-model="newName" placeholder="product-defects" class="block w-full mt-1.5 px-3.5 py-2.5 text-[13px] bg-canvas border border-hairline rounded-(--radius-sm) text-ink focus:outline-none focus:border-primary transition-colors" />
            </label>

            <label class="block">
              <span class="text-[11px] text-ink-mute uppercase tracking-wide">Classes (optional)</span>
              <input v-model="newClasses" placeholder="scratch, dent, crack" class="block w-full mt-1.5 px-3.5 py-2.5 text-[13px] bg-canvas border border-hairline rounded-(--radius-sm) text-ink focus:outline-none focus:border-primary transition-colors" />
            </label>
          </div>

          <div class="flex justify-between px-6 pb-6">
            <button class="px-4 py-2.5 text-[13px] text-ink-mute rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer" @click="showCreate = false">Cancel</button>
            <button class="px-5 py-2.5 text-[13px] font-medium text-on-primary bg-primary rounded-(--radius-sm) hover:bg-primary-deep disabled:opacity-50 transition-colors cursor-pointer" :disabled="creating || !newName.trim()" @click="createProject">
              {{ creating ? 'Creating...' : 'Create' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </section>
</template>
