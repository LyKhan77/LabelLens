<script setup lang="ts">
export type PoseTool = 'move' | 'bbox' | 'pan' | 'visibility'

const props = withDefaults(defineProps<{ activeTool?: PoseTool }>(), {
  activeTool: 'move',
})

const emit = defineEmits<{
  'update:activeTool': [tool: PoseTool]
  'infer-assist': []
}>()

const tools: { id: PoseTool; label: string; shortcut: string; icon: string }[] = [
  { id: 'move', label: 'Move', shortcut: 'M', icon: 'move' },
  { id: 'bbox', label: 'BBox', shortcut: 'B', icon: 'bbox' },
  { id: 'pan', label: 'Pan / Zoom', shortcut: 'H', icon: 'pan' },
  { id: 'visibility', label: 'Visibility', shortcut: 'C', icon: 'eye' },
]
</script>

<template>
  <div class="dataset-canvas-toolbar">
    <button
      v-for="tool in tools"
      :key="tool.id"
      :class="{ 'is-active': props.activeTool === tool.id }"
      :title="`${tool.label} (${tool.shortcut})`"
      @click="emit('update:activeTool', tool.id)"
    >
      <!-- Move (4-way arrows) -->
      <svg v-if="tool.icon === 'move'" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2v20M2 12h20M12 2l-3 3M12 2l3 3M12 22l-3-3M12 22l3-3M2 12l3-3M2 12l3 3M22 12l-3-3M22 12l-3 3" />
      </svg>
      <!-- BBox rectangle -->
      <svg v-else-if="tool.icon === 'bbox'" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="4 2" />
      </svg>
      <!-- Pan hand -->
      <svg v-else-if="tool.icon === 'pan'" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 11V6a2 2 0 00-4 0v5" />
        <path d="M14 10V4a2 2 0 00-4 0v6" />
        <path d="M10 10.5V6a2 2 0 00-4 0v8" />
        <path d="M18 8a2 2 0 014 0v6a8 8 0 01-8 8H12a8 8 0 01-6-2.69L4 17.5" />
      </svg>
      <!-- Visibility eye -->
      <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    </button>

    <div class="dataset-canvas-toolbar-divider" />

    <button
      title="Infer Assist (AI pose detection)"
      @click="emit('infer-assist')"
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3l1.912 5.813a2 2 0 001.275 1.275L21 12l-5.813 1.912a2 2 0 00-1.275 1.275L12 21l-1.912-5.813a2 2 0 00-1.275-1.275L3 12l5.813-1.912a2 2 0 001.275-1.275L12 3z" />
      </svg>
    </button>
  </div>
</template>
