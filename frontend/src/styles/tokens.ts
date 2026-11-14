/**
 * DealForge colour tokens (plan section 7): the single source of truth, used by
 * tailwind.config.ts for utilities and by chart code, which needs literal colours.
 *
 * The palette is CLOSED: there is no generic red or green scale. Status colours exist only
 * under `status` and are for status indicators alone; negatives are shown with parentheses,
 * never colour.
 */
export const slate = {
  50: "#F8FAFC", // table stripes, subtle surfaces
  100: "#F1F5F9",
  200: "#E2E8F0", // borders, rules
  300: "#CBD5E1",
  400: "#94A3B8",
  500: "#64748B",
  600: "#475569", // secondary text
  700: "#334155",
  800: "#1E293B",
  900: "#0F172A", // primary text ("near-black" for backend outputs)
};

export const colors = {
  transparent: "transparent",
  current: "currentColor",
  white: "#FFFFFF",
  slate,
  navy: {
    950: "#071224",
    900: "#0B1B33", // rail and header
    800: "#14284A",
    700: "#1E3760",
    300: "#93A4BF", // muted text on navy
  },
  accent: {
    DEFAULT: "#1F5FBF", // interactive elements and ASSUMED inputs
    hover: "#194E9E",
    subtle: "#EEF4FC", // unsaved draft cells
    line: "#A9C4EC",
  },
  // Sensitivity heat shading (lib/heat.ts): blue for up, slate for down, never red/green.
  heat: {
    "up-1": "#EEF4FC",
    "up-2": "#D9E6F7",
    "up-3": "#BFD4F1",
    "down-1": "#F4F6F9",
    "down-2": "#E6EAF0",
    "down-3": "#D3DAE4",
  },
  status: {
    ok: "#027A48",
    "ok-subtle": "#ECFDF3",
    warn: "#B7791F",
    "warn-subtle": "#FFFAEB",
    error: "#B42318",
    "error-subtle": "#FEF3F2",
  },
} as const;
