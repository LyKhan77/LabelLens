<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getGpus, updateGpuConfig } from '../api/system'
import { useBackendStatus } from '../composables/useBackendStatus'
import type { GpuInfo } from '../types'

const emit = defineEmits<{ close: [] }>()
const { yoloeStatus } = useBackendStatus()

const gpus = ref<GpuInfo[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const yoloeDevice = ref<number>(0)
const samDevice = ref<number>(0)
const applying = ref(false)
const applyError = ref<string | null>(null)
const applySuccess = ref(false)

const hasGpus = computed(() => gpus.value.length > 0)
const modelLoaded = computed(() => yoloeStatus.value === 'loaded')

const gpuOptions = computed(() =>
  gpus.value.map(g => ({
    value: g.index,
    label: `GPU ${g.index} — ${g.name}`,
  }))
)

function formatVram(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(0)} GB`
  return `${mb} MB`
}

onMounted(async () => {
  try {
    const res = await getGpus()
    gpus.value = res.gpus
    if (res.inference_config) {
      yoloeDevice.value = res.inference_config.yoloe_device
      samDevice.value = res.inference_config.sam_device
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to detect GPUs'
  } finally {
    loading.value = false
  }
})

async function apply() {
  applyError.value = null
  applySuccess.value = false
  applying.value = true
  try {
    await updateGpuConfig(yoloeDevice.value, samDevice.value)
    applySuccess.value = true
  } catch (e: any) {
    applyError.value = e?.response?.data?.detail || e?.message || 'Failed to update GPU config'
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <div
    class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="bg-canvas rounded-(--radius-lg) border border-hairline w-full max-w-lg max-h-[85vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between px-(--spacing-xxl) py-4 border-b border-hairline">
        <h3 class="text-[16px] font-medium text-ink">GPU Settings</h3>
        <button
          class="p-1 rounded-(--radius-sm) text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto px-(--spacing-xxl) py-4 space-y-4">
        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center py-8">
          <svg class="w-5 h-5 text-ink-mute animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span class="ml-2 text-[13px] text-ink-mute">Detecting GPUs...</span>
        </div>

        <!-- Detection error -->
        <div v-else-if="error" class="p-3 rounded-(--radius-md) bg-red-50 border border-red-200 text-[13px] text-red-700">
          {{ error }}
        </div>

        <!-- No GPUs -->
        <div v-else-if="!hasGpus" class="py-8 text-center">
          <svg class="w-8 h-8 text-ink-faint mx-auto mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <line x1="9" y1="9" x2="15" y2="15" />
            <line x1="15" y1="9" x2="9" y2="15" />
          </svg>
          <p class="text-[13px] text-ink-mute">No CUDA GPUs detected</p>
        </div>

        <!-- GPU list and config -->
        <template v-else>
          <!-- Model loaded warning -->
          <div v-if="modelLoaded" class="p-3 rounded-(--radius-md) bg-amber-50 border border-amber-200 text-[13px] text-amber-800 flex items-start gap-2">
            <svg class="w-4 h-4 mt-0.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>Model is currently loaded. Changing devices may require a model reload.</span>
          </div>

          <!-- Detected GPUs -->
          <div>
            <h4 class="text-[12px] text-ink-mute uppercase tracking-wide mb-2">Detected GPUs</h4>
            <div class="space-y-2">
              <div
                v-for="gpu in gpus"
                :key="gpu.index"
                class="p-3 rounded-(--radius-md) border border-hairline bg-canvas-soft"
              >
                <div class="flex items-center justify-between">
                  <span class="text-[13px] text-ink font-medium">{{ gpu.name }}</span>
                  <span class="text-[11px] text-ink-mute font-mono">Index {{ gpu.index }}</span>
                </div>
                <div class="mt-1 text-[12px] text-ink-mute">
                  VRAM: {{ formatVram(gpu.vram_total_mb) }}
                </div>
              </div>
            </div>
          </div>

          <!-- Device dropdowns -->
          <div class="space-y-3">
            <label class="block">
              <span class="text-[12px] text-ink-mute uppercase tracking-wide">YOLOE Device</span>
              <select
                v-model.number="yoloeDevice"
                class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary cursor-pointer"
              >
                <option v-for="opt in gpuOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>

            <label class="block">
              <span class="text-[12px] text-ink-mute uppercase tracking-wide">SAM Device</span>
              <select
                v-model.number="samDevice"
                class="block w-full mt-1 px-3 py-2 text-[13px] bg-canvas border border-hairline rounded-(--radius-md) text-ink focus:outline-none focus:border-primary cursor-pointer"
              >
                <option v-for="opt in gpuOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>
          </div>

          <!-- Apply feedback -->
          <div v-if="applyError" class="p-3 rounded-(--radius-md) bg-red-50 border border-red-200 text-[13px] text-red-700">
            {{ applyError }}
          </div>
          <div v-if="applySuccess" class="p-3 rounded-(--radius-md) bg-green-50 border border-green-200 text-[13px] text-green-700">
            GPU configuration updated successfully.
          </div>
        </template>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-2 px-(--spacing-xxl) py-3 border-t border-hairline">
        <button
          class="px-3 py-1.5 text-[13px] rounded-(--radius-sm) border border-hairline text-ink-mute hover:text-ink hover:bg-canvas-soft transition-colors cursor-pointer"
          @click="emit('close')"
        >
          Close
        </button>
        <button
          v-if="hasGpus"
          class="px-4 py-1.5 text-[13px] rounded-(--radius-sm) bg-primary text-white font-medium hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="applying"
          @click="apply"
        >
          {{ applying ? 'Applying...' : 'Apply' }}
        </button>
      </div>
    </div>
  </div>
</template>
