import { BookOpen, FileWarning, Hand } from "lucide-react";
import type { DetectedCondition } from "../../types/api";
import { Badge } from "../primitives/Badge";
import { Card } from "../primitives/Card";
import { ActionList } from "./ActionList";

export function ConditionCard({
  condition,
  position,
}: {
  condition: DetectedCondition;
  position: number;
}) {
  const { runbook, plan } = condition;

  return (
    <Card className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-text-tertiary">#{position}</span>
            <span className="rounded-md bg-surface-sunken px-2 py-0.5 font-mono text-xs font-semibold text-text-secondary">
              {condition.code}
            </span>
            <Badge severity={condition.severity} />
          </div>
          <h3 className="mt-2 text-base font-semibold text-text-primary">{condition.title}</h3>
          <p className="mt-1 text-sm text-text-secondary">{condition.detail}</p>
        </div>

        <div className="text-right">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            Blast radius
          </p>
          <p className="text-2xl font-semibold tabular-nums text-text-primary">
            {condition.impact_score}
          </p>
          <p className="text-xs text-text-tertiary">{condition.scope}</p>
        </div>
      </div>

      <section>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          Evidence
        </h4>
        <ul className="flex flex-col gap-1">
          {condition.evidence.map((line) => (
            <li key={line} className="text-sm text-text-secondary">
              <span className="mr-2 text-text-tertiary">-</span>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          <BookOpen className="h-3.5 w-3.5" />
          Your team's procedure
        </h4>

        {runbook.has_team_procedure ? (
          <div className="flex flex-col gap-3">
            {runbook.sections.map((section) => (
              <div
                key={section.anchor}
                className="rounded-lg border border-accent-border bg-accent-bg/40 p-3"
              >
                <p className="text-sm font-medium text-text-primary">
                  {section.heading_path.join(" > ")}
                </p>
                <p className="mt-0.5 font-mono text-xs text-text-tertiary">{section.citation}</p>
                <p className="mt-1 text-xs text-text-tertiary">
                  Matched because: {section.match_reason}. Mapped to this condition:{" "}
                  {section.mapping_reason}.
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex gap-2 rounded-lg border border-severity-warning-border bg-severity-warning-bg p-3">
            <FileWarning className="mt-0.5 h-4 w-4 shrink-0 text-severity-warning" />
            <div>
              <p className="text-sm font-medium text-text-primary">
                No documented procedure covers {condition.code}
              </p>
              <p className="mt-0.5 text-sm text-text-secondary">
                {runbook.note ??
                  "The actions below are SQLGuardian's generic baseline, not your team's process."}
              </p>
            </div>
          </div>
        )}
      </section>

      {condition.hold_off.length > 0 && (
        <section>
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            <Hand className="h-3.5 w-3.5" />
            Not yet
          </h4>
          <ul className="flex flex-col gap-1.5">
            {condition.hold_off.map((line) => (
              <li key={line} className="text-sm text-text-secondary">
                <span className="mr-2 text-text-tertiary">-</span>
                {line}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          Actions, least destructive first
        </h4>
        <ActionList actions={plan.actions} />
      </section>
    </Card>
  );
}
