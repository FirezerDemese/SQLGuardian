import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        surface: {
          canvas: "var(--surface-canvas)",
          card: "var(--surface-card)",
          sunken: "var(--surface-sunken)",
        },
        border: {
          subtle: "var(--border-subtle)",
          DEFAULT: "var(--border-default)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          bg: "var(--accent-bg)",
          border: "var(--accent-border)",
        },
        severity: {
          healthy: "var(--sev-healthy)",
          "healthy-bg": "var(--sev-healthy-bg)",
          "healthy-border": "var(--sev-healthy-border)",
          warning: "var(--sev-warning)",
          "warning-bg": "var(--sev-warning-bg)",
          "warning-border": "var(--sev-warning-border)",
          critical: "var(--sev-critical)",
          "critical-bg": "var(--sev-critical-bg)",
          "critical-border": "var(--sev-critical-border)",
          unknown: "var(--sev-unknown)",
          "unknown-bg": "var(--sev-unknown-bg)",
          "unknown-border": "var(--sev-unknown-border)",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
