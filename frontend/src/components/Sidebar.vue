<script setup lang="ts">
import GroundingInput from './GroundingInput.vue'
import MediaInput from './MediaInput.vue'
import SettingsPanel from './SettingsPanel.vue'
</script>

<template>
  <aside class="w-[380px] shrink-0 border-r border-hairline bg-canvas overflow-y-auto h-full">
    <div class="p-(--spacing-lg) space-y-(--spacing-xl)">
      <GroundingInput />

      <hr class="border-hairline" />

      <MediaInput />

      <hr class="border-hairline" />

      <SettingsPanel />
    </div>
  </aside>
</template>
