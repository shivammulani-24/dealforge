// Start the real FastAPI backend for the E2E suite: a FRESH SQLite database every run, serving
// the production build from frontend/dist (same origin, strict CSP). Used by playwright.config.ts.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(here, "..");
const backend = resolve(frontend, "../backend");
const dist = resolve(frontend, "dist");
const tmp = resolve(here, ".tmp");
const port = process.argv[2] ?? "8765";

if (!existsSync(resolve(dist, "index.html"))) {
  console.error("frontend/dist is missing: run `npm run build` before the E2E suite.");
  process.exit(1);
}

rmSync(tmp, { recursive: true, force: true });
mkdirSync(tmp, { recursive: true });

const child = spawn(
  process.env.PYTHON ?? "python",
  ["-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", port],
  {
    cwd: backend,
    stdio: "inherit",
    env: {
      ...process.env,
      DEALFORGE_DATABASE_URL: `sqlite:///${resolve(tmp, "e2e.sqlite3")}`,
      DEALFORGE_FRONTEND_DIST: dist,
    },
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    child.kill(signal);
  });
}
child.on("exit", (code) => process.exit(code === null ? 1 : code));
