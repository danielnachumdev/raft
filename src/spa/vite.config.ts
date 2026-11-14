import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Production build → packaged static files served by ``raft serve`` (one process).
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      includeAssets: [
        "favicon.svg",
        "apple-touch-icon.png",
        "pwa-512-maskable.png",
      ],
      manifest: {
        id: "/",
        name: "Raft ops",
        short_name: "raft",
        description: "Operator dashboard for the raft control plane.",
        theme_color: "#0f6b5c",
        background_color: "#f3efe6",
        display: "standalone",
        orientation: "any",
        start_url: "/",
        scope: "/",
        lang: "en",
        categories: ["utilities", "developer"],
        icons: [
          {
            src: "pwa-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        globPatterns: ["**/*.{js,css,html,ico,svg,png,webmanifest}"],
        runtimeCaching: [
          {
            // Status/API polls and mutative actions must always hit the network.
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkOnly",
          },
          {
            // oauth2-proxy paths must never be cached by the service worker.
            urlPattern: ({ url }) => url.pathname.startsWith("/oauth2/"),
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  base: "/",
  build: {
    outDir: path.resolve(
      rootDir,
      "../raft/core/platform/share/serve/spa",
    ),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8787",
    },
  },
});
