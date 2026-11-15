import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

const backendTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    strictPort: true,
    // Same-origin API traffic keeps refresh cookies predictable during development.
    proxy: {
      "/api": { target: backendTarget, changeOrigin: false },
      "/health": { target: backendTarget, changeOrigin: false },
    },
  },
});
