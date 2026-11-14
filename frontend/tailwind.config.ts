import type { Config } from "tailwindcss";

import { colors } from "./src/styles/tokens";

/**
 * DealForge design tokens (plan section 7).
 *
 * The palette is deliberately CLOSED: `theme.colors` is replaced, not extended, so only the
 * approved colours exist as utilities. There is no generic red/green scale, which makes
 * "negative numbers in red" impossible to write by accident; status colours exist only under
 * the `status-*` names and are meant for status indicators alone.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    screens: {
      // D4-09: < 1024 unsupported (notice only); 1024–1279 compact; >= 1280 full layout.
      lg: "1024px",
      xl: "1280px",
      "2xl": "1440px",
    },
    colors: { ...colors },
    fontFamily: {
      sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"],
      mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
    },
    fontSize: {
      // [size, line-height]
      label: ["11px", "16px"], // uppercase column labels
      table: ["13px", "20px"], // all tables
      body: ["14px", "20px"], // body copy
      section: ["15px", "22px"], // 600-weight section headers
      title: ["20px", "28px"], // page titles
      kpi: ["20px", "26px"], // KPI tile values
    },
    borderRadius: {
      none: "0",
      sm: "2px",
      DEFAULT: "3px",
      md: "4px",
      full: "9999px",
    },
    // No decorative shadows (section 7): hairline borders only.
    boxShadow: { none: "none" },
    extend: {
      spacing: {
        row: "28px", // compact table row
        rail: "224px", // expanded left rail (>= 1280)
        "rail-compact": "56px", // icon rail (1024–1279)
        header: "48px",
      },
      transitionDuration: { DEFAULT: "150ms" },
    },
  },
  plugins: [],
};

export default config;
