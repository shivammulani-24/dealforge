import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests against the REAL backend (plan section 8.2): FastAPI on a fresh SQLite
 * database, serving the production build (`npm run build` first) from the same origin with its
 * strict CSP, exactly as deployed (D4-07). Two viewports, per D4-09.
 *
 * PYTHON selects the interpreter that has the backend installed (default: `python`).
 */
const PORT = 8765;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  forbidOnly: process.env.CI !== undefined,
  retries: 0,
  reporter: process.env.CI === undefined ? "list" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${String(PORT)}`,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    // Screenshots a person reviews are taken at 2x.
    { name: "desktop-1440", use: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 } },
    { name: "laptop-1024", use: { viewport: { width: 1024, height: 768 }, deviceScaleFactor: 2 } },
  ],
  webServer: {
    command: `node e2e/start-backend.mjs ${String(PORT)}`,
    url: `http://127.0.0.1:${String(PORT)}/api/v1/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
