/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Development: the Vite dev server proxies /api to FastAPI on :8000, so the browser only ever
// talks to one origin (no CORS, the token is never sent cross-site).
// Production: FastAPI serves dist/ from the same origin (D4-07, B11) with a strict CSP
// (default-src 'self'; script-src 'self'; style-src 'self'), so the build must not inline
// scripts, styles or data: fonts.
const backend = process.env.DEALFORGE_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: backend, changeOrigin: false } },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // CSP: fonts fall under default-src 'self', so no asset may be inlined as a data: URI.
    assetsInlineLimit: 0,
    // CSP: no inline module-preload polyfill; every supported browser has native support.
    modulePreload: { polyfill: false },
    cssCodeSplit: true,
    // Recharts 3 (with its Redux store) is ~520 kB minified, ~157 kB gzipped; it is lazy-loaded.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Charts are shared by several later screens: keep Recharts and its own dependencies in
        // one cacheable chunk, loaded only by screens that draw charts. React stays in the
        // entry chunk, so the app shell never downloads chart code.
        manualChunks(id) {
          const chartDeps =
            /node_modules\/(recharts|victory-vendor|d3-[^/]+|@reduxjs|react-redux|redux|immer|reselect|es-toolkit|decimal\.js-light|eventemitter3|tiny-invariant|internmap)\//;
          return chartDeps.test(id) ? "charts" : undefined;
        },
        chunkFileNames: "assets/[name]-[hash].js",
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/api/schema.d.ts",
        "src/fixtures/**",
        "src/main.tsx",
        "src/vite-env.d.ts",
      ],
      thresholds: {
        // The display and session rules carry the financial-integrity guarantees, so they are
        // held to a higher bar than the rest of the UI.
        "src/lib/**": { statements: 100, branches: 95, functions: 100, lines: 100 },
        "src/auth/**": { statements: 90, branches: 85, functions: 90, lines: 90 },
        "src/api/**": { statements: 90, branches: 85, functions: 90, lines: 90 },
        statements: 85,
        branches: 80,
        functions: 85,
        lines: 85,
      },
    },
  },
});
