/**
 * Application shell (plan section 7, D4-09):
 * - navy left rail and header; white canvas;
 * - >= 1280 px: expanded rail with labels;
 * - 1024–1279 px: rail collapses to icons, each with a tooltip (the label stays available to
 *   assistive technology);
 * - < 1024 px: a non-blocking notice; no mobile layout (LIM-24);
 * - the page never scrolls sideways: the content column is `min-w-0` and wide content scrolls
 *   inside its own container.
 */
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";

import { useMe } from "@/api/queries/system";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/companies", label: "Companies", icon: "companies" },
  { to: "/runs", label: "Saved runs", icon: "runs" },
  { to: "/style-guide", label: "Design system", icon: "styleguide" },
];

function RailLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={item.end ?? false}
      className={({ isActive }) =>
        cn(
          "group relative flex h-9 items-center gap-3 rounded px-2.5 text-body transition-colors",
          "justify-center xl:justify-start",
          isActive ? "bg-navy-800 text-white" : "text-navy-300 hover:bg-navy-800 hover:text-white",
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden="true"
            className={cn(
              "absolute left-0 top-1.5 h-6 w-0.5 rounded-full",
              isActive ? "bg-accent-line" : "bg-transparent",
            )}
          />
          <Icon name={item.icon} size={18} className="shrink-0" />
          {/* Visible label at >= 1280; screen-reader label below that. */}
          <span className="sr-only xl:not-sr-only xl:truncate">{item.label}</span>
          {/* Tooltip for the compact rail (decorative: the label above is the accessible name). */}
          <span
            aria-hidden="true"
            data-rail-tooltip=""
            className="pointer-events-none invisible absolute left-full z-50 ml-2 whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-table text-white group-hover:visible group-focus-visible:visible xl:hidden"
          >
            {item.label}
          </span>
        </>
      )}
    </NavLink>
  );
}

function Rail() {
  // The navy column spans the full page height; only the inner nav is sticky.
  return (
    <div className="w-rail-compact shrink-0 self-stretch bg-navy-900 xl:w-rail">
      <nav aria-label="Main" data-rail="" className="sticky top-0 flex h-screen flex-col">
        <div className="flex h-header items-center justify-center border-b border-navy-800 px-3 xl:justify-start">
          <span className="flex h-7 w-7 items-center justify-center rounded-sm border border-navy-700 text-table font-semibold text-white">
            DF
          </span>
          <span className="ml-2.5 hidden text-section font-semibold tracking-tight text-white xl:inline">
            DealForge
          </span>
        </div>
        <ul className="flex flex-col gap-0.5 p-2">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <RailLink item={item} />
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

function SessionBanner() {
  const { expiringSoon, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  if (!expiringSoon) return null;
  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-2 border-b border-status-warn bg-status-warn-subtle px-6 py-1.5 text-table text-slate-800"
    >
      <span className="flex items-center gap-2">
        <Icon name="warning" size={14} className="text-status-warn" />
        Your session expires within two minutes. Log in again to keep working.
      </span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          const next = `${location.pathname}${location.search}`;
          void logout().then(() => {
            navigate(`/login?${new URLSearchParams({ next }).toString()}`, { replace: true });
          });
        }}
      >
        Log in again
      </Button>
    </div>
  );
}

function Header() {
  const { logout } = useAuth();
  const me = useMe();
  return (
    <header className="flex h-header shrink-0 items-center justify-between gap-4 bg-navy-900 px-6 text-white">
      <span className="truncate text-table text-navy-300">Professional valuation workspace</span>
      <div className="flex min-w-0 items-center gap-3">
        <span className="truncate text-table text-navy-300" data-testid="current-user">
          {me.data?.email ?? ""}
        </span>
        <Button
          variant="on-navy"
          size="sm"
          onClick={() => {
            void logout();
          }}
        >
          <Icon name="logout" size={14} />
          Log out
        </Button>
      </div>
    </header>
  );
}

export function ViewportNotice() {
  return (
    <div
      role="note"
      data-viewport-notice=""
      className="border-b border-slate-300 bg-slate-100 px-4 py-1.5 text-table text-slate-700 lg:hidden"
    >
      DealForge is designed for desktop screens (1024 px and wider). Some layouts may not fit.
    </div>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-screen w-full bg-white">
      <Rail />
      <div className="flex min-w-0 flex-1 flex-col">
        <ViewportNotice />
        <Header />
        <SessionBanner />
        <main id="main" className="min-w-0 flex-1 px-6 py-5 2xl:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
