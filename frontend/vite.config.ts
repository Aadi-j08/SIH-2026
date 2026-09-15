import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// The API (FastAPI) owns the root paths; the web app lives under /app so the
// two never collide, in dev (proxy) and in production (served by FastAPI).
const API_PREFIXES = ["/auth", "/cooperative", "/disputes", "/stats", "/workers", "/bookings", "/admin", "/forecast", "/voice", "/allocation", "/rates", "/settlements", "/events", "/docs", "/openapi.json"];

export default defineConfig({
  base: "/app/",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "SahakarSetu",
        short_name: "SahakarSetu",
        description: "Fair work allocation for a workers' cooperative",
        start_url: "/app/",
        scope: "/app/",
        display: "standalone",
        background_color: "#FCFAF6",
        theme_color: "#C65D26",
        lang: "en-IN",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
          { src: "icon-maskable.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/app/index.html",
        globPatterns: ["**/*.{js,css,html,svg}"],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: Object.fromEntries(API_PREFIXES.map((p) => [p, { target: "http://127.0.0.1:8000", changeOrigin: true }])),
  },
  build: { outDir: "dist", emptyOutDir: true },
});
