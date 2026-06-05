<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ClassificationLabelAnnotation } from '../../shared/api/dataset'

const props = defineProps<{
  mode: 'single' | 'multi'
  labels: ClassificationLabelAnnotation[]
  knownLabels: string[]
  classColors: Record<string, string>
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [labels: { label: string; confidence?: number; accepted?: boolean; source?: string }[]]
}>()

const selected = ref<Set<string>>(new Set())
const localLabels = ref<string[]>([])
const draftLabel = ref('')

watch(
  () => props.labels,
  () => {
    selected.value = new Set(props.labels.filter((l) => l.accepted).map((l) => l.label))
    localLabels.value = []
  },
  { immediate: true, deep: true },
)

const allLabels = computed(() => {
  const labels = new Set(props.knownLabels)
  for (const label of props.labels) labels.add(label.label)
  for (const label of localLabels.value) labels.add(label)
  return Array.from(labels).sort((a, b) => a.localeCompare(b))
})

const canSave = computed(() => selected.value.size > 0 && !props.saving)

const activeLabels = computed(() => Array.from(selected.value))

function colorFor(label: string): string {
  return props.classColors[label] ?? '#6B7280'
}

function toggle(label: string) {
  const next = new Set(selected.value)
  if (props.mode === 'single') {
    next.clear()
    next.add(label)
  } else if (next.has(label)) {
    next.delete(label)
  } else {
    next.add(label)
  }
  selected.value = next
}

function addDraftLabel() {
  const label = draftLabel.value.trim()
  if (!label) return
  if (!localLabels.value.includes(label) && !allLabels.value.includes(label)) {
    localLabels.value = [...localLabels.value, label]
  }
  draftLabel.value = ''
}

function save() {
  emit('save', Array.from(selected.value).map((label) => ({
    label,
    confidence: 1,
    accepted: true,
    source: 'manual',
  })))
}
</script>

<template>
  <section class="cls-panel">
    <!-- Header -->
    <div class="cls-header">
      <span class="cls-title">Image Labels</span>
      <span class="cls-badge">{{ mode === 'single' ? 'Single' : 'Multi' }}</span>
    </div>

    <!-- Active label indicator -->
    <div class="cls-active-block">
      <span class="cls-active-label">Active Label</span>
      <template v-if="activeLabels.length">
        <div class="cls-active-values">
          <span
            v-for="al in activeLabels"
            :key="al"
            class="cls-active-chip"
            :style="{ '--chip-color': colorFor(al) }"
          >
            <span class="cls-active-dot" />
            {{ al }}
          </span>
        </div>
      </template>
      <span v-else class="cls-active-none">No active label selected</span>
    </div>

    <!-- Label chips -->
    <div v-if="allLabels.length" class="cls-chips">
      <button
        v-for="label in allLabels"
        :key="label"
        type="button"
        class="cls-chip"
        :class="{ 'cls-chip--selected': selected.has(label) }"
        :style="{ '--chip-color': colorFor(label) }"
        @click="toggle(label)"
      >
        <span class="cls-chip-dot" />
        <span class="cls-chip-text">{{ label }}</span>
        <svg v-if="selected.has(label)" class="cls-chip-check" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 6L5 8.5L9.5 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </div>
    <p v-else class="cls-empty">No labels yet. Add the first label below.</p>

    <!-- Add label input -->
    <div class="cls-input-row">
      <input
        v-model="draftLabel"
        type="text"
        class="cls-input"
        placeholder="Type new label…"
        @keydown.enter.prevent="addDraftLabel"
      />
      <button
        class="dataset-secondary-button"
        type="button"
        :disabled="!draftLabel.trim()"
        @click="addDraftLabel"
      >
        <svg viewBox="0 0 14 14" fill="none" width="14" height="14">
          <path d="M7 2v10M2 7h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        Add
      </button>
    </div>

    <!-- Save -->
    <button class="dataset-primary-button w-full" :disabled="!canSave" @click="save">
      <span v-if="saving" class="cls-save-spinner" />
      {{ saving ? 'Saving…' : 'Save Labels' }}
    </button>
  </section>
</template>

<style scoped>
.cls-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 12px;
}

/* Header */
.cls-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cls-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink);
  letter-spacing: 0.02em;
}
.cls-badge {
  font-size: 9px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-ink-mute);
  border: 1px solid var(--color-hairline);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Active label block */
.cls-active-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-canvas-soft);
  border: 1px solid var(--color-hairline);
}
.cls-active-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-ink-faint);
}
.cls-active-values {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cls-active-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  color: var(--chip-color);
  background: color-mix(in srgb, var(--chip-color) 14%, var(--color-canvas));
  border: 1px solid color-mix(in srgb, var(--chip-color) 25%, transparent);
}
.cls-active-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--chip-color);
  flex-shrink: 0;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--chip-color) 25%, transparent);
}
.cls-active-none {
  font-size: 11px;
  color: var(--color-ink-faint);
  font-style: italic;
}

/* Label chips */
.cls-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 140px;
  overflow-y: auto;
  padding: 2px 0;
}
.cls-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px 0 7px;
  border: 1.5px solid color-mix(in srgb, var(--chip-color) 35%, var(--color-hairline));
  border-radius: 999px;
  background: transparent;
  color: var(--color-ink-mute);
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  transition: all 0.12s ease;
  line-height: 1;
}
.cls-chip:hover {
  border-color: color-mix(in srgb, var(--chip-color) 60%, var(--color-hairline));
  color: var(--color-ink);
}
.cls-chip--selected {
  background: color-mix(in srgb, var(--chip-color) 10%, transparent);
  border-color: var(--chip-color);
  color: var(--chip-color);
  font-weight: 600;
}
.cls-chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--chip-color);
  flex-shrink: 0;
  opacity: 0.5;
  transition: opacity 0.12s ease;
}
.cls-chip--selected .cls-chip-dot {
  opacity: 1;
}
.cls-chip-text {
  white-space: nowrap;
}
.cls-chip-check {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  color: var(--chip-color);
}

/* Empty */
.cls-empty {
  font-size: 11px;
  color: var(--color-ink-faint);
  padding: 10px 0;
  line-height: 1.5;
}

/* Input row */
.cls-input-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}
.cls-input {
  width: 100%;
  min-width: 0;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-sm);
  background: var(--color-canvas-soft);
  color: var(--color-ink);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s ease;
}
.cls-input:focus {
  border-color: var(--color-surface-border);
}
.cls-input::placeholder {
  color: var(--color-ink-faint);
}

/* Save spinner */
.cls-save-spinner {
  width: 12px;
  height: 12px;
  border: 1.5px solid color-mix(in srgb, var(--color-on-primary) 30%, transparent);
  border-top-color: var(--color-on-primary);
  border-radius: 50%;
  animation: cls-spin 0.6s linear infinite;
}
@keyframes cls-spin {
  to { transform: rotate(360deg); }
}
</style>
