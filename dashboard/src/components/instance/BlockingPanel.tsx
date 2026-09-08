import type { BlockingSnapshot } from "../../types/api";

export function BlockingPanel({ blocking }: { blocking: BlockingSnapshot }) {
  const { blocked_sessions, head_blockers } = blocking;

  return (
    <div className="flex flex-col gap-8">
      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          Head Blockers ({head_blockers.length})
        </h3>
        {head_blockers.length === 0 ? (
          <p className="text-sm text-text-tertiary">No blocking detected.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border-subtle">
            <table className="w-full text-xs">
              <thead className="border-b border-border-subtle bg-surface-sunken text-text-tertiary">
                <tr>
                  {["SPID", "Login", "Host", "Program", "Status", "Wait Type", "Sessions Blocked", "Current SQL"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {head_blockers.map((b) => (
                  <tr key={b.session_id} className="border-b border-border-subtle last:border-0">
                    <td className="px-3 py-2 font-mono">{b.session_id}</td>
                    <td className="px-3 py-2">{b.login_name}</td>
                    <td className="px-3 py-2">{b.host_name}</td>
                    <td className="max-w-[120px] truncate px-3 py-2">{b.program_name}</td>
                    <td className="px-3 py-2">{b.status}</td>
                    <td className="px-3 py-2">{b.wait_type}</td>
                    <td className="px-3 py-2 text-center font-semibold text-severity-critical">
                      {b.sessions_blocked}
                    </td>
                    <td className="max-w-[200px] truncate px-3 py-2 font-mono text-text-tertiary">
                      {b.current_sql}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          Blocked Sessions ({blocked_sessions.length})
        </h3>
        {blocked_sessions.length === 0 ? (
          <p className="text-sm text-text-tertiary">No blocked sessions.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border-subtle">
            <table className="w-full text-xs">
              <thead className="border-b border-border-subtle bg-surface-sunken text-text-tertiary">
                <tr>
                  {["SPID", "Blocked by", "Wait Type", "Wait (s)", "DB", "Login", "Statement"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {blocked_sessions.map((s) => (
                  <tr key={s.session_id} className="border-b border-border-subtle last:border-0">
                    <td className="px-3 py-2 font-mono">{s.session_id}</td>
                    <td className="px-3 py-2 font-mono text-severity-critical">
                      {s.blocking_session_id}
                    </td>
                    <td className="px-3 py-2">{s.wait_type}</td>
                    <td className="px-3 py-2 font-semibold text-severity-critical">
                      {s.wait_seconds.toFixed(1)}
                    </td>
                    <td className="px-3 py-2">{s.database_name}</td>
                    <td className="px-3 py-2">{s.login_name}</td>
                    <td className="max-w-[200px] truncate px-3 py-2 font-mono text-text-tertiary">
                      {s.current_statement}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
