import { useState } from "react";
import { AlertTriangle, Copy, FileText, Check } from "lucide-react";
import { useInstanceContext } from "../hooks/InstanceContext";
import { useDraftIncidentReport } from "../hooks/useRunbooks";
import { Card } from "../components/primitives/Card";
import { cn } from "../lib/cn";

type Tab = "technical" | "business";

export function InstanceReportPage() {
  const { name } = useInstanceContext();
  const draft = useDraftIncidentReport();
  const [tab, setTab] = useState<Tab>("technical");
  const [copied, setCopied] = useState(false);

  const report = draft.data;
  const body = report
    ? tab === "technical"
      ? report.technical_report
      : report.business_summary
    : "";

  async function copy() {
    await navigator.clipboard.writeText(body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <Card>
        <h1 className="text-sm font-semibold text-text-primary">Incident write-up</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Both documents render from one evidence object: the timeline, what fired, what was
          checked and the values seen. The engineering write-up and the paragraph for a director
          cannot disagree, because they share a source. The model narrates only — every number it
          writes is checked back against the evidence before you see it.
        </p>

        <button
          onClick={() => draft.mutate(name)}
          disabled={draft.isPending}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          <FileText className="h-4 w-4" />
          {draft.isPending ? "Drafting..." : "Draft the report"}
        </button>

        {draft.isError && (
          <p className="mt-3 rounded-lg border border-severity-critical-border bg-severity-critical-bg p-3 text-sm text-text-secondary">
            {draft.error instanceof Error ? draft.error.message : "Could not draft the report."}
          </p>
        )}
      </Card>

      {report && (
        <Card className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-1 rounded-lg border border-border-subtle bg-surface-sunken p-1">
              {(["technical", "business"] as Tab[]).map((id) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    tab === id
                      ? "bg-surface-card text-text-primary shadow-sm"
                      : "text-text-secondary"
                  )}
                >
                  {id === "technical" ? "For the engineer" : "For the director"}
                </button>
              ))}
            </div>

            <button
              onClick={copy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-sunken"
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy markdown"}
            </button>
          </div>

          {report.narration && !report.narration.available && (
            <p className="flex items-start gap-2 rounded-lg border border-severity-warning-border bg-severity-warning-bg p-3 text-sm text-text-secondary">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-warning" />
              <span>
                The narration model was unavailable, so the summary below was generated
                deterministically from the evidence. The findings are unaffected.
                <span className="mt-1 block font-mono text-xs text-text-tertiary">
                  {report.narration.unavailable_reason}
                </span>
              </span>
            </p>
          )}

          {report.narration?.available && !report.narration.verified && (
            <p className="flex items-start gap-2 rounded-lg border border-severity-warning-border bg-severity-warning-bg p-3 text-sm text-text-secondary">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-warning" />
              <span>
                Narration verification failed.
                {report.narration.unsupported_numbers.length > 0 && (
                  <> Numbers the evidence does not support as written:{" "}
                    <span className="font-mono text-xs">
                      {report.narration.unsupported_numbers.join(", ")}
                    </span>.
                  </>
                )}
                {report.narration.business_leaks.length > 0 && (
                  <> Technical identifiers were removed from the director summary.</>
                )}
              </span>
            </p>
          )}

          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-lg bg-surface-sunken p-4 text-sm leading-relaxed text-text-primary">
            {body}
          </pre>

          {report.narration && (
            <p className="text-xs text-text-tertiary">
              Narrated by {report.narration.model} · verified against the evidence object ·
              incident {report.incident_id}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
