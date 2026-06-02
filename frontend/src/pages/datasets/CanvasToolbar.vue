<script setup lang="ts">
export type CanvasTool = 'select' | 'bbox' | 'pan'

const props = withDefaults(defineProps<{
  activeTool?: CanvasTool
  samEnabled?: boolean
  samAvailable?: boolean
}>(), {
  activeTool: 'select',
  samEnabled: true,
  samAvailable: false,
})

const emit = defineEmits<{
  'update:activeTool': [tool: CanvasTool]
  'update:samEnabled': [enabled: boolean]
}>()

const tools: { id: CanvasTool; label: string; shortcut: string; icon: string }[] = [
  { id: 'select', label: 'Select', shortcut: 'V', icon: 'select' },
  { id: 'bbox', label: 'BBox', shortcut: 'B', icon: 'bbox' },
  { id: 'pan', label: 'Pan', shortcut: 'H', icon: 'pan' },
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
      <!-- Select cursor -->
      <svg v-if="tool.icon === 'select'" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
        <path d="M13 13l6 6" />
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
    </button>

    <div class="dataset-canvas-toolbar-divider" />

    <!-- SAM toggle -->
    <button
      v-if="props.samAvailable"
      :class="{ 'is-active': props.samEnabled }"
      :title="`SAM Mask (${props.samEnabled ? 'ON' : 'OFF'}) [M]`"
      @click="emit('update:samEnabled', !props.samEnabled)"
    >
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" stroke-dasharray="3 2" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    </button>
  </div>
</template>
