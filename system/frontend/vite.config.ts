/**
 * Vite 构建配置
 *
 * 功能说明：
 * - 使用 @vitejs/plugin-vue 编译 .vue 单文件组件
 * - 配置 @ 别名指向 src 目录，简化模块导入路径
 * - 开发服务器运行在 5173 端口
 * - /api 请求代理到后端 localhost:8000，解决开发环境跨域问题
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      'three/webgpu': resolve(__dirname, 'src/runtime/webglOnlyRenderer.ts'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    manifest: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const moduleId = id.replace(/\\/g, '/')
          if (
            moduleId.includes('/node_modules/ant-design-vue/')
            || moduleId.includes('/node_modules/@ant-design/icons-vue/')
          ) {
            return 'ant-ui'
          }
          if (moduleId.includes('/node_modules/three/examples/jsm/')) return 'three-addons'
          if (moduleId.includes('/node_modules/three/')) return 'three-renderer'
          if (
            moduleId.includes('/node_modules/3d-force-graph/')
            || moduleId.includes('/node_modules/three-forcegraph/')
            || moduleId.includes('/node_modules/three-render-objects/')
            || moduleId.includes('/node_modules/three-spritetext/')
          ) {
            return 'graph3d-view'
          }
          if (
            moduleId.includes('/node_modules/d3-')
            || moduleId.includes('/node_modules/force-graph/')
            || moduleId.includes('/node_modules/kapsule/')
          ) {
            return 'graph-layout'
          }
          if (
            moduleId.includes('/node_modules/vue/')
            || moduleId.includes('/node_modules/@vue/')
            || moduleId.includes('/node_modules/vue-router/')
            || moduleId.includes('/node_modules/pinia/')
          ) {
            return 'vue-runtime'
          }
        },
      },
    },
  },
})
