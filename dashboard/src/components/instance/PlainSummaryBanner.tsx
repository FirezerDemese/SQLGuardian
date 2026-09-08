import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { buildPlainSummary } from "../../lib/plainSummary";
import { cn } from "../../lib/cn";
import type { Snapshot } from "../../types/api";

const bannerStyle: Record<string, string> = {
  healthy: "bg-severity-healthy-bg border-severity-healthy-border text-severity-healthy",
  warning: "bg-severity-warning-bg border-severity-warning-border text-severity-warning",
  critical: "bg-severity-critical-bg border-severity-critical-border text-severity-critical",
  unknown: "bg-severity-unknown-bg border-severity-unknown-border text-severity-unknown",
};

export function PlainSummaryBanner({ snapshot }: { snapshot: Snapshot | undefined }) {
  const navigate = useNavigate();
  const lines = buildPlainSummary(snapshot);
  const severity = snapshot?.overall_severity ?? "unknown";

  if (lines.length === 0) return null;

  return (
    <div
      className={cn("rounded-xl border p-5", bannerStyle[severity])}
    >
      <ul className="space-y-1.5 text-sm text-text-primary">
        {lines.map((line, i) => (
          <li key={i} className="flex gap-2">
            <span className="select-none">•</span>
            {line}
          </li>
        ))}
      </ul>
      {severity !== "healthy" && (
        <button
          onClick={() => navigate("ai")}
          className="mt-3 flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Ask AI to Explain
        </button>
      )}
    </div>
  );
}
