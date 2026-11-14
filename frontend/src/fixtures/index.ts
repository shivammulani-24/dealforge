/**
 * Responses RECORDED from the real backend by scripts/record-fixtures.mjs (synthetic sample
 * company only). Never hand-edited: src/fixtures/fixtures.test.ts validates every body against
 * the committed docs/openapi.json, so the casts below are checked at test time.
 */
import type { components } from "@/api/schema";

import dashboard from "./recorded/dashboard.json";
import errorCalculation from "./recorded/error-calculation.json";
import errorValidation from "./recorded/error-validation.json";
import financials from "./recorded/financials.json";
import health from "./recorded/health.json";
import historicalAnalysis from "./recorded/historical-analysis.json";
import preview from "./recorded/preview.json";
import run from "./recorded/run.json";
import runsPage from "./recorded/runs-page.json";
import sensitivityInvalid from "./recorded/sensitivity-invalid-cells.json";
import sensitivityNegative from "./recorded/sensitivity-negative-base.json";
import sensitivityWaccG from "./recorded/sensitivity-wacc-g.json";

type S = components["schemas"];

export interface RecordedMeta {
  operation: { method: string; path: string; status: number };
  engine_version: string;
  note: string;
  source: string;
}

export interface Recorded<T> {
  $recorded: RecordedMeta;
  body: T;
}

function rec<T>(json: unknown): Recorded<T> {
  return json as Recorded<T>;
}

/** The backend error envelope, which is not part of the OpenAPI document. */
export interface ErrorEnvelope {
  error_type: string;
  status: number;
  errors: Record<string, unknown>[];
  engine_version?: string;
}

export const recorded = {
  health: rec<S["HealthOut"]>(health),
  dashboard: rec<S["DashboardOut"]>(dashboard),
  financials: rec<S["FinancialsOut"]>(financials),
  historicalAnalysis: rec<S["HistoricalAnalysisOut"]>(historicalAnalysis),
  preview: rec<S["PreviewOut"]>(preview),
  run: rec<S["RunOut"]>(run),
  runsPage: rec<S["RunsPageOut"]>(runsPage),
  sensitivityWaccG: rec<S["SensitivityOut"]>(sensitivityWaccG),
  sensitivityInvalid: rec<S["SensitivityOut"]>(sensitivityInvalid),
  sensitivityNegative: rec<S["SensitivityOut"]>(sensitivityNegative),
  errorCalculation: rec<ErrorEnvelope>(errorCalculation),
  errorValidation: rec<ErrorEnvelope>(errorValidation),
} as const;

export type RecordedName = keyof typeof recorded;
