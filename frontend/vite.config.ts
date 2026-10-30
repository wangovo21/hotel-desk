import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * dev 下前端跑 5173，`/api` 全部代理到后端的 8000。
 *
 * 为什么用代理而不是让前端直连 8000 + CORS：
 *   · 前端代码里就只有一个相对路径 `/api`，dev / 生产 / 打包后托管到后端，
 *     三种环境一份代码，不用靠 VITE_API_BASE 切来切去；
 *   · 顺带绕开 CORS 预检 —— 前台大厅的网络环境里，少一个请求类型少一类故障。
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
