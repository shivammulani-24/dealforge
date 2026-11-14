import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The standard surface: white, 1 px slate border, no shadow. Optional header (title, meta such
 * as the unit, actions) and footer (e.g. the basis legend under a table).
 */
export function Panel({
  title,
  meta,
  actions,
  footer,
  children,
  className,
  bodyClassName,
  as: Tag = "section",
}: {
  title?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  as?: "section" | "div" | "article";
}) {
  const hasHeader = title !== undefined || meta !== undefined || actions !== undefined;
  return (
    <Tag className={cn("min-w-0 rounded border border-slate-200 bg-white", className)}>
      {hasHeader ? (
        <header className="flex min-h-10 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-slate-200 px-4 py-2">
          <div className="flex min-w-0 items-baseline gap-3">
            {title === undefined ? null : (
              <h2 className="text-section font-semibold text-slate-900">{title}</h2>
            )}
            {meta === undefined ? null : <span className="text-table text-slate-500">{meta}</span>}
          </div>
          {actions === undefined ? null : <div className="flex items-center gap-2">{actions}</div>}
        </header>
      ) : null}
      <div className={cn("min-w-0", bodyClassName ?? "p-4")}>{children}</div>
      {footer === undefined ? null : (
        <footer className="border-t border-slate-200 px-4 py-2 text-label text-slate-600">
          {footer}
        </footer>
      )}
    </Tag>
  );
}

/** Page title block: breadcrumb trail, title, unit/meta and page-level actions. */
export function PageHeader({
  breadcrumbs,
  title,
  meta,
  actions,
}: {
  breadcrumbs?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 border-b border-slate-200 pb-3">
      <div className="min-w-0">
        {breadcrumbs === undefined ? null : (
          <nav aria-label="Breadcrumb" className="mb-1 text-table text-slate-500">
            {breadcrumbs}
          </nav>
        )}
        <div className="flex flex-wrap items-baseline gap-x-3">
          <h1 className="text-title font-semibold text-slate-900">{title}</h1>
          {meta === undefined ? null : <span className="text-table text-slate-600">{meta}</span>}
        </div>
      </div>
      {actions === undefined ? null : <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/**
 * Main content with a side panel. At >= 1280 px the side panel sits beside the content; at
 * 1024–1279 px it moves below it (D4-09).
 */
export function SidePanelLayout({ main, side }: { main: ReactNode; side: ReactNode }) {
  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0">{main}</div>
      <aside className="min-w-0" aria-label="Details">
        {side}
      </aside>
    </div>
  );
}
