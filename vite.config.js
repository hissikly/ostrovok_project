import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// Оболочка фронта — app/frontend, компоненты фич — features/<фича>/frontend (алиас @features).
export default defineConfig({
  root: 'app/frontend',
  plugins: [react()],
  resolve: {
    alias: {
      '@features': fileURLToPath(new URL('./features', import.meta.url)),
      '@app': fileURLToPath(new URL('./app/frontend', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8080', '/health': 'http://localhost:8080' },
    fs: { allow: ['.'] },
  },
  build: { outDir: '../static', emptyOutDir: true },
})
