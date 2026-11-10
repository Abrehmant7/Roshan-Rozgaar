import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Django runs on the host; the dev server proxies relative /api requests to it,
// so the browser only ever talks to one origin. Production builds are served by
// Django itself under /static/ (see backend/config/urls.py), again one origin.
const backend = process.env.VITE_BACKEND || 'http://127.0.0.1:8000'

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: backend, changeOrigin: true } },
  },
}))
