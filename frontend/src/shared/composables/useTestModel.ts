import { ref, computed } from 'vue'
import { loadCustomModel } from '../api/client'
import type { ModelVersion } from '../api/training'
import { getModelVersion } from '../api/training'

const testModelId = ref<string | null>(null)
const testModelInfo = ref<ModelVersion | null>(null)
const loading = ref(false)
const loaded = ref(false)
const error = ref<string | null>(null)

export function useTestModel() {
  const modelName = computed(() => testModelInfo.value?.model_name ?? null)
  const classNames = computed(() => testModelInfo.value?.class_names ?? [])
  const modelArch = computed(() =>
    testModelInfo.value ? `${testModelInfo.value.family} / ${testModelInfo.value.size}` : '',
  )

  async function loadModelInfo(modelId: string) {
    loading.value = true
    error.value = null
    try {
      testModelInfo.value = await getModelVersion(modelId)
      testModelId.value = modelId
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load model info'
    } finally {
      loading.value = false
    }
  }

  async function loadTestModel(modelId: string) {
    loading.value = true
    error.value = null
    try {
      await loadModelInfo(modelId)
      const result = await loadCustomModel(modelId)
      loaded.value = result.loaded
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load test model'
      loaded.value = false
    } finally {
      loading.value = false
    }
  }

  function reset() {
    testModelId.value = null
    testModelInfo.value = null
    loading.value = false
    loaded.value = false
    error.value = null
  }

  return {
    testModelId,
    testModelInfo,
    loading,
    loaded,
    error,
    modelName,
    classNames,
    modelArch,
    loadModelInfo,
    loadTestModel,
    reset,
  }
}
