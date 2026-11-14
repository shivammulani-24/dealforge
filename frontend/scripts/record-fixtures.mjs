// Record API responses from a REAL backend into src/fixtures/recorded/ (plan section 8.2:
// "fixtures recorded from the real backend, never hand-typed numbers").
//
//   DEALFORGE_DATABASE_URL=sqlite:///./fixtures.sqlite3 \
//     uvicorn app.main:create_app --factory --port 8000      # from backend/, fresh database
//   node scripts/record-fixtures.mjs http://127.0.0.1:8000
//
// Every file records the operation it came from ({method, path template, status}), so
// src/fixtures/fixtures.test.ts can validate each body against docs/openapi.json. All data is
// the synthetic sample company (R4); recorded values are never edited by hand.
import { mkdir, readFile, writeFile } from "node:fs/promises";

const base = (process.argv[2] ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const outDir = new URL("../src/fixtures/recorded/", import.meta.url);
const scenarioFile = new URL("../../backend/samples/ardent_base_scenario.json", import.meta.url);

async function call(method, path, { token, body, headers = {}, expect } = {}) {
  const res = await fetch(`${base}/api/v1${path}`, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token === undefined ? {} : { Authorization: `Bearer ${token}` }),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  const json = text === "" ? null : JSON.parse(text);
  if (expect !== undefined && res.status !== expect) {
    throw new Error(`${method} ${path}: expected ${expect}, got ${res.status}: ${text}`);
  }
  return { status: res.status, body: json };
}

let health = null;
async function save(name, { method, template, note }, { status, body }) {
  const fixture = {
    $recorded: {
      operation: { method: method.toLowerCase(), path: `/api/v1${template}`, status },
      engine_version: health.engine_version,
      note,
      source: "scripts/record-fixtures.mjs against a live backend; synthetic sample data only",
    },
    body,
  };
  await writeFile(new URL(`${name}.json`, outDir), `${JSON.stringify(fixture, null, 2)}\n`);
  console.log(`  ${name}.json  ${method} ${template} -> ${status}`);
}

async function user(tag) {
  const creds = { email: `fixtures.${tag}@example.com`, password: "fixture-password-1" };
  await call("POST", "/auth/register", { body: creds });
  const tok = await call("POST", "/auth/token", { body: creds, expect: 200 });
  return tok.body.access_token;
}

async function main() {
  await mkdir(outDir, { recursive: true });
  health = (await call("GET", "/health", { expect: 200 })).body;
  console.log(`backend ${base}, engine ${health.engine_version}`);
  await save(
    "health",
    { method: "GET", template: "/health", note: "service status" },
    {
      status: 200,
      body: health,
    },
  );

  // --- Base case: the synthetic sample company (KA-DCF-03 inputs) ---------------------------
  const token = await user("base");
  const samples = await call("GET", "/samples", { token, expect: 200 });
  const sampleId = samples.body[0].id;
  const loaded = await call("POST", `/samples/${sampleId}/load`, { token, expect: 201 });
  const { company_id: cid, scenario_id: sid } = loaded.body;

  await save(
    "financials",
    { method: "GET", template: "/companies/{company_id}/financials", note: "sample statements" },
    await call("GET", `/companies/${cid}/financials`, { token, expect: 200 }),
  );
  await save(
    "historical-analysis",
    {
      method: "GET",
      template: "/companies/{company_id}/historical-analysis",
      note: "sample ratios, including liquidity",
    },
    await call("GET", `/companies/${cid}/historical-analysis`, { token, expect: 200 }),
  );
  await save(
    "preview",
    { method: "POST", template: "/scenarios/{scenario_id}/preview", note: "KA-DCF-03 preview" },
    await call("POST", `/scenarios/${sid}/preview`, { token, expect: 200 }),
  );
  const run = await call("POST", `/scenarios/${sid}/runs`, {
    token,
    body: { label: "Fixture run" },
    headers: { "Idempotency-Key": "fixture-run-base-0001" },
    expect: 201,
  });
  const rid = run.body.id;
  await save(
    "run",
    { method: "GET", template: "/runs/{run_id}", note: "frozen KA-DCF-03 run" },
    await call("GET", `/runs/${rid}`, { token, expect: 200 }),
  );
  const grid = (row, col) => ({ row, col, output: "value_per_share" });
  await save(
    "sensitivity-wacc-g",
    {
      method: "POST",
      template: "/runs/{run_id}/sensitivity",
      note: "WACC ±2 × 0.5pp, g ±2 × 0.5pp, value per share",
    },
    await call("POST", `/runs/${rid}/sensitivity`, {
      token,
      body: grid(
        { variable: "wacc", step: 0.005, steps_each_side: 2 },
        { variable: "terminal_growth", step: 0.005, steps_each_side: 2 },
      ),
      expect: 200,
    }),
  );
  await save(
    "sensitivity-invalid-cells",
    {
      method: "POST",
      template: "/runs/{run_id}/sensitivity",
      note: "wide g step so some cells have g >= WACC (invalid)",
    },
    await call("POST", `/runs/${rid}/sensitivity`, {
      token,
      body: grid(
        { variable: "wacc", step: 0.005, steps_each_side: 1 },
        { variable: "terminal_growth", step: 0.05, steps_each_side: 2 },
      ),
      expect: 200,
    }),
  );
  await save(
    "runs-page",
    { method: "GET", template: "/runs", note: "saved runs list" },
    await call("GET", "/runs?page=1&page_size=25", { token, expect: 200 }),
  );
  await save(
    "dashboard",
    { method: "GET", template: "/dashboard", note: "dashboard after loading the sample" },
    await call("GET", "/dashboard", { token, expect: 200 }),
  );

  // --- Error envelopes ---------------------------------------------------------------------
  const scen = JSON.parse(await readFile(scenarioFile, "utf8"));
  const badAssumptions = scen.assumptions.map((a) =>
    a.key === "terminal_growth" ? { ...a, value: 0.2 } : a,
  );
  await save(
    "error-calculation",
    {
      method: "POST",
      template: "/scenarios/{scenario_id}/preview",
      note: "draft with terminal growth 20% (>= WACC): engine refuses; nothing is written",
    },
    await call("POST", `/scenarios/${sid}/preview`, {
      token,
      body: { settings: scen.settings, assumptions: badAssumptions },
      expect: 422,
    }),
  );
  await save(
    "error-validation",
    { method: "POST", template: "/companies", note: "malformed company (lower-case currency)" },
    await call("POST", "/companies", {
      token,
      body: {
        name: "",
        sector: null,
        currency: "inr",
        scale: "crores",
        fiscal_year_end_month: 3,
        is_financial_institution: false,
        is_synthetic: true,
      },
      expect: 422,
    }),
  );

  // --- Negative base (A9): large debt-like claim, so equity and value per share are < 0 ------
  const tokenNeg = await user("negative-base");
  const loadedNeg = await call("POST", `/samples/${sampleId}/load`, {
    token: tokenNeg,
    expect: 201,
  });
  const fin = await call("GET", `/companies/${loadedNeg.body.company_id}/financials`, {
    token: tokenNeg,
    expect: 200,
  });
  const last = fin.body.periods[fin.body.periods.length - 1];
  const claim = last.line_items.find((li) => li.item_code === "other_debt_like_claims");
  await call("PATCH", `/line-items/${claim.id}`, {
    token: tokenNeg,
    body: {
      value: 5000.0,
      basis: "assumed",
      rationale:
        "Fixture: large debt-like claim so the base equity value is negative (A9 NM rule).",
    },
    expect: 200,
  });
  const runNeg = await call("POST", `/scenarios/${loadedNeg.body.scenario_id}/runs`, {
    token: tokenNeg,
    body: { label: "Negative base fixture" },
    headers: { "Idempotency-Key": "fixture-run-negative-0001" },
    expect: 201,
  });
  await save(
    "sensitivity-negative-base",
    {
      method: "POST",
      template: "/runs/{run_id}/sensitivity",
      note: "base value per share < 0: change_abs given, change_pct NM in every cell",
    },
    await call("POST", `/runs/${runNeg.body.id}/sensitivity`, {
      token: tokenNeg,
      body: grid(
        { variable: "wacc", step: 0.005, steps_each_side: 1 },
        { variable: "terminal_growth", step: 0.005, steps_each_side: 1 },
      ),
      expect: 200,
    }),
  );
  console.log("done");
}

await main();
