/**
 * A small inline SVG icon set (no icon font, no external requests: CSP-safe). 1.5 px strokes,
 * 16 px by default. Decorative by default (aria-hidden); pass `label` when the icon carries
 * meaning on its own.
 */
export type IconName =
  | "dashboard"
  | "companies"
  | "runs"
  | "styleguide"
  | "logout"
  | "check"
  | "warning"
  | "error"
  | "info"
  | "lock"
  | "database"
  | "chevron-right"
  | "refresh";

const PATHS: Record<IconName, string[]> = {
  dashboard: ["M3 3h7v9H3z", "M14 3h7v5h-7z", "M14 12h7v9h-7z", "M3 16h7v5H3z"],
  companies: ["M4 21V5l8-2v18", "M12 9h8v12", "M7 8h2M7 12h2M7 16h2M15 13h2M15 17h2", "M2 21h20"],
  runs: ["M4 4h16v4H4z", "M5 8v12h14V8", "M10 12h4"],
  styleguide: ["M4 20h16", "M6 16l6-12 6 12", "M8.5 11h7"],
  logout: ["M15 4h4v16h-4", "M10 8l-4 4 4 4", "M6 12h10"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  warning: ["M12 3.5 22 20.5H2z", "M12 10v4.5", "M12 17.5v.5"],
  error: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M9 9l6 6M15 9l-6 6"],
  info: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 11v5.5", "M12 7.5v.5"],
  lock: ["M6 11h12v9H6z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3"],
  database: [
    "M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z",
    "M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6",
    "M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3",
  ],
  "chevron-right": ["M9 6l6 6-6 6"],
  refresh: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 4v7h-7"],
};

export function Icon({
  name,
  size = 16,
  label,
  className,
}: {
  name: IconName;
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={label === undefined ? undefined : "img"}
      aria-hidden={label === undefined ? true : undefined}
      aria-label={label}
      focusable="false"
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
