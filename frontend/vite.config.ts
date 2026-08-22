import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// 端口从项目根 .env 读取（与 scripts/manage.py、app/config.py 共用同一份），
// loadEnv 第三参数传 "" 表示加载所有前缀变量（默认只读 VITE_ 前缀会漏掉 BACKEND_PORT）。
// envDir 指向项目根但不改 server 配置，不影响前端 import.meta.env 行为。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const backendPort = env.BACKEND_PORT || "3333";
  const frontendPort = parseInt(env.FRONTEND_PORT || "2222", 10);

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: frontendPort,
      proxy: {
        "/api": {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./tests/setup.ts"],
    },
  };
});
