/**
 * The backend's single error envelope (docs/api-contract.md section 4):
 *   { error_type, status, errors: [{ code, message, loc? | field?, severity?, detail? }] }
 *
 * The envelope isn't in the OpenAPI document (FastAPI only documents its default 422 shape), so
 * it is typed here from the contract and parsed defensively. An ApiError never carries request
 * headers, so the bearer token can't leak through an error object, a log line or an error
 * report (D4-01; tested).
 */

export type ErrorType =
  | "validation"
  | "calculation"
  | "not_found"
  | "conflict"
  | "import"
  | "authentication"
  | "immutable"
  | "unavailable"
  | "method_not_allowed"
  | "internal"
  | "network"
  | "unknown";

const KNOWN: readonly ErrorType[] = [
  "validation",
  "calculation",
  "not_found",
  "conflict",
  "import",
  "authentication",
  "immutable",
  "unavailable",
  "method_not_allowed",
  "internal",
];

export interface ApiErrorItem {
  code: string | null;
  message: string;
  /** Pydantic location for validation errors, e.g. ["body", "email"]. */
  loc: (string | number)[] | null;
  /** Engine input field for calculation errors, e.g. "terminal_growth". */
  field: string | null;
  severity: string | null;
  detail: unknown;
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return typeof v === "object" && v !== null && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

function item(raw: unknown): ApiErrorItem {
  const r = asRecord(raw) ?? {};
  const loc = Array.isArray(r.loc)
    ? r.loc.filter((p): p is string | number => typeof p === "string" || typeof p === "number")
    : null;
  return {
    code: str(r.code),
    message: str(r.message) ?? "Unknown error.",
    loc,
    field: str(r.field),
    severity: str(r.severity),
    detail: r.detail ?? null,
  };
}

export class ApiError extends Error {
  override readonly name = "ApiError";
  readonly status: number;
  readonly errorType: ErrorType;
  readonly errors: ApiErrorItem[];
  readonly engineVersion: string | null;
  /** Seconds, from `Retry-After` (503 DATABASE_BUSY). */
  readonly retryAfter: number | null;

  constructor(init: {
    status: number;
    errorType: ErrorType;
    errors: ApiErrorItem[];
    engineVersion?: string | null;
    retryAfter?: number | null;
  }) {
    super(init.errors[0]?.message ?? `Request failed (${init.errorType}).`);
    this.status = init.status;
    this.errorType = init.errorType;
    this.errors = init.errors;
    this.engineVersion = init.engineVersion ?? null;
    this.retryAfter = init.retryAfter ?? null;
  }

  /** Codes of every error item, for matching specific cases (e.g. ENGINE_VERSION_MISMATCH). */
  get codes(): string[] {
    return this.errors.map((e) => e.code).filter((c): c is string => c !== null);
  }

  static fromResponse(status: number, body: unknown, headers?: Headers): ApiError {
    const env = asRecord(body);
    const rawType = str(env?.error_type);
    const errorType: ErrorType =
      rawType !== null && (KNOWN as readonly string[]).includes(rawType)
        ? (rawType as ErrorType)
        : "unknown";
    const rawErrors = Array.isArray(env?.errors) ? env.errors : [];
    const errors =
      rawErrors.length > 0
        ? rawErrors.map(item)
        : [item({ message: `The server returned HTTP ${String(status)}.` })];
    const retry = headers?.get("Retry-After");
    const retryAfter = retry === null || retry === undefined ? null : Number.parseInt(retry, 10);
    return new ApiError({
      status,
      errorType,
      errors,
      engineVersion: str(env?.engine_version),
      retryAfter: retryAfter === null || Number.isNaN(retryAfter) ? null : retryAfter,
    });
  }

  static network(): ApiError {
    return new ApiError({
      status: 0,
      errorType: "network",
      errors: [item({ code: "NETWORK_ERROR", message: "The server could not be reached." })],
    });
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
