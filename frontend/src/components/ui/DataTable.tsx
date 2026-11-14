/**
 * Table primitives for dense financial tables (plan section 7):
 * - 13 px text, 28 px rows, 11 px uppercase column labels;
 * - years as columns, oldest left; a vertical rule and shaded "Forecast" header separate
 *   historical from forecast columns;
 * - subtotal rows bold with a top border;
 * - sticky header and sticky first column. A wide table scrolls horizontally INSIDE its
 *   container (`TableScroll`), so the page itself never scrolls sideways (D4-09).
 */
import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function TableScroll({
  label,
  children,
  maxHeightClass,
}: {
  /** Accessible name of the scroll region (it is keyboard-focusable so it can be scrolled). */
  label: string;
  children: ReactNode;
  /** e.g. "max-h-[420px]" to keep the header sticky while scrolling vertically. */
  maxHeightClass?: string;
}) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      data-table-scroll=""
      className={cn("relative w-full min-w-0 overflow-auto", maxHeightClass)}
    >
      {children}
    </div>
  );
}

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <table className={cn("w-full border-separate border-spacing-0 text-table", className)}>
      {children}
    </table>
  );
}

interface CellFlags {
  /** Sticky first (label) column. */
  first?: boolean | undefined;
  /** Numeric cell: right-aligned, tabular figures. */
  numeric?: boolean | undefined;
  /** Forecast column (shaded header). */
  forecast?: boolean | undefined;
  /** Vertical rule on the left (first forecast column). */
  divider?: boolean | undefined;
}

function flagClasses({ first, numeric, divider }: CellFlags): string {
  return cn(
    first === true && "sticky left-0 z-10 border-r border-slate-200 text-left",
    numeric === true && "df-num",
    divider === true && "border-l border-l-slate-400",
  );
}

export function Th({
  first,
  numeric,
  forecast,
  divider,
  className,
  children,
  ...rest
}: CellFlags & ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        "df-label sticky top-0 h-row border-b border-slate-300 px-3 font-semibold",
        first === true ? "z-30" : "z-20",
        forecast === true ? "bg-slate-100" : "bg-slate-50",
        numeric === true ? "text-right" : "text-left",
        flagClasses({ first, numeric: false, forecast, divider }),
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

export type RowVariant = "default" | "subtotal" | "section";

export function Tr({
  variant = "default",
  children,
}: {
  variant?: RowVariant;
  children: ReactNode;
}) {
  return (
    <tr
      data-variant={variant}
      className={cn(
        "group",
        variant === "subtotal" && "font-semibold",
        variant === "section" && "df-label",
      )}
    >
      {children}
    </tr>
  );
}

export function Td({
  first,
  numeric,
  forecast,
  divider,
  subtotal,
  className,
  children,
  ...rest
}: CellFlags & { subtotal?: boolean } & TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn(
        "h-row whitespace-nowrap border-b border-slate-200 bg-white px-3 group-hover:bg-slate-50",
        subtotal === true && "border-t border-t-slate-400",
        flagClasses({ first, numeric, forecast, divider }),
        className,
      )}
      {...rest}
    >
      {children}
    </td>
  );
}

/** A row label with an optional trailing element (e.g. the basis badge for the whole row). */
export function RowLabel({ children, trailing }: { children: ReactNode; trailing?: ReactNode }) {
  return (
    <span className="flex items-center justify-between gap-3">
      <span className="truncate">{children}</span>
      {trailing}
    </span>
  );
}
