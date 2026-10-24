import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,
    target: 'es2020',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return
          if (id.includes('maplibre-gl')) return 'maplibre'
          if (id.includes('@tanstack/react-query')) return 'query'
          if (id.includes('framer-motion')) return 'motion'
          if (id.includes('i18next') || id.includes('react-i18next')) return 'i18n'
          if (id.includes('zustand')) return 'zustand'
          if (id.includes('three')) return 'three-lazy'
          if (id.includes('react') || id.includes('scheduler')) return 'reactvendor'
        },
      },
    },
  },
})
