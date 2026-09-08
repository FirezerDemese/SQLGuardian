import { AlertTriangle, ShieldCheck } from "lucide-react";
import { useInstanceContext } from "../hooks/InstanceContext";
import { useConditions } from "../hooks/useRunbooks";
import { ConditionCard } from "../components/response/ConditionCard";
import { EmptyState } from "../components/primitives/EmptyState";
import { Skeleton } from "../components/primitives/Skeleton";

export function InstanceResponsePage() {
  const { name } = useInstanceContext();
  const { data, isLoading, isError } = useConditions(name);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <EmptyState
          icon={AlertTriangle}
          title="Could not read the current conditions"
          description="The API is unreachable or the instance is not registered."
        />
      </div>
    );
  }

  const withProcedure = data.conditions.filter((c) => c.runbook.has_team_procedure).length;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="rounded-xl border border-border-subtle bg-surface-card p-5">
        <p className="text-sm text-text-secondary">
          {data.condition_count === 0 ? (
            "No conditions are firing. Nothing to respond to."
          ) : (
            <>
              <span className="font-semibold text-text-primary">
                {data.condition_count} condition{data.condition_count === 1 ? "" : "s"}
              </span>{" "}
              firing, ranked by blast radius — what happens if it is left alone, not how
              loud it is.{" "}
              <span className="font-semibold text-text-primary">{withProcedure}</span> of them
              have a documented team procedure.
            </>
          )}
        </p>

        {data.failed_checks.length > 0 && (
          <p className="mt-3 flex items-start gap-2 rounded-lg border border-severity-warning-border bg-severity-warning-bg p-3 text-sm text-text-secondary">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-warning" />
            <span>
              {data.failed_checks.length} check(s) could not run:{" "}
              <span className="font-mono text-xs">{data.failed_checks.join(", ")}</span>. That
              is not the same as healthy — those areas are unknown right now.
            </span>
          </p>
        )}
      </div>

      {data.conditions.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="Nothing is firing"
          description="Every check returned inside its threshold at the last poll."
        />
      ) : (
        data.conditions.map((condition, index) => (
          <ConditionCard key={condition.code} condition={condition} position={index + 1} />
        ))
      )}
    </div>
  );
}
