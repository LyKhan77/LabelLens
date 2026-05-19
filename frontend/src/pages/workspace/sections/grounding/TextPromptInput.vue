<script setup lang="ts">
import { ref } from 'vue'
import { useInferenceStore } from '../../../../shared/stores/inference'

const store = useInferenceStore()
const input = ref('')

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    const val = input.value.replace(',', '').trim()
    if (val) {
      store.addLabel(val)
      input.value = ''
    }
  }
}

function handleBlur() {
  const val = input.value.replace(',', '').trim()
  if (val) {
    store.addLabel(val)
    input.value = ''
  }
}
</script>

<template>
  <div>
    <label class="text-sm font-medium text-ink mb-1 block">
      Text Prompt
    </label>
    <p class="text-xs text-ink-mute mb-2">
      Type object labels separated by comma or Enter
    </p>

    <div class="flex flex-wrap gap-1.5 mb-2 min-h-[28px]">
      <span
        v-for="(label, idx) in store.labels"
        :key="idx"
        class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-primary text-on-primary"
      >
        {{ label }}
        <button
          class="hover:opacity-70 transition-opacity"
          @click="store.removeLabel(idx)"
        >
          ×
        </button>
      </span>
    </div>

    <input
      v-model="input"
      type="text"
      placeholder="e.g. person, car, dog"
      class="w-full px-(--spacing-sm) py-1.5 text-sm rounded-(--radius-sm) border border-hairline bg-canvas text-ink placeholder:text-ink-faint focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
      @keydown="handleKeydown"
      @blur="handleBlur"
    />
  </div>
</template>
