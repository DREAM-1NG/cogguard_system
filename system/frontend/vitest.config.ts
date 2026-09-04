import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      'three/webgpu': resolve(__dirname, 'src/runtime/webglOnlyRenderer.ts'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
