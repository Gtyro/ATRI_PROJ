import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";

function normalizeBase(value) {
  if (!value || value === "/") {
    return "/";
  }

  return value.endsWith("/") ? value : `${value}/`;
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const publicBase = normalizeBase(env.VITE_PUBLIC_BASE || "/");
  const buildOutDir =
    env.VITE_BUILD_OUT_DIR ||
    (mode === "production" ? "../static/webui" : ".preview-dist");

  return {
    base: publicBase,
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
      outDir: buildOutDir,
      emptyOutDir: true,
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/echarts")) {
              return "vendor-echarts";
            }
            if (id.includes("node_modules/three")) {
              return "vendor-three";
            }
            return undefined;
          },
        },
      },
    },
  };
});
