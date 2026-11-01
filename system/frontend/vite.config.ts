/**
 * Vite 构建配置
 *
 * 功能说明：
 * - 使用 @vitejs/plugin-vue 编译 .vue 单文件组件
 * - 配置 @ 别名指向 src 目录，简化模块导入路径
 * - 开发服务器运行在 5173 端口
 * - /api 请求代理到后端 IPv4 loopback:8000，解决开发环境跨域问题
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
        // Uvicorn binds IPv4 in the local stack. Avoid a localhost -> ::1
        // resolution race that Vite reports to the browser as HTTP 502.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    manifest: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // The workspace control module owns its transitive UI dependencies so
        // a dense analyst route does not resolve dozens of tiny imports. The
        // heavy visual groups remain isolated by their explicit roots below.
        onlyExplicitManualChunks: false,
        manualChunks(id) {
          const moduleId = id.replace(/\\/g, '/')
          if (moduleId.endsWith('/src/ui/semanticWorkspaceControls.ts')) return 'semantic-workspace-ui'
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
