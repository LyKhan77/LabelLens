<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'

const store = useDatasetStore()

const showCreate = ref(false)
const newName = ref('')
const newClasses = ref('')
const creating = ref(false)
const deleting = ref<string | null>(null)

const totals = computed(() => store.projects.reduce(
  (acc, p) => {
    acc.images += p.stats.total_images
    acc.annotations += p.stats.total_annotations
    acc.accepted += p.stats.accepted
    acc.classes += p.stats.classes.length
    return acc
  },
  { images: 0, annotations: 0, accepted: 0, classes: 0 },
))

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
  deleting.value = name
  try {
    await store.deleteProject(name)
  } finally {
    deleting.value = null
  }
}
</script>

<template>
  <section class="dataset-list-page">
    <div class="dataset-list-hero">
      <div class="min-w-0">
        <p class="text-[11px] uppercase tracking-wide text-ink-faint mb-2">Dataset Manager</p>
        <h1 class="text-[32px] leading-[1.1] font-medium tracking-[-0.72px] text-ink">Review-ready datasets for YOLO fine-tuning</h1>
        <p class="text-[13px] text-ink-mute mt-2 max-w-[720px] leading-relaxed">
          Upload images or sampled video frames, auto-label with YOLOE grounding, review detections, then export YOLO or COCO.
        </p>
      </div>
      <button class="dataset-primary-button" @click="showCreate = true">
        New Dataset
      </button>
    </div>

    <div class="dataset-list-metrics">
      <div class="dataset-list-metric is-primary">
        <span>Projects</span>
        <strong>{{ store.projects.length }}</strong>
      </div>
      <div class="dataset-list-metric">
        <span>Images</span>
        <strong>{{ totals.images }}</strong>
      </div>
      <div class="dataset-list-metric">
        <span>Annotations</span>
        <strong>{{ totals.annotations }}</strong>
      </div>
      <div class="dataset-list-metric">
        <span>Classes</span>
        <strong>{{ totals.classes }}</strong>
      </div>
    </div>

    <div v-if="store.projects.length" class="dataset-project-grid">
      <article
        v-for="p in store.projects"
        :key="p.name"
        class="dataset-project-card"
      >
        <button class="dataset-project-open" @click="openProject(p.name)" @keydown.enter="openProject(p.name)">
          <span class="dataset-project-icon">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="m21 15-5-5L5 21" />
            </svg>
          </span>
          <span class="dataset-project-main">
            <strong>{{ p.name }}</strong>
            <span>{{ p.stats.total_images }} images · {{ p.stats.total_annotations }} annotations</span>
          </span>
        </button>

        <div class="dataset-project-footer">
          <div class="dataset-project-tags">
            <span class="is-primary">{{ p.stats.accepted }} accepted</span>
            <span v-if="p.stats.rejected">{{ p.stats.rejected }} rejected</span>
            <span>{{ p.stats.classes.length }} classes</span>
          </div>
          <button
            class="dataset-delete-button"
            :disabled="deleting === p.name"
            @click="deleteProject(p.name)"
          >
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
            </svg>
            {{ deleting === p.name ? 'Deleting' : 'Delete' }}
          </button>
        </div>
      </article>
    </div>

    <div v-else class="dataset-list-empty">
      <div class="w-11 h-11 rounded-(--radius-lg) border border-hairline bg-canvas-soft flex items-center justify-center mb-3">
        <svg class="w-6 h-6 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
      </div>
      <p class="text-[15px] font-medium text-ink mb-1">No datasets yet</p>
      <p class="text-[12px] text-ink-mute mb-4">Create a dataset to start collecting labeled images.</p>
      <button class="dataset-primary-button" @click="showCreate = true">
        New Dataset
      </button>
    </div>

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 scale-[0.98]"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-to-class="opacity-0 scale-[0.98]"
    >
      <div v-if="showCreate" class="dataset-dialog-backdrop" @click.self="showCreate = false">
        <div class="dataset-create-dialog">
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
              <input v-model="newName" placeholder="product-defects" class="dataset-text-input" />
            </label>

            <label class="block">
              <span class="text-[11px] text-ink-mute uppercase tracking-wide">Classes (optional)</span>
              <input v-model="newClasses" placeholder="scratch, dent, crack" class="dataset-text-input" />
            </label>
          </div>

          <div class="flex justify-between px-6 pb-6">
            <button class="px-4 py-2.5 text-[13px] text-ink-mute rounded-(--radius-sm) hover:bg-canvas-soft transition-colors cursor-pointer" @click="showCreate = false">Cancel</button>
            <button class="dataset-primary-button px-5" :disabled="creating || !newName.trim()" @click="createProject">
              {{ creating ? 'Creating...' : 'Create' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </section>
</template>
