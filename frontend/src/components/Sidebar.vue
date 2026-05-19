<script setup lang="ts">
import { ref } from 'vue'
import GroundingInput from './GroundingInput.vue'
import MediaInput from './MediaInput.vue'
import SettingsPanel from './SettingsPanel.vue'

const collapsed = ref(false)
</script>

<template>
  <aside
    class="shrink-0 border-r border-hairline bg-canvas h-full transition-[width] duration-200 overflow-hidden"
    :class="collapsed ? 'w-12' : 'w-[380px]'"
  >
    <div v-show="collapsed" class="h-full flex flex-col items-center py-3">
      <button
        type="button"
        class="w-9 h-9 flex items-center justify-center rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
        aria-label="Expand controls"
        title="Expand controls"
        @click="collapsed = false"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m9 18 6-6-6-6" />
        </svg>
      </button>
      <span class="mt-3 rotate-180 text-[11px] font-medium uppercase tracking-wider text-ink-mute" style="writing-mode: vertical-rl;">
        Controls
      </span>
    </div>

    <div v-show="!collapsed" class="h-full overflow-y-auto">
      <div class="p-(--spacing-lg) space-y-(--spacing-xl)">
        <div class="flex items-center justify-between gap-3">
          <p class="text-xs font-medium text-ink-mute uppercase tracking-wider">Controls</p>
          <button
            type="button"
            class="w-8 h-8 flex items-center justify-center rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
            aria-label="Collapse controls"
            title="Collapse controls"
            @click="collapsed = true"
          >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m15 18-6-6 6-6" />
            </svg>
          </button>
        </div>

        <GroundingInput />

        <hr class="border-hairline" />

        <MediaInput />

        <hr class="border-hairline" />

        <SettingsPanel />
      </div>
    </div>
  </aside>
</template>
