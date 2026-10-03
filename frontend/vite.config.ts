import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// The API (FastAPI) owns the root paths; the web app lives under /app so the
// two never collide, in dev (proxy) and in production (served by FastAPI).
const API_PREFIXES = [
  "/auth",
  "/assistant",
  "/cooperative",
  "/disputes",
  "/feedback",
  "/stats",
  "/workers",
  "/bookings",
  "/admin",
  "/forecast",
  "/voice",
  "/allocation",
  "/rates",
  "/settlements",
  "/events",
  "/docs",
  "/openapi.json",
];

export default defineConfig(({ command }) => {
  // Fail the production build when the API origin is missing entirely. This is
  // the only place that can catch a typo in the Cloudflare Pages env var: a bad
  // value is still a syntactically valid URL, so nothing downstream would reject
  // it, and src/api.ts deliberately has no hardcoded fallback to mask it.
  //
  // An explicitly empty value is legitimate and means "same origin" -- that is
  // what the copy FastAPI serves from /app/ needs, since the API and the SPA
  // share a host there. Only a *missing* variable is an error.
  if (command === "build" && process.env.VITE_API_BASE_URL === undefined) {
    throw new Error(
      "VITE_API_BASE_URL must be set for production builds. Set it in the Cloudflare " +
        "Pages dashboard under Settings -> Environment variables for both Production " +
        "and Preview. See docs/DEPLOY.md section 2.",
    );
  }

  return {
    base: process.env.VITE_BASE_PATH || "/",
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        includeAssets: ["icon.svg"],
        manifest: {
          name: "SahakarSetu",
          short_name: "SahakarSetu",
          description: "Fair work allocation for a workers' cooperative",
          start_url: process.env.VITE_BASE_PATH || "/",
          scope: process.env.VITE_BASE_PATH || "/",
          display: "standalone",
          background_color: "#FCFAF6",
          theme_color: "#C65D26",
          lang: "en-IN",
          icons: [
            { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
            {
              src: "icon-maskable.svg",
              sizes: "any",
              type: "image/svg+xml",
              purpose: "maskable",
            },
          ],
        },
        workbox: {
          navigateFallback: (process.env.VITE_BASE_PATH || "/") + "index.html",
          globPatterns: ["**/*.{js,css,html,svg}"],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: Object.fromEntries(API_PREFIXES.map((p) => [p, { target: "http://127.0.0.1:8000", changeOrigin: true }])),
    },
    build: { outDir: "dist", emptyOutDir: true },
  };
});
