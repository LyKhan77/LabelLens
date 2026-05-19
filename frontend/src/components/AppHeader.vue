<script setup lang="ts">
import { useBackendStatus } from '../composables/useBackendStatus'
import { useTheme } from '../composables/useTheme'

const { connected } = useBackendStatus()
const { theme, toggle } = useTheme()
</script>

<template>
  <header class="flex items-center justify-between px-(--spacing-lg) h-14 border-b border-hairline bg-canvas">
    <div class="flex items-center gap-2">
      <div class="w-6 h-6 rounded-(--radius-sm) bg-primary flex items-center justify-center">
        <svg class="w-4 h-4 text-on-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
      </div>
      <span class="text-ink font-medium text-lg tracking-tight">LabelLens</span>
    </div>

    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full transition-colors"
          :class="connected ? 'bg-primary' : 'bg-red-500'"
        />
        <span class="text-xs text-ink-mute">
          {{ connected ? 'Backend Connected' : 'Backend Offline' }}
        </span>
      </div>

      <button
        class="p-1.5 rounded-(--radius-sm) border border-hairline hover:bg-canvas-soft transition-colors cursor-pointer"
        :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
        @click="toggle()"
      >
        <!-- Sun icon (shown in dark mode) -->
        <svg v-if="theme === 'dark'" class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
        <!-- Moon icon (shown in light mode) -->
        <svg v-else class="w-4 h-4 text-ink-mute" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      </button>
    </div>
  </header>
</template>
