import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DatasetProject,
  DatasetImage,
  ImageAnnotation,
  DetectionAnnotation,
  DetectionPayload,
  PosePayload,
} from '../api/dataset'
import type { DatasetTaskConfig, DatasetTaskType } from '../types'
import * as api from '../api/dataset'

const CLASS_COLOR_FALLBACKS = [
  '#3ECF8E', '#2563EB', '#F59E0B', '#EF4444',
  '#8B5CF6', '#14B8A6', '#EC4899', '#84CC16',
  '#06B6D4', '#F97316', '#6366F1', '#22C55E',
  '#EAB308', '#A855F7', '#0EA5E9', '#F43F5E',
]

function fallbackClassColor(label: string): string {
  let hash = 0
  for (let i = 0; i < label.length; i++) hash = ((hash << 5) - hash + label.charCodeAt(i)) | 0
  return CLASS_COLOR_FALLBACKS[Math.abs(hash) % CLASS_COLOR_FALLBACKS.length]
}

export const useDatasetStore = defineStore('dataset', () => {
  // Projects
  const projects = ref<DatasetProject[]>([])
  const projectsLoading = ref(false)

  // Current project
  const currentProject = ref<string | null>(null)

  // Images
  const images = ref<DatasetImage[]>([])
  const imagesTotal = ref(0)
  const imagesPage = ref(1)
  const imagesLimit = ref(25)

  // Review
  const selectedImage = ref<string | null>(null)
  const currentAnnotations = ref<ImageAnnotation | null>(null)
  const reviewingImageId = ref<string | null>(null)

  // Auto-labelling
  const autoLabelActive = ref(false)
  const autoLabelDataset = ref<string | null>(null)
  const autoLabelFps = ref(1)
  const autoLabelRtspTimerSeconds = ref<number | null>(null)

  // Overlay state
  const overlayState = ref({
    showBbox: true,
    showLabels: true,
    showMasks: false,
    hiddenClasses: new Set<string>(),
    hiddenDetections: new Set<number>(),
  })

  // Computed
  const currentProjectData = computed(() =>
    projects.value.find((p) => p.name === currentProject.value),
  )

  // Actions
  async function fetchProjects() {
    projectsLoading.value = true
    try {
      projects.value = await api.listDatasets()
    } finally {
      projectsLoading.value = false
    }
  }

  function classColor(label: string): string {
    return currentProjectData.value?.class_colors?.[label] ?? fallbackClassColor(label)
  }

  async function setClassColor(label: string, color: string) {
    if (!currentProject.value) return
    const updated = await api.updateClassColor(currentProject.value, label, color)
    const idx = projects.value.findIndex((project) => project.name === updated.name)
    if (idx >= 0) projects.value.splice(idx, 1, updated)
    else projects.value.push(updated)
  }

  async function renameClass(oldLabel: string, newLabel: string) {
    if (!currentProject.value) return
    await api.renameClass(currentProject.value, oldLabel, newLabel)
    await fetchProjects()
    if (selectedImage.value) await selectImage(selectedImage.value)
    await fetchImages(imagesPage.value)
  }

  async function deleteClass(label: string) {
    if (!currentProject.value) return
    await api.deleteClass(currentProject.value, label)
    await fetchProjects()
    if (selectedImage.value) await selectImage(selectedImage.value)
    await fetchImages(imagesPage.value)
  }

  async function createProject(
    name: string,
    taskType: DatasetTaskType = 'detect',
    taskConfig: DatasetTaskConfig = {},
  ) {
    await api.createDataset(name, taskType, taskConfig)
    await fetchProjects()
  }

  async function deleteProject(name: string) {
    await api.deleteDataset(name)
    if (currentProject.value === name) {
      currentProject.value = null
      images.value = []
    }
    await fetchProjects()
  }

  async function fetchImages(page = 1) {
    if (!currentProject.value) return
    imagesPage.value = page
    const result = await api.listImages(currentProject.value, page, imagesLimit.value)
    images.value = result.images
    imagesTotal.value = result.total
  }

  async function selectImage(imgId: string) {
    if (!currentProject.value) return
    selectedImage.value = imgId
    currentAnnotations.value = await api.getImage(currentProject.value, imgId)
  }

  function clearSelection() {
    selectedImage.value = null
    currentAnnotations.value = null
  }

  function startReview(imgId: string) {
    reviewingImageId.value = imgId
  }

  function exitReview() {
    reviewingImageId.value = null
  }

  async function reviewDetection(
    imgId: string,
    reviews: { id: number; accepted: boolean }[],
  ) {
    if (!currentProject.value) return
    await api.reviewImage(currentProject.value, imgId, reviews)
    if (selectedImage.value === imgId) {
      await selectImage(imgId)
    }
    await fetchImages(imagesPage.value)
  }


  async function addDetection(
    imgId: string,
    payload: Required<Pick<DetectionPayload, 'label' | 'box'>> & Omit<DetectionPayload, 'label' | 'box'>,
  ) {
    if (!currentProject.value) return
    const result = await api.addDetection(currentProject.value, imgId, payload)
    if (selectedImage.value === imgId) {
      await selectImage(imgId)
    }
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function updateDetection(imgId: string, detId: number, payload: DetectionPayload) {
    if (!currentProject.value) return
    const result = await api.updateDetection(currentProject.value, imgId, detId, payload)
    if (selectedImage.value === imgId) {
      await selectImage(imgId)
    }
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function deleteDetection(imgId: string, detId: number) {
    if (!currentProject.value) return
    const result = await api.deleteDetection(currentProject.value, imgId, detId)
    if (selectedImage.value === imgId) {
      await selectImage(imgId)
    }
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function setImageLabels(
    imgId: string,
    labels: { label: string; confidence?: number; accepted?: boolean; source?: string }[],
  ) {
    if (!currentProject.value) return
    const result = await api.setImageLabels(currentProject.value, imgId, labels)
    if (selectedImage.value === imgId) {
      await selectImage(imgId)
    }
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function addPose(imgId: string, payload: PosePayload) {
    if (!currentProject.value) return
    const result = await api.addPose(currentProject.value, imgId, payload)
    if (selectedImage.value === imgId) {
      await selectImage(imgId)
    }
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function inferNextVisualPrompt(
    sourceImgId: string,
    targetImgId: string,
    prompts: { box: [number, number, number, number]; label: string }[],
    confidence = 0.5,
  ) {
    if (!currentProject.value) return
    return api.inferNextVisualPrompt(currentProject.value, sourceImgId, {
      target_img_id: targetImgId,
      prompts,
      confidence,
    })
  }

  async function generateSamMask(
    imgId: string,
    box: [number, number, number, number],
  ) {
    if (!currentProject.value) return null
    try {
      return await api.generateSamMask(currentProject.value, imgId, box)
    } catch {
      return null
    }
  }

  async function saveToDataset(name: string, file: File, detections: unknown[], source = 'inference') {
    return api.saveToDataset(name, file, detections, source)
  }

  async function removeImages(imgIds: string[]) {
    if (!currentProject.value || imgIds.length === 0) return
    const uniqueIds = Array.from(new Set(imgIds))
    for (const imgId of uniqueIds) {
      await api.deleteImage(currentProject.value, imgId)
    }
    if (selectedImage.value && uniqueIds.includes(selectedImage.value)) {
      clearSelection()
    }
    const remainingTotal = Math.max(0, imagesTotal.value - uniqueIds.length)
    const maxPage = Math.max(1, Math.ceil(remainingTotal / imagesLimit.value))
    await fetchImages(Math.min(imagesPage.value, maxPage))
    await fetchProjects()
  }

  async function removeImage(imgId: string) {
    await removeImages([imgId])
  }

  async function uploadRaw(files: File[]) {
    if (!currentProject.value) return
    const result = await api.uploadRaw(currentProject.value, files)
    await fetchImages(imagesPage.value)
    return result
  }

  async function uploadStream(
    params: { file?: File; rtspUrl?: string; sampleFps?: number },
  ) {
    if (!currentProject.value) return
    const result = await api.uploadStream(currentProject.value, params)
    await fetchImages(imagesPage.value)
    return result
  }

  async function labelImages(
    promptType: string,
    labels: string[] = [],
    confidence = 0.5,
    visual?: { referImage?: File; bboxes?: [number, number, number, number][]; vcls?: string[] },
  ) {
    if (!currentProject.value) return
    const result = await api.labelImages(
      currentProject.value,
      promptType,
      labels,
      confidence,
      visual,
    )
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function createLabelJob(params: {
    promptType: string
    labels?: string[]
    confidence?: number
    referImage?: File
    bboxes?: [number, number, number, number][]
    vcls?: string[]
  }) {
    if (!currentProject.value) return
    return api.createLabelJob(currentProject.value, params)
  }

  async function getLabelJob(jobId: string) {
    if (!currentProject.value) return
    const result = await api.getLabelJob(currentProject.value, jobId)
    if (result.state === 'done') {
      await fetchImages(imagesPage.value)
      await fetchProjects()
    }
    return result
  }

  async function batchUpload(
    files: File[],
    promptType: string,
    labels: string[] = [],
    confidence = 0.5,
  ) {
    if (!currentProject.value) return
    const result = await api.batchUpload(
      currentProject.value,
      files,
      promptType,
      labels,
      confidence,
    )
    await fetchImages(imagesPage.value)
    await fetchProjects()
    return result
  }

  async function saveStream(
    name: string,
    params: {
      file?: File
      rtspUrl?: string
      promptType: string
      labels?: string[]
      confidence?: number
      sampleFps?: number
      referImage?: File
      bboxes?: [number, number, number, number][]
      vcls?: string[]
    },
  ) {
    return api.saveStream(name, params)
  }

  async function exportDataset(format: 'yolo' | 'coco', split = 0.8) {
    if (!currentProject.value) return
    const blob = await api.exportDataset(currentProject.value, format, split)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentProject.value}_${format}.zip`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Auto-labelling
  function toggleAutoLabel(dataset: string, fps: number, rtspTimerSeconds: number | null = null) {
    autoLabelActive.value = true
    autoLabelDataset.value = dataset
    autoLabelFps.value = fps
    autoLabelRtspTimerSeconds.value = rtspTimerSeconds
  }

  function disableAutoLabel() {
    autoLabelActive.value = false
    autoLabelDataset.value = null
    autoLabelRtspTimerSeconds.value = null
  }

  // Overlay controls
  function toggleOverlay(type: 'showBbox' | 'showLabels' | 'showMasks') {
    overlayState.value[type] = !overlayState.value[type]
  }

  function toggleClassVisibility(cls: string) {
    const hidden = overlayState.value.hiddenClasses
    if (hidden.has(cls)) {
      hidden.delete(cls)
    } else {
      hidden.add(cls)
    }
  }

  function toggleDetectionVisibility(id: number) {
    const hidden = overlayState.value.hiddenDetections
    if (hidden.has(id)) {
      hidden.delete(id)
    } else {
      hidden.add(id)
    }
  }

  function isDetectionVisible(det: DetectionAnnotation): boolean {
    if (overlayState.value.hiddenClasses.has(det.label)) return false
    if (overlayState.value.hiddenDetections.has(det.id)) return false
    return true
  }

  return {
    // State
    projects,
    projectsLoading,
    currentProject,
    images,
    imagesTotal,
    imagesPage,
    imagesLimit,
    selectedImage,
    currentAnnotations,
    reviewingImageId,
    autoLabelActive,
    autoLabelDataset,
    autoLabelFps,
    autoLabelRtspTimerSeconds,
    overlayState,
    // Computed
    currentProjectData,
    // Actions
    fetchProjects,
    classColor,
    setClassColor,
    renameClass,
    deleteClass,
    createProject,
    deleteProject,
    fetchImages,
    selectImage,
    clearSelection,
    startReview,
    exitReview,
    reviewDetection,
    addDetection,
    updateDetection,
    deleteDetection,
    setImageLabels,
    addPose,
    inferNextVisualPrompt,
    generateSamMask,
    saveToDataset,
    removeImage,
    removeImages,
    uploadRaw,
    uploadStream,
    labelImages,
    createLabelJob,
    getLabelJob,
    batchUpload,
    saveStream,
    exportDataset,
    toggleAutoLabel,
    disableAutoLabel,
    toggleOverlay,
    toggleClassVisibility,
    toggleDetectionVisibility,
    isDetectionVisible,
  }
})
