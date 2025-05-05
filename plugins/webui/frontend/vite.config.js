import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],

  // 路径别名
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },

  // 开发服务器配置
  server: {
    proxy: {
      '/auth': {
        target: 'http://localhost:8080', // 后端API地址
        changeOrigin: true
      },
      '/db': {
        target: 'http://localhost:8080', // 后端API地址
        changeOrigin: true
      }
    }
  },

  // 构建配置
  build: {
    outDir: '../static/webui', // 构建输出到static/webui目录
    emptyOutDir: true
  }
})