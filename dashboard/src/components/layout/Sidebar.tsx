import { NavLink, useParams } from "react-router-dom";
import { ShieldCheck, LayoutGrid, Server, BookOpen } from "lucide-react";
import { useInstances, useFleetSnapshots } from "../../hooks/useInstances";
import { Pulse } from "../primitives/Pulse";
import { cn } from "../../lib/cn";

export function Sidebar() {
  const { name: activeInstance } = useParams<{ name: string }>();
  const { data } = useInstances();
  const instanceNames = data?.instances ?? [];
  const fleet = useFleetSnapshots(instanceNames);

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-border-subtle bg-surface-card">
      <div className="flex items-center gap-2 px-5 py-5">
        <ShieldCheck className="h-6 w-6 text-accent" />
        <span className="text-base font-semibold text-text-primary">SQLGuardian</span>
      </div>

      <nav className="flex flex-col gap-1 px-3">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-accent-bg text-accent"
                : "text-text-secondary hover:bg-surface-sunken"
            )
          }
        >
          <LayoutGrid className="h-4 w-4" />
          Fleet Overview
        </NavLink>

        <NavLink
          to="/runbooks"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-accent-bg text-accent"
                : "text-text-secondary hover:bg-surface-sunken"
            )
          }
        >
          <BookOpen className="h-4 w-4" />
          Runbooks
        </NavLink>
      </nav>

      <div className="mt-6 flex-1 overflow-y-auto px-3">
        <div className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
          Instances
        </div>
        <div className="flex flex-col gap-0.5">
          {instanceNames.length === 0 && (
            <p className="px-3 py-2 text-xs text-text-tertiary">No instances registered</p>
          )}
          {instanceNames.map((name, i) => {
            const severity = fleet[i]?.snapshot?.overall_severity ?? "unknown";
            const isActive = name === activeInstance;
            return (
              <NavLink
                key={name}
                to={`/instance/${encodeURIComponent(name)}`}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent-bg text-accent"
                    : "text-text-secondary hover:bg-surface-sunken"
                )}
              >
                <Server className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{name}</span>
                <Pulse severity={severity} className="ml-auto" />
              </NavLink>
            );
          })}
        </div>
      </div>

      <div className="border-t border-border-subtle px-5 py-4 text-xs text-text-tertiary">
        SQLGuardian v1.0
      </div>
    </aside>
  );
}
