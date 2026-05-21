import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DatasetProject,
  DatasetImage,
  ImageAnnotation,
  DetectionAnnotation,
} from '../api/dataset'
import * as api from '../api/dataset'

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

  async function createProject(name: string, classes: string[] = []) {
    await api.createDataset(name, classes)
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

  async function saveToDataset(name: string, file: File, detections: unknown[], source = 'inference') {
    return api.saveToDataset(name, file, detections, source)
  }

  async function removeImage(imgId: string) {
    if (!currentProject.value) return
    await api.deleteImage(currentProject.value, imgId)
    if (selectedImage.value === imgId) {
      clearSelection()
    }
    await fetchImages(imagesPage.value)
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
    autoLabelActive,
    autoLabelDataset,
    autoLabelFps,
    autoLabelRtspTimerSeconds,
    overlayState,
    // Computed
    currentProjectData,
    // Actions
    fetchProjects,
    createProject,
    deleteProject,
    fetchImages,
    selectImage,
    clearSelection,
    reviewDetection,
    saveToDataset,
    removeImage,
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
