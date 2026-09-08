import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { IS_DEMO } from "../../api/endpoints";

export function AppShell() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-surface-canvas">
      {IS_DEMO && (
        <div className="flex items-center justify-center gap-2 border-b border-violet-200 bg-violet-50 px-4 py-1.5 text-xs text-violet-700">
          <span className="font-semibold uppercase tracking-wide">Live demo</span>
          <span>
            — simulated 4-instance fleet, no real SQL Server behind this page.
            Explore freely: blocking chain on{" "}
            <span className="font-medium">primary</span>, AI Brain included.
          </span>
          <a
            href="https://github.com/Firezerdemese/sqlguardian"
            target="_blank"
            rel="noopener"
            className="font-semibold underline underline-offset-2 hover:text-violet-900"
          >
            View source
          </a>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
