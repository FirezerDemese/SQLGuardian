import type { Severity } from "./api";

const ORDER: Record<Severity, number> = {
  critical: 0,
  warning: 1,
  unknown: 2,
  healthy: 3,
};

export function severityRank(s: Severity): number {
  return ORDER[s] ?? ORDER.unknown;
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
  unknown: "Unknown",
};

// Resolved hex values (mirrors the CSS custom properties in index.css) for contexts
// that need a literal color string, e.g. inline SVG/chart fills via Recharts.
export const SEVERITY_HEX: Record<Severity, string> = {
  healthy: "#16a34a",
  warning: "#d97706",
  critical: "#dc2626",
  unknown: "#64748b",
};
