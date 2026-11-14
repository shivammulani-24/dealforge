/**
 * Loading, empty, error and stale states (plan section 1, "Loading, error and duplicate-
 * submission handling"). Errors are rendered from the backend envelope (`ApiError`); nothing
 * here invents a message the server didn't send, except for network failures.
 */
import type { ReactNode } from "react";

import type { ApiError } from "@/api/errors";
import { cn } from "@/lib/cn";

import { StatusIndicator, Tag } from "./Badge";
import { Button } from "./Button";
import { Icon } from "./Icon";

/** Skeleton block that keeps the final layout while loading. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("rounded-sm bg-slate-100", className)} />;
}

export function SkeletonRows({ rows = 4, label }: { rows?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-2">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-5 w-full" />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}

/** Background refetch: content stays visible, with a small "updating" indicator. */
export function UpdatingIndicator() {
  return (
    <span role="status" className="inline-flex items-center gap-1 text-label text-slate-500">
      <Icon name="refresh" size={12} />
      Updating…
    </span>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 rounded border border-dashed border-slate-300 bg-slate-50 px-5 py-6">
      <p className="text-section font-semibold text-slate-900">{title}</p>
      {children === undefined ? null : (
        <div className="max-w-prose text-body text-slate-600">{children}</div>
      )}
      {action}
    </div>
  );
}

const TITLES: Partial<Record<ApiError["errorType"], string>> = {
  validation: "The request was not accepted",
  calculation: "The model can't be calculated with these inputs",
  not_found: "Not found or not yours",
  conflict: "Conflict",
  immutable: "Frozen runs can't be changed",
  authentication: "Your session has ended",
  unavailable: "The database is busy",
  network: "The server could not be reached",
};

/**
 * Error panel. Calculation errors list each engine issue (code, field, message); network and
 * 5xx errors offer a Retry button (POSTs are never retried automatically).
 */
export function ErrorPanel({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const retryable = error.errorType === "network" || error.status >= 500;
  return (
    <div
      role="alert"
      className="rounded border border-status-error bg-status-error-subtle px-4 py-3"
      data-error-type={error.errorType}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <StatusIndicator tone="error">
          <span className="font-semibold">{TITLES[error.errorType] ?? "Something went wrong"}</span>
        </StatusIndicator>
        <div className="flex items-center gap-2">
          {error.engineVersion === null ? null : <Tag mono>engine {error.engineVersion}</Tag>}
          {error.status === 0 ? null : <Tag mono>HTTP {error.status}</Tag>}
        </div>
      </div>
      <ul className="mt-2 flex flex-col gap-1.5">
        {error.errors.map((e, i) => (
          <li key={`${e.code ?? "error"}-${String(i)}`} className="text-table text-slate-800">
            <span className="flex flex-wrap items-baseline gap-x-2">
              {e.code === null ? null : <code className="df-code font-medium">{e.code}</code>}
              {e.field === null ? null : (
                <span className="df-code text-slate-500">field: {e.field}</span>
              )}
              {e.loc === null ? null : (
                <span className="df-code text-slate-500">at: {e.loc.join(".")}</span>
              )}
            </span>
            <span className="block">{e.message}</span>
          </li>
        ))}
      </ul>
      {retryable && onRetry !== undefined ? (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

/**
 * Results produced from inputs that are now invalid: greyed out and labelled
 * "Stale – inputs invalid" (plan section 1, calculation errors).
 */
export function StaleOverlay({ stale, children }: { stale: boolean; children: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2" data-stale={stale || undefined}>
      {stale ? <Tag tone="warn">Stale – inputs invalid</Tag> : null}
      <div
        className={cn(
          "w-full transition-opacity",
          stale && "pointer-events-none select-none opacity-40",
        )}
        aria-hidden={stale || undefined}
      >
        {children}
      </div>
    </div>
  );
}

export interface IssueItem {
  code: string;
  message: string;
  severity: string;
  field?: string | null;
}

const SEVERITY_TONE: Record<string, "error" | "warn" | "info"> = {
  error: "error",
  warning: "warn",
  info: "info",
};

/** Engine issues and warnings, severity shown by icon and text. */
export function IssueList({ issues }: { issues: IssueItem[] }) {
  if (issues.length === 0) return <StatusIndicator tone="ok">No issues</StatusIndicator>;
  return (
    <ul className="flex flex-col divide-y divide-slate-200">
      {issues.map((issue, i) => (
        <li
          key={`${issue.code}-${String(i)}`}
          className="flex flex-col gap-0.5 py-2 first:pt-0 last:pb-0"
        >
          <span className="flex flex-wrap items-center gap-2">
            <StatusIndicator tone={SEVERITY_TONE[issue.severity] ?? "info"}>
              <span className="capitalize">{issue.severity}</span>
            </StatusIndicator>
            <code className="df-code">{issue.code}</code>
            {issue.field === null || issue.field === undefined ? null : (
              <span className="df-code text-slate-500">{issue.field}</span>
            )}
          </span>
          <span className="text-table text-slate-700">{issue.message}</span>
        </li>
      ))}
    </ul>
  );
}

/** R4: shown whenever the data is synthetic. */
export function SyntheticBanner({ subject }: { subject?: string }) {
  return (
    <div
      role="note"
      className="flex items-center gap-2 rounded border border-status-warn bg-status-warn-subtle px-3 py-1.5 text-table text-slate-800"
    >
      <Icon name="warning" size={14} className="shrink-0 text-status-warn" />
      <span>
        <span className="font-semibold">SYNTHETIC – not real data.</span>{" "}
        {subject ?? "Every figure on this page comes from the synthetic sample company."}
      </span>
    </div>
  );
}
