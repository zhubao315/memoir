import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages serves the site at /<repo>/; allow overriding at build time.
const base = process.env.VITE_BASE_PATH || '/'

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist' },
  test: { environment: 'node' },
})
