export function AiMeta({ generatedAt, model }: { generatedAt: string; model: string }) {
  return (
    <p className="mt-4 text-xs text-text-tertiary">
      Generated {generatedAt.slice(0, 19).replace("T", " ")} UTC · {model}
    </p>
  );
}

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-severity-critical-bg text-severity-critical",
  medium: "bg-severity-warning-bg text-severity-warning",
  low: "bg-severity-healthy-bg text-severity-healthy",
};

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
        PRIORITY_STYLE[priority] ?? "bg-surface-sunken text-text-secondary"
      }`}
    >
      {priority}
    </span>
  );
}

const RISK_STYLE: Record<string, string> = {
  safe: "bg-severity-healthy-bg text-severity-healthy",
  low: "bg-severity-healthy-bg text-severity-healthy",
  medium: "bg-severity-warning-bg text-severity-warning",
  high: "bg-severity-critical-bg text-severity-critical",
};

export function RiskBadge({ risk }: { risk: string }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
        RISK_STYLE[risk] ?? "bg-surface-sunken text-text-secondary"
      }`}
    >
      {risk} risk
    </span>
  );
}
