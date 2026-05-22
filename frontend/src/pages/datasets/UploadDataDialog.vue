<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDatasetStore } from '../../shared/stores/dataset'

const emit = defineEmits<{ close: [] }>()
const datasetStore = useDatasetStore()

const files = ref<File[]>([])
const sampleFps = ref(1)
const isDragging = ref(false)
const uploading = ref(false)
const uploadMessage = ref('')
const error = ref('')

const VALID_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.mp4', '.avi', '.mov'])

function isValidMediaFile(name: string): boolean {
  const dot = name.lastIndexOf('.')
  return dot >= 0 && VALID_EXTENSIONS.has(name.slice(dot).toLowerCase())
}

async function scanEntries(entries: FileSystemEntry[]): Promise<File[]> {
  const results: File[] = []

  async function processEntry(entry: FileSystemEntry): Promise<void> {
    if (entry.isFile) {
      const fileEntry = entry as FileSystemFileEntry
      const file: File = await new Promise((resolve, reject) => fileEntry.file(resolve, reject))
      if (isValidMediaFile(file.name)) results.push(file)
    } else if (entry.isDirectory) {
      const dirReader = (entry as FileSystemDirectoryEntry).createReader()
      const batch: FileSystemEntry[] = await new Promise((resolve, reject) => {
        dirReader.readEntries(resolve, reject)
      })
      for (const child of batch) {
        await processEntry(child)
      }
    }
  }

  await Promise.all(entries.map(processEntry))
  return results
}

function onFolderSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files) return
  const valid = Array.from(input.files).filter((f) => isValidMediaFile(f.name))
  files.value = [...files.value, ...valid]
  error.value = ''
  input.value = ''
}

const imageFiles = computed(() => files.value.filter((f) => f.type.startsWith('image/')))
const videoFiles = computed(() => files.value.filter((f) => f.type.startsWith('video/')))
const hasMixedMedia = computed(() => imageFiles.value.length > 0 && videoFiles.value.length > 0)
const canUpload = computed(() => files.value.length > 0 && !hasMixedMedia.value)

async function onDrop(e: DragEvent) {
  isDragging.value = false
  if (!e.dataTransfer) return
  error.value = ''
  const items = e.dataTransfer.items
  if (items && items.length > 0) {
    const entries: FileSystemEntry[] = []
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.()
      if (entry) entries.push(entry)
    }
    if (entries.length > 0) {
      uploading.value = true
      try {
        const scanned = await scanEntries(entries)
        files.value = [...files.value, ...scanned]
      } finally {
        uploading.value = false
      }
      return
    }
  }
  files.value = [...files.value, ...Array.from(e.dataTransfer.files)]
}

function removeFile(idx: number) {
  files.value.splice(idx, 1)
}

async function startUpload() {
  error.value = ''
  if (!canUpload.value) {
    error.value = 'Upload either images or videos, not mixed media.'
    return
  }
  uploading.value = true
  uploadMessage.value = ''
  try {
    if (videoFiles.value.length > 0) {
      let totalFrames = 0
      for (const video of videoFiles.value) {
        const result = await datasetStore.uploadStream({ file: video, sampleFps: sampleFps.value })
        totalFrames += result?.uploaded ?? 0
      }
      uploadMessage.value = `${totalFrames} frames uploaded from ${videoFiles.value.length} video(s)`
    } else {
      const result = await datasetStore.uploadRaw(imageFiles.value)
      uploadMessage.value = `${result?.uploaded ?? 0} images uploaded`
    }
    emit('close')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Upload failed'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition ease-out duration-200"
    enter-from-class="opacity-0 scale-[0.98]"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition ease-in duration-150"
    leave-to-class="opacity-0 scale-[0.98]"
  >
    <div class="dataset-dialog-backdrop" @click.self="emit('close')">
      <section class="dataset-upload-dialog">
        <header class="dataset-modal-header">
          <div>
            <h3 class="dataset-modal-title">Upload Data</h3>
            <p class="dataset-modal-copy">Add images or videos to this dataset.</p>
          </div>
          <button class="dataset-modal-close" @click="emit('close')" aria-label="Close upload dialog">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </header>

        <div class="dataset-modal-body dataset-upload-body">
          <div
            class="dataset-dropzone"
            :class="{ 'is-active': isDragging }"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="onDrop"
          >
            <input ref="fileInput" type="file" multiple accept="image/*,video/*" class="hidden" @change="(e) => { files.push(...Array.from((e.target as HTMLInputElement).files ?? [])); error = '' }" />
            <input ref="folderInput" type="file" webkitdirectory directory multiple class="hidden" @change="onFolderSelect" />
            <svg class="w-9 h-9 text-ink-faint" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
            <div>
              <p>Drop images, videos, or a folder here</p>
              <small>Images are stored raw. Video is sampled per FPS. Folders scanned recursively.</small>
            </div>
            <div class="dataset-upload-actions">
              <button class="dataset-secondary-button" @click.stop="($refs.fileInput as HTMLInputElement)?.click()">Select Files</button>
              <button class="dataset-secondary-button" @click.stop="($refs.folderInput as HTMLInputElement)?.click()">Select Folder</button>
            </div>
          </div>

          <div v-if="files.length" class="dataset-upload-files">
            <div class="dataset-upload-files-header">
              <span>{{ files.length }} selected</span>
              <small v-if="hasMixedMedia">Mixed image and video batches are not supported.</small>
              <small v-else>Ready to upload.</small>
            </div>
            <div class="dataset-file-list">
              <div v-for="(f, i) in files" :key="f.name + i" class="dataset-file-row">
                <span>{{ f.name }}</span>
                <button @click="removeFile(i)">Remove</button>
              </div>
            </div>
          </div>

          <div v-if="videoFiles.length" class="dataset-panel-block">
            <div class="dataset-field-row">
              <span class="dataset-field-label">Frame Sampling</span>
              <span class="dataset-field-value">{{ sampleFps }} fps</span>
            </div>
            <input v-model.number="sampleFps" type="range" min="0.5" max="10" step="0.5" class="dataset-range" />
          </div>

          <p v-if="uploadMessage" class="dataset-success-message">{{ uploadMessage }}</p>
          <p v-if="error" class="dataset-error-message">{{ error }}</p>
        </div>

        <footer class="dataset-modal-footer is-split">
          <button class="dataset-secondary-button" @click="emit('close')">Cancel</button>
          <button class="dataset-primary-button" :disabled="uploading || !canUpload" @click="startUpload">
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
        </footer>
      </section>
    </div>
  </Transition>
</template>
