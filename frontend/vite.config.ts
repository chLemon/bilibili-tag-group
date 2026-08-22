import fs from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 端口从项目根 config.json 读取（与 scripts/manage.py、app/config.py 共用同一份）。
// defineConfig 在 Node 环境运行，可直接同步读 JSON。
const configPath = path.resolve(__dirname, "..", "config.json");
const config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
const backendPort = config.backend_port ?? 3333;
const frontendPort = config.frontend_port ?? 2222;

export default defineConfig({
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
});
