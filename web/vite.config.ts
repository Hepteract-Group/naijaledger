/// <reference types="vitest/config" />
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(rootDir, "..");

export default defineConfig(({ mode }) => {
  // loadEnv reads web/.env so local API_PORT overrides work without shell export.
  const env = loadEnv(mode, rootDir, "");
  const engineUrl = env.VITE_ENGINE_URL || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      fs: {
        allow: [repoRoot],
      },
      proxy: {
        "/api": {
          target: engineUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
