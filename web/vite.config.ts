import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Production build → packaged static files served by ``raft serve`` (one process).
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: path.resolve(rootDir, "../src/raft/share/serve/spa"),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8787",
    },
  },
});
