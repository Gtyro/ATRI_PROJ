import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  // 生产构建挂载在 /webui 下，开发环境保持根路径
  base: command === "build" ? "/webui/" : "/",
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
      "@": resolve(__dirname, "src"),
    },
  },

  // 开发服务器配置
  server: {
    proxy: {
      "/auth": {
        target: "http://localhost:8080", // 后端API地址
        changeOrigin: true,
      },
      "/db": {
        target: "http://localhost:8080", // 后端API地址
        changeOrigin: true,
      },
      "/api": {
        target: "http://localhost:8080", // 后端API地址
        changeOrigin: true,
      },
    },
  },

  // 构建配置
  build: {
    outDir: "../static/webui", // 构建输出到static/webui目录
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/element-plus")) {
            return "vendor-element-plus";
          }
          if (id.includes("node_modules/echarts")) {
            return "vendor-echarts";
          }
          if (id.includes("node_modules/three")) {
            return "vendor-three";
          }
          if (
            id.includes("node_modules/vue") ||
            id.includes("node_modules/pinia") ||
            id.includes("node_modules/vue-router")
          ) {
            return "vendor-vue";
          }
          return undefined;
        },
      },
    },
  },
}));
