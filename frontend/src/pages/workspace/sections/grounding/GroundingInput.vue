<script setup lang="ts">
import { useInferenceStore } from '../../../../shared/stores/inference'
import TextPromptInput from './TextPromptInput.vue'
import VisualPromptInput from './VisualPromptInput.vue'

const store = useInferenceStore()
</script>

<template>
  <div v-if="store.inferenceMode === 'prompt'">
    <p class="text-xs font-medium text-ink-mute uppercase tracking-wider mb-2">
      Step 1 — Grounding Prompt
    </p>

    <!-- Tab toggle -->
    <div class="flex rounded-(--radius-sm) border border-hairline overflow-hidden mb-3">
      <button
        class="flex-1 px-3 py-1.5 text-sm font-medium transition-colors"
        :class="store.promptMode === 'text'
          ? 'bg-primary text-on-primary'
          : 'bg-canvas text-ink-mute hover:text-ink'"
        @click="store.promptMode = 'text'"
      >
        Text Prompt
      </button>
      <button
        class="flex-1 px-3 py-1.5 text-sm font-medium transition-colors"
        :class="store.promptMode === 'visual'
          ? 'bg-primary text-on-primary'
          : 'bg-canvas text-ink-mute hover:text-ink'"
        @click="store.promptMode = 'visual'"
      >
        Visual Prompt
      </button>
    </div>

    <TextPromptInput v-if="store.promptMode === 'text'" />
    <VisualPromptInput v-else />
  </div>
</template>
