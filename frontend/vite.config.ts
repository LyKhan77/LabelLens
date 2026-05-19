import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 8282,
    proxy: {
      '/api': { target: 'http://localhost:3131', changeOrigin: true },
      '/ws': { target: 'ws://localhost:3131', ws: true },
    },
  },
})
