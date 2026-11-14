import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

declare const process: { env: Record<string, string | undefined> };
// KORI_API points the dev proxy at another backend, e.g. the deployed one for a live-voice check
const api = process.env.KORI_API || "http://127.0.0.1:8811";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 8812,
    host: "127.0.0.1",
    strictPort: true,
    proxy: {
      "/api": { target: api, changeOrigin: true },
      "/v1": { target: api, changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
