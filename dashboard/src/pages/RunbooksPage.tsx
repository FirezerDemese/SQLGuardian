import { useRef, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  CircleSlash,
  FileText,
  Trash2,
  Upload,
} from "lucide-react";
import {
  useDeleteRunbook,
  useRunbookGaps,
  useRunbooks,
  useUploadRunbook,
} from "../hooks/useRunbooks";
import { Card } from "../components/primitives/Card";
import { EmptyState } from "../components/primitives/EmptyState";
import { Skeleton } from "../components/primitives/Skeleton";
import { IS_DEMO } from "../api/endpoints";

const ALL_CONDITIONS = [
  "BLOCKING_CHAIN",
  "AGENT_JOB_FAILURE",
  "BACKUP_AGE_EXCEEDED",
  "LOG_GROWTH",
  "DISK_PRESSURE",
  "WAIT_SPIKE",
  "LONG_RUNNING_REQUEST",
] as const;

export function RunbooksPage() {
  const { data, isLoading } = useRunbooks();
  const gaps = useRunbookGaps(90);
  const upload = useUploadRunbook();
  const remove = useDeleteRunbook();
  const fileInput = useRef<HTMLInputElement>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const covered = new Set(data?.conditions_covered ?? []);

  async function onFiles(files: FileList | null) {
    if (!files) return;
    setLastError(null);
    for (const file of Array.from(files)) {
      try {
        await upload.mutateAsync(file);
      } catch (error) {
        setLastError(error instanceof Error ? error.message : String(error));
      }
    }
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <header>
        <h1 className="text-lg font-semibold text-text-primary">Runbooks</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          The procedures your team already has. SQLGuardian chunks them by heading, maps each
          section to the conditions it covers, and cites the document and section every time it
          shows you a step. A step with no citation is not shown as yours.
        </p>
      </header>

      {/* Coverage ---------------------------------------------------------- */}
      <Card>
        <h2 className="text-sm font-semibold text-text-primary">Condition coverage</h2>
        <p className="mt-1 text-sm text-text-secondary">
          {data?.document_count ?? 0} document(s), {data?.section_count ?? 0} section(s) in the
          corpus.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {ALL_CONDITIONS.map((code) => {
            const isCovered = covered.has(code);
            return (
              <span
                key={code}
                className={
                  isCovered
                    ? "inline-flex items-center gap-1.5 rounded-md border border-severity-healthy-border bg-severity-healthy-bg px-2 py-1 font-mono text-xs font-semibold text-severity-healthy"
                    : "inline-flex items-center gap-1.5 rounded-md border border-severity-warning-border bg-severity-warning-bg px-2 py-1 font-mono text-xs font-semibold text-severity-warning"
                }
              >
                {isCovered ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <CircleSlash className="h-3.5 w-3.5" />
                )}
                {code}
              </span>
            );
          })}
        </div>
      </Card>

      {/* Upload ------------------------------------------------------------ */}
      <Card>
        <h2 className="text-sm font-semibold text-text-primary">Add a runbook</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Markdown, plain text, HTML or Confluence export, PDF, or Word (.docx). Re-uploading the
          same filename replaces the previous version.
        </p>

        <div className="mt-3 flex items-center gap-3">
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".md,.markdown,.txt,.html,.htm,.pdf,.docx"
            className="hidden"
            onChange={(event) => onFiles(event.target.files)}
          />
          <button
            onClick={() => fileInput.current?.click()}
            disabled={upload.isPending || IS_DEMO}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {upload.isPending ? "Ingesting..." : "Choose files"}
          </button>
          {IS_DEMO && (
            <span className="text-xs text-text-tertiary">
              Upload is disabled in the static demo — the corpus below is pre-loaded.
            </span>
          )}
        </div>

        {upload.isSuccess && !upload.isPending && (
          <p className="mt-3 rounded-lg border border-severity-healthy-border bg-severity-healthy-bg p-3 text-sm text-text-secondary">
            Ingested <span className="font-medium">{upload.data.title}</span>:{" "}
            {upload.data.mapped_section_count} of {upload.data.section_count} sections mapped to a
            condition.
            {upload.data.note && <> {upload.data.note}</>}
          </p>
        )}
        {lastError && (
          <p className="mt-3 rounded-lg border border-severity-critical-border bg-severity-critical-bg p-3 text-sm text-text-secondary">
            {lastError}
          </p>
        )}
      </Card>

      {/* Corpus ------------------------------------------------------------ */}
      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : data && data.documents.length > 0 ? (
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-text-primary">Corpus</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-text-tertiary">
                <tr>
                  <th className="pb-2 pr-4 font-semibold">Document</th>
                  <th className="pb-2 pr-4 font-semibold">Format</th>
                  <th className="pb-2 pr-4 font-semibold">Sections</th>
                  <th className="pb-2 pr-4 font-semibold">Conditions covered</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {data.documents.map((document) => (
                  <tr key={document.doc_id} className="border-t border-border-subtle">
                    <td className="py-2 pr-4">
                      <span className="flex items-center gap-2 text-text-primary">
                        <FileText className="h-4 w-4 text-text-tertiary" />
                        {document.title}
                      </span>
                      <span className="ml-6 font-mono text-xs text-text-tertiary">
                        {document.filename}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-text-secondary">{document.format}</td>
                    <td className="py-2 pr-4 text-text-secondary">
                      {document.mapped_section_count} mapped / {document.section_count}
                    </td>
                    <td className="py-2 pr-4">
                      <span className="flex flex-wrap gap-1">
                        {document.conditions_covered.length === 0 ? (
                          <span className="text-xs text-text-tertiary">none</span>
                        ) : (
                          document.conditions_covered.map((code) => (
                            <span
                              key={code}
                              className="rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-[10px] text-text-secondary"
                            >
                              {code}
                            </span>
                          ))
                        )}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => remove.mutate(document.doc_id)}
                        disabled={IS_DEMO}
                        className="rounded p-1 text-text-tertiary transition-colors hover:text-severity-critical disabled:opacity-30"
                        aria-label={`Remove ${document.title}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState
          icon={BookOpen}
          title="No runbooks ingested"
          description="Every condition that fires will be answered with generic guidance until you add one."
        />
      )}

      {/* Gap report -------------------------------------------------------- */}
      <Card>
        <h2 className="text-sm font-semibold text-text-primary">Runbook gap report</h2>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Conditions that have actually fired on this fleet with no documented procedure behind
          them. This is the list worth writing next.
        </p>

        {gaps.isLoading ? (
          <Skeleton className="mt-4 h-24 w-full" />
        ) : gaps.data ? (
          <>
            <p className="mt-3 rounded-lg border border-border-subtle bg-surface-sunken p-3 text-sm text-text-primary">
              {gaps.data.headline}
            </p>

            {gaps.data.uncovered_firings.length > 0 && (
              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                  Fired with no procedure — last {gaps.data.window_days} days
                </h3>
                <ul className="mt-2 flex flex-col gap-1.5">
                  {gaps.data.uncovered_firings.map((item) => (
                    <li key={item.condition} className="flex items-baseline gap-2 text-sm">
                      <span className="font-mono text-xs font-semibold text-severity-warning">
                        {item.condition}
                      </span>
                      <span className="text-text-secondary">
                        fired {item.firings} time{item.firings === 1 ? "" : "s"}
                        {item.last_seen && `, last ${new Date(item.last_seen).toLocaleString()}`}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {gaps.data.never_fired_gaps.length > 0 && (
              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                  No procedure, has not fired yet
                </h3>
                <p className="mt-1 text-sm text-text-secondary">
                  Cheaper to write today than at 3am:{" "}
                  <span className="font-mono text-xs">
                    {gaps.data.never_fired_gaps.join(", ")}
                  </span>
                </p>
              </div>
            )}

            {gaps.data.covered_firings.length > 0 && (
              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                  Answered from your runbooks
                </h3>
                <ul className="mt-2 flex flex-col gap-1.5">
                  {gaps.data.covered_firings.map((item) => (
                    <li key={item.condition} className="text-sm">
                      <span className="font-mono text-xs font-semibold text-severity-healthy">
                        {item.condition}
                      </span>{" "}
                      <span className="text-text-secondary">
                        answered {item.firings} time{item.firings === 1 ? "" : "s"}
                      </span>
                      {item.citations[0] && (
                        <p className="ml-1 font-mono text-[11px] text-text-tertiary">
                          {item.citations[0]}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : null}
      </Card>
    </div>
  );
}
