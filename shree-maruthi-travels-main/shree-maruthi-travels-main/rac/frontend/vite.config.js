import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/admin/dispatch/',
  server: {
    port: 5173,
    host: true
  }
})
