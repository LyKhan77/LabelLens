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
  <div class="w-full max-w-[680px] px-(--spacing-xl)">
    <div class="text-center mb-(--spacing-huge)">
      <h2 class="text-[18px] font-medium text-ink tracking-[-0.42px] mb-(--spacing-xs)">
        Dataset Manager
      </h2>
      <p class="text-[13px] text-ink-mute leading-[1.45]">
        Create and manage labeled datasets for YOLO fine-tuning
      </p>
    </div>

    <!-- Project cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-(--spacing-lg)">
      <button
        v-for="p in store.projects"
        :key="p.name"
        @click="openProject(p.name)"
        class="group relative flex flex-col items-start p-(--spacing-xxl) rounded-(--radius-lg) border border-hairline bg-canvas transition-all duration-150 text-left cursor-pointer hover:border-hairline-strong hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
      >
        <!-- Delete button -->
        <button
          @click.stop="deleteProject(p.name)"
          class="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity text-ink-faint hover:text-red-400"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
          </svg>
        </button>

        <h3 class="text-[16px] font-medium text-ink mb-(--spacing-xs)">{{ p.name }}</h3>
        <p class="text-[12px] text-ink-mute">
          {{ p.stats.total_images }} images &middot; {{ p.stats.total_annotations }} annotations
        </p>
        <div class="flex gap-2 mt-(--spacing-sm)">
          <span
            v-if="p.stats.accepted > 0"
            class="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary"
          >
            {{ p.stats.accepted }} accepted
          </span>
          <span
            v-if="p.stats.rejected > 0"
            class="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400"
          >
            {{ p.stats.rejected }} rejected
          </span>
        </div>
      </button>

      <!-- New dataset card -->
      <button
        @click="showCreate = true"
        class="flex flex-col items-center justify-center p-(--spacing-xxl) rounded-(--radius-lg) border-2 border-dashed border-hairline bg-canvas transition-all duration-150 cursor-pointer hover:border-primary/30"
      >
        <svg class="w-6 h-6 text-ink-faint mb-(--spacing-sm)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        <span class="text-[13px] text-ink-faint">New Dataset</span>
      </button>
    </div>

    <!-- Empty state -->
    <div v-if="!store.projectsLoading && store.projects.length === 0" class="text-center mt-(--spacing-xxl)">
      <p class="text-[13px] text-ink-faint">No datasets yet. Create one to start labeling.</p>
    </div>

    <!-- Create dialog -->
    <div
      v-if="showCreate"
      class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      @click.self="showCreate = false"
    >
      <div class="bg-canvas rounded-(--radius-lg) p-(--spacing-xxl) w-full max-w-[400px] border border-hairline">
        <h3 class="text-[16px] font-medium text-ink mb-(--spacing-lg)">New Dataset</h3>

        <label class="block mb-(--spacing-md)">
          <span class="text-[12px] text-ink-mute uppercase tracking-wide">Name</span>
          <input
            v-model="newName"
            placeholder="e.g. product-defects"
            class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
          />
        </label>

        <label class="block mb-(--spacing-lg)">
          <span class="text-[12px] text-ink-mute uppercase tracking-wide">Classes (optional, comma-separated)</span>
          <input
            v-model="newClasses"
            placeholder="defect, scratch, dent"
            class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary"
          />
        </label>

        <div class="flex gap-3 justify-end">
          <button
            @click="showCreate = false"
            class="px-4 py-2 text-[13px] text-ink-mute rounded-(--radius-md) hover:bg-ink/5"
          >
            Cancel
          </button>
          <button
            @click="createProject"
            :disabled="creating || !newName.trim()"
            class="px-4 py-2 text-[13px] font-medium text-white bg-primary rounded-(--radius-md) hover:opacity-90 disabled:opacity-50"
          >
            {{ creating ? 'Creating...' : 'Create' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
