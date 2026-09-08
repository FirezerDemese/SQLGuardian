import { Sparkles } from "lucide-react";
import { useAiExplain } from "../../hooks/useAi";
import { Card } from "../primitives/Card";
import { Badge } from "../primitives/Badge";
import { AiMeta, PriorityBadge } from "./AiMeta";

export function ExplainView() {
  const mutation = useAiExplain();
  const result = mutation.data;

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={() => mutation.mutate({ fresh: false })}
        disabled={mutation.isPending}
        className="flex w-fit items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        <Sparkles className="h-4 w-4" />
        {mutation.isPending ? "Analyzing..." : "Explain Current Health"}
      </button>

      {mutation.isError && (
        <p className="text-sm text-severity-critical">Failed to reach the AI engine.</p>
      )}

      {result?.error && <p className="text-sm text-severity-critical">{result.error}</p>}

      {result && !result.error && (
        <Card>
          <div className="mb-2 flex items-center gap-2">
            <Badge severity={result.severity_label} />
          </div>
          <h3 className="text-base font-semibold text-text-primary">{result.headline}</h3>

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                For the DBA
              </div>
              <p className="mt-1 text-sm text-text-secondary">{result.dba_summary}</p>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                For the Manager
              </div>
              <p className="mt-1 text-sm text-text-secondary">{result.manager_summary}</p>
            </div>
          </div>

          {result.top_issues.length > 0 && (
            <div className="mt-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                Top Issues
              </div>
              <div className="mt-2 flex flex-col gap-3">
                {result.top_issues.map((issue, i) => (
                  <div key={i} className="rounded-lg border border-border-subtle p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-text-primary">{issue.issue}</span>
                      <PriorityBadge priority={issue.priority} />
                    </div>
                    <p className="mt-1 text-sm text-text-secondary">{issue.detail}</p>
                    <p className="mt-1 text-xs text-text-tertiary">Impact: {issue.impact}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-5">
            <div className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              Root Cause
            </div>
            <p className="mt-1 text-sm text-text-secondary">{result.root_cause}</p>
          </div>

          <AiMeta generatedAt={result.generated_at} model={result.model} />
        </Card>
      )}
    </div>
  );
}
