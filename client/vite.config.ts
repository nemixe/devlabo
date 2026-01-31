import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: '/app/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/connect': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/agent': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
