import { useState } from "react";
import { Wrench, ShieldAlert } from "lucide-react";
import { useAiSuggest } from "../../hooks/useAi";
import { Card } from "../primitives/Card";
import { AiMeta, RiskBadge } from "./AiMeta";

export function SuggestView() {
  const [issueFocus, setIssueFocus] = useState("");
  const mutation = useAiSuggest();
  const result = mutation.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <input
          value={issueFocus}
          onChange={(e) => setIssueFocus(e.target.value)}
          placeholder="Optional focus, e.g. blocking, disk space, failed jobs"
          className="flex-1 rounded-lg border border-border-subtle bg-surface-card px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        />
        <button
          onClick={() => mutation.mutate({ issue_focus: issueFocus || undefined, fresh: false })}
          disabled={mutation.isPending}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <Wrench className="h-4 w-4" />
          {mutation.isPending ? "Thinking..." : "Suggest Fixes"}
        </button>
      </div>

      {mutation.isError && (
        <p className="text-sm text-severity-critical">Failed to reach the AI engine.</p>
      )}
      {result?.error && <p className="text-sm text-severity-critical">{result.error}</p>}

      {result && !result.error && (
        <Card>
          {result.immediate_actions.length > 0 && (
            <div className="mb-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                Immediate Actions
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-secondary">
                {result.immediate_actions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-col gap-3">
            {result.remediations.map((r, i) => (
              <div key={i} className="rounded-lg border border-border-subtle p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-text-primary">{r.title}</span>
                  <RiskBadge risk={r.risk_level} />
                </div>
                <p className="mt-1 text-sm text-text-secondary">{r.description}</p>
                {r.tsql && (
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-sunken p-3 text-xs text-text-primary">
                    <code>{r.tsql}</code>
                  </pre>
                )}
                <p className="mt-2 text-xs text-text-tertiary">
                  Expected outcome: {r.expected_outcome}
                </p>
                {r.requires_approval && (
                  <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-severity-warning">
                    <ShieldAlert className="h-3.5 w-3.5" />
                    Requires manual approval before running
                  </div>
                )}
              </div>
            ))}
          </div>

          {result.monitoring_followup && (
            <div className="mt-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                Monitoring Follow-up
              </div>
              <p className="mt-1 text-sm text-text-secondary">{result.monitoring_followup}</p>
            </div>
          )}

          <AiMeta generatedAt={result.generated_at} model={result.model} />
        </Card>
      )}
    </div>
  );
}
