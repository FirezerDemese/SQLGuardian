import { useState } from "react";
import { BookOpen, ChevronDown, Eye, Lock, ShieldAlert, Undo2 } from "lucide-react";
import type { ActionCandidate, BlastRadius } from "../../types/api";
import { cn } from "../../lib/cn";

const BLAST_LABEL: Record<BlastRadius, string> = {
  read_only: "Read only",
  session: "One session",
  database: "One database",
  instance: "Whole instance",
  host: "Host / storage",
};

const BLAST_STYLE: Record<BlastRadius, string> = {
  read_only: "bg-severity-healthy-bg text-severity-healthy border-severity-healthy-border",
  session: "bg-severity-warning-bg text-severity-warning border-severity-warning-border",
  database: "bg-severity-warning-bg text-severity-warning border-severity-warning-border",
  instance: "bg-severity-critical-bg text-severity-critical border-severity-critical-border",
  host: "bg-severity-critical-bg text-severity-critical border-severity-critical-border",
};

/**
 * Renders the ordering it is given. The order is computed server-side in
 * core/actions.py from each action's blast radius, reversibility and approval
 * flag - this component never sorts, and the model never chooses.
 */
export function ActionList({ actions }: { actions: ActionCandidate[] }) {
  return (
    <ol className="flex flex-col gap-2">
      {actions.map((action, index) => (
        <ActionRow key={`${action.action}-${index}`} action={action} position={index + 1} />
      ))}
    </ol>
  );
}

function ActionRow({ action, position }: { action: ActionCandidate; position: number }) {
  const [open, setOpen] = useState(false);

  return (
    <li
      className={cn(
        "rounded-lg border bg-surface-card",
        action.destructive
          ? "border-severity-critical-border"
          : "border-border-subtle"
      )}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
      >
        <span className="mt-0.5 w-5 shrink-0 text-xs font-semibold text-text-tertiary">
          {position}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{action.action}</span>

            {action.source === "runbook" ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-accent-border bg-accent-bg px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
                <BookOpen className="h-3 w-3" />
                Your runbook
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-md border border-border-subtle bg-surface-sunken px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
                Generic guidance
              </span>
            )}

            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                BLAST_STYLE[action.blast_radius]
              )}
            >
              {action.blast_radius === "read_only" ? (
                <Eye className="h-3 w-3" />
              ) : (
                <ShieldAlert className="h-3 w-3" />
              )}
              {BLAST_LABEL[action.blast_radius]}
            </span>

            {action.requires_approval && (
              <span className="inline-flex items-center gap-1 rounded-md border border-border-subtle bg-surface-sunken px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                <Lock className="h-3 w-3" />
                Approval required
              </span>
            )}

            {!action.reversible && (
              <span className="inline-flex items-center gap-1 rounded-md border border-severity-critical-border bg-severity-critical-bg px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-severity-critical">
                <Undo2 className="h-3 w-3" />
                Cannot be undone
              </span>
            )}
          </span>

          <span className="mt-1 block text-sm text-text-secondary">{action.what_it_does}</span>
        </span>

        <ChevronDown
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0 text-text-tertiary transition-transform",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <div className="border-t border-border-subtle px-4 py-3 pl-12">
          <Field label="Expected effect">{action.expected_effect}</Field>
          <Field label="Rollback">{action.how_to_undo}</Field>
          {action.citation && (
            <Field label="Source">
              <span className="font-mono text-xs">{action.citation}</span>
            </Field>
          )}
          {action.tsql && (
            <div className="mt-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                T-SQL — run it yourself, SQLGuardian will not
              </p>
              <pre className="overflow-x-auto rounded-lg bg-surface-sunken p-3 text-xs leading-relaxed text-text-primary">
                <code>{action.tsql}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-2 first:mt-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">{label}</p>
      <p className="mt-0.5 text-sm text-text-secondary">{children}</p>
    </div>
  );
}
