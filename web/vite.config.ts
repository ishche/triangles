import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.DOMEPRINT_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 700 }, // the lazy 3D view bundles three.js
  server: { port: 5173, proxy: { "/api": api } },
});
