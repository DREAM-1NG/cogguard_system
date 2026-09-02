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
})
