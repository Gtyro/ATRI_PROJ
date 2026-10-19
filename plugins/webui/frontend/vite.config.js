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
      host: "127.0.0.1",
      port: 5188,
      strictPort: true,
      proxy: {
        "/auth": {
          target: "http://127.0.0.1:8080", // ATRI 内部 API 上游
          changeOrigin: true,
        },
        "/db": {
          target: "http://127.0.0.1:8080", // ATRI 内部 API 上游
          changeOrigin: true,
        },
        "/api": {
          target: "http://127.0.0.1:8080", // ATRI 内部 API 上游
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
