import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import {
  LayoutDashboard,
  ListChecks,
  Database,
  AlertOctagon,
  Activity,
  Sparkles,
  Siren,
  FileText,
} from "lucide-react";
import { useSnapshot } from "../hooks/useSnapshot";
import { InstanceContextProvider } from "../hooks/InstanceContext";
import { TopBar } from "../components/layout/TopBar";
import { ConnectionBanner } from "../components/layout/ConnectionBanner";
import { cn } from "../lib/cn";

const TABS = [
  { to: "", label: "Overview", icon: LayoutDashboard, end: true },
  // Response is the primary workflow: condition -> team procedure -> ordered actions.
  { to: "response", label: "Response", icon: Siren, end: false },
  { to: "report", label: "Write-up", icon: FileText, end: false },
  { to: "ai", label: "AI Brain", icon: Sparkles, end: false },
  { to: "jobs", label: "Agent Jobs", icon: ListChecks, end: false },
  { to: "databases", label: "Databases", icon: Database, end: false },
  { to: "blocking", label: "Blocking", icon: AlertOctagon, end: false },
  { to: "waits", label: "Waits", icon: Activity, end: false },
];

export function InstanceLayout() {
  const { name } = useParams<{ name: string }>();
  const location = useLocation();
  const query = useSnapshot(name);
  const snapshot = query.data;

  const tabLabel =
    TABS.find((t) => t.to !== "" && location.pathname.endsWith(`/${t.to}`))?.label ?? "Overview";

  if (!name) return null;

  return (
    <InstanceContextProvider value={{ name, query }}>
      <div className="flex h-full flex-col">
        <TopBar
          instanceName={name}
          tabLabel={tabLabel}
          lastUpdated={query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : undefined}
          isFetching={query.isFetching}
          onRefresh={() => query.refetch()}
        />
        {query.isError && (
          <ConnectionBanner message="Lost connection to SQLGuardian API — retrying..." />
        )}

        <div className="flex items-center gap-1 border-b border-border-subtle bg-surface-card px-6">
          {TABS.map((tab) => {
            const badgeCount =
              tab.to === "jobs"
                ? snapshot?.agent_jobs.failed_count
                : tab.to === "databases"
                ? snapshot?.database_status.databases_missing_backup
                : tab.to === "blocking"
                ? snapshot?.blocking.blocked_session_count
                : undefined;

            return (
              <NavLink
                key={tab.label}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 border-b-2 px-3 py-3 text-sm font-medium transition-colors",
                    isActive
                      ? "border-accent text-accent"
                      : "border-transparent text-text-secondary hover:text-text-primary"
                  )
                }
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
                {!!badgeCount && (
                  <span className="ml-0.5 rounded-full bg-severity-critical-bg px-1.5 py-0.5 text-[10px] font-semibold text-severity-critical">
                    {badgeCount}
                  </span>
                )}
              </NavLink>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto">
          <Outlet />
        </div>
      </div>
    </InstanceContextProvider>
  );
}
