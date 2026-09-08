# SQLGuardian

**Runbook automation for SQL Server.** Every monitoring tool tells you something is
wrong. None of them encode how *your* team fixes it — that lives in a Confluence
page nobody opens at 3am, or in the head of the one senior who always gets called.

SQLGuardian ingests those procedures, maps each section to the conditions it
covers, and when a condition fires it hands back your team's documented steps,
cited to the document and section they came from — ordered by blast radius, with
the destructive options last. When your runbooks do not cover a condition, it says
so, and keeps a record of every time that has happened.

Detection is the cheap input here. The product is the distance between an alert
firing and a junior engineer knowing what this team does about it.

---

## What it does

**Ingests the runbooks you already have.** Markdown, plain text, HTML or Confluence
export, PDF, and Word (.docx). Chunked by heading, so a retrieved step arrives with
its surrounding procedure rather than orphaned. Every chunk stores its source
document, heading path, and a stable anchor.

**Retrieves by condition, not by similarity.** Each of seven checks emits a
structured condition code. Only sections mapped to that code are eligible, so the
disaster-recovery runbook cannot answer a blocking incident. A section is mapped
either because the document declares it (`Conditions: BLOCKING_CHAIN`) or because a
keyword rule matched — and the rule that matched is recorded and shown in the UI.
There is no embedding model and no vector store: retrieval gives the same answer at
3am during an outage that it gave in testing.

**Orders the response by blast radius.** Candidate actions are structured data —
what it does, expected effect, blast radius, reversible yes/no, how to undo,
approval required, source. The ordering is a deterministic function of that
metadata. Destructive actions are last, always, and carry a rollback. Each
condition also carries what *not* to do yet, and why.

**Reports the gaps.** When a condition fires and no team procedure covers it, that
is recorded. The resulting report — "these conditions fired N times in the last 90
days and your runbooks do not cover them" — is the list worth writing next.

**Drafts the write-up.** One `IncidentEvidence` object renders two documents: a
technical write-up with session ids and values, and one paragraph in business
language with none. Same source, so they cannot disagree. Every number the model
writes is bound to what it quantifies and checked against the evidence: "4
sessions" is checked against session counts, not against every number in the
record, so `1 session was blocked` is caught even though 1 is in the evidence as
a job count.

## The safety boundary

The model narrates. It does not decide anything, and that is enforced rather than
asserted:

| Claim | Where it is enforced | Test |
|---|---|---|
| The LLM cannot change a check verdict | Verdicts are computed in `core/conditions.py` before narration; reports read severity from the evidence | `test_a_narrator_claiming_everything_is_fine_cannot_change_the_status` |
| The evidence is read-only at the narration boundary | `IncidentEvidence` is a frozen dataclass with tuple fields — a runtime error *and* a mypy error | `test_evidence_cannot_be_mutated`, `test_mutating_evidence_is_a_static_type_error` |
| Generated prose cannot invent or misattribute numbers | Each number is bound to what it quantifies and checked against the evidence values of that same kind, so a number that exists in the evidence as something else does not license the claim; violations are reported on the page, not hidden | `test_numbers_in_the_narration_must_appear_in_the_evidence`, `test_a_number_that_exists_as_something_else_does_not_license_the_claim` |
| The business summary carries no session ids | A leaking summary is discarded and the deterministic one renders instead | `test_a_leaking_business_summary_is_not_used` |
| The monitoring connection never writes | `assert_read_only()` runs on every query before a connection is opened | `test_writes_are_refused`, run against every query in `core/monitor.py` |
| A failed check is never reported as healthy | Failed sections are excluded from the rollup and reported separately; severity becomes `unknown` | `test_a_snapshot_where_every_check_failed_is_not_healthy` |

If the model is unreachable — or its id gets retired — the reports still render,
with the deterministic summary in place of the prose and the failure stated on the
page. Findings are unaffected.

## The seven conditions

| Condition | Fires on | Source |
|---|---|---|
| `BLOCKING_CHAIN` | Sessions blocked past the wait threshold | `sys.dm_exec_requests`, `sys.dm_exec_sessions` |
| `LOG_GROWTH` | Log percent-used past threshold, **or** `log_reuse_wait_desc` blocking truncation at any percentage | `sys.dm_os_performance_counters`, `sys.databases` |
| `DISK_PRESSURE` | Any volume past the usage threshold | `sys.dm_os_volume_stats` |
| `BACKUP_AGE_EXCEEDED` | A database outside its full-backup window | `msdb.dbo.backupset` |
| `AGENT_JOB_FAILURE` | A job whose last run finished with `run_status = 0` | `msdb.dbo.sysjobhistory` |
| `WAIT_SPIKE` | One actionable wait type dominating a sampling window | `sys.dm_os_wait_stats` (delta mode only) |
| `LONG_RUNNING_REQUEST` | A request past the elapsed threshold that is **not** blocked | `sys.dm_exec_requests` |

Two deliberate exclusions, because triaging one incident twice is worse than a
missed row: a blocked request is not also counted as a long-running query, and a
`LCK_` wait spike is suppressed when a blocking chain is already firing — it is the
same event measured differently.

Conditions are ranked by **blast radius**, not severity. A database 31 hours outside
its backup window is only a "warning" by threshold, and it still outranks a
"critical" failed Agent job: one means you cannot restore, the other means a job
needs re-running.

## Permissions

The monitoring account needs exactly this, and no more. **sysadmin is not
required and should not be granted.** This exact script was run against SQL
Server 2022, and all thirteen monitoring queries were then executed as that
login with `IS_SRVROLEMEMBER('sysadmin') = 0`.

```sql
CREATE LOGIN sqlguardian WITH PASSWORD = '<...>';
GRANT VIEW SERVER STATE   TO sqlguardian;   -- the sys.dm_* views
GRANT VIEW ANY DEFINITION TO sqlguardian;   -- object names behind sql_handle
GRANT VIEW ANY DATABASE   TO sqlguardian;   -- database list and backup history

USE msdb;
CREATE USER sqlguardian FOR LOGIN sqlguardian;
ALTER ROLE SQLAgentReaderRole ADD MEMBER sqlguardian;

-- SQLAgentReaderRole alone is not enough: it does not carry SELECT on the
-- job tables themselves, so the Agent checks fail with "SELECT permission was
-- denied on the object 'sysjobs'" without these three.
GRANT SELECT ON dbo.sysjobs        TO sqlguardian;
GRANT SELECT ON dbo.sysjobhistory  TO sqlguardian;
GRANT SELECT ON dbo.sysjobactivity TO sqlguardian;
```

No `EXECUTE` grant is needed anywhere. The Agent query converts `run_date` and
`run_time` inline rather than calling `msdb.dbo.agent_datetime`, which would
require an `EXECUTE` grant on an msdb internal helper purely to format a date.

Remediation T-SQL is shown for a DBA to run themselves, under their own
credentials. SQLGuardian will not execute it: every generated script — including
every `KILL` — is refused by the read-only guard if anything tries to route it
through the monitoring connection.

## Worked example

Reproduce all of this with no SQL Server:

```bash
python scripts/worked_example.py            # deterministic parts only
python scripts/worked_example.py --narrate  # also calls the model
```

**1. A condition fires.** `BLOCKING_CHAIN`, critical, blast radius 86:

```
- 4 session(s) blocked, longest wait 412s (sys.dm_exec_requests.blocking_session_id > 0).
- Head blocker is session 62, login APP\svc_ordersync, program OrderSync.
- Statement holding the lock: UPDATE Sales.OrderLines SET PickedQty = PickedQty - 1
  WHERE OrderLineID BETWEEN 900000 AND 940000
- Session 71 waiting 412s on LCK_M_S in WideWorldImporters.
```

**2. The team's procedure is retrieved, with a citation:**

```
Citation     : dba blocking and long queries - Platform DBA Runbook - Contention >
               Blocking chain on a production OLTP instance
               (dba-blocking-and-long-queries.md#platform-dba-runbook-contention-
               blocking-chain-on-a-production-oltp-instance, lines 7-26)
Why this one : document declares this condition explicitly; body matches "ordersync"
```

**3. Actions, ordered by blast radius:**

```
 1. [read_only] [runbook] Step 1: Confirm the head blocker is still live and still running...
 2. [read_only] [runbook] Step 2: Record the head blocker session id, login, host, program...
 3. [read_only] [runbook] Step 3: If program_name is OrderSync or WMS-Bridge, page the
                          Fulfilment on-call before doing anything else...
 ...
 7. [read_only] [generic] Identify who owns session 62
10. [session  ] [runbook] Step 6: Kill the head blocker only with duty manager approval...
                          ! approval required, DESTRUCTIVE, irreversible
11. [session  ] [generic] Kill session 62
                          ! approval required, DESTRUCTIVE, irreversible
```

Step 4 of that runbook reads *"Do not kill it while they are still investigating"* —
it stays classified read-only. A verb inside a prohibition is not an instruction to
perform it.

**Not yet**, shown alongside:

> Do not KILL the head blocker before identifying who owns it. A rollback of a large
> open transaction can hold the same locks for longer than the original block.

**4. The write-up drafts from the evidence** — technical and business, both from one
object. Every number in the narration is verified against the evidence before it is
shown.

## Quick start

```bash
git clone https://github.com/Firezerdemese/sqlguardian.git
cd sqlguardian
cp .env.example .env          # set GROQ_API_KEY; GROQ_MODEL has a working default
./dev_start.sh                # SQL Server 2022 Developer + API + dashboard
```

- Dashboard — http://localhost:8000/dashboard/
- Swagger — http://localhost:8000/docs
- Is the model id still valid? — http://localhost:8000/health/llm

Load the sample corpus in `docs/runbook-samples/` — one document per supported
format — to see the flow end to end:

```bash
for f in docs/runbook-samples/*; do
  curl -X POST http://localhost:8000/runbooks/upload -F "file=@$f"
done
```

Tests:

```bash
pip install -r requirements-dev.txt && pytest
```

### Static demo build

The dashboard has a demo mode backed by fixtures, so it runs as a static site with
no backend and no SQL Server. It ships a pre-loaded runbook corpus; upload and
delete are disabled there and say so, because ingestion needs somewhere to write.

```bash
cd dashboard
VITE_DEMO=true VITE_BASE=/sqlguardian-demo/ npm run build   # -> dist/
```

Build this from PowerShell or with `MSYS_NO_PATHCONV=1`. Git Bash rewrites a
value beginning with `/` into a Windows path, so `VITE_BASE` becomes
`/Program Files/Git/sqlguardian-demo/`, every asset URL in `index.html` carries
that prefix, and the deployed page loads nothing and renders blank.

Live: [firezerdemese.github.io/sqlguardian-demo](https://firezerdemese.github.io/sqlguardian-demo/)

- [Runbooks](https://firezerdemese.github.io/sqlguardian-demo/#/runbooks) - corpus, condition coverage, gap report
- [Response](https://firezerdemese.github.io/sqlguardian-demo/#/instance/primary/response) - conditions, citations, ordered actions
- [Write-up](https://firezerdemese.github.io/sqlguardian-demo/#/instance/primary/report) - both documents from one evidence object

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /incidents/conditions` | Conditions ranked by blast radius, each with its retrieved procedure, citations, ordered actions, and hold-off guidance |
| `POST /incidents/report` | Both incident documents, drafted from one evidence object |
| `GET /incidents/evidence` | The raw evidence object the reports are built from |
| `POST /runbooks/upload` | Ingest a runbook (md / txt / html / pdf / docx) |
| `GET /runbooks/` | Corpus, with which conditions are and are not covered |
| `GET /runbooks/sections?condition=` | Sections scoped to one condition, with mapping reasons |
| `GET /runbooks/gaps?days=90` | The runbook gap report |
| `GET /health/snapshot` · `/health/llm` | Cached snapshot; narration model reachability |
| `GET /monitoring/{server,blocking,waits,jobs,disk,databases}` | Individual checks |
| `POST /ai/{explain,suggest,ask}` | The earlier free-form AI panel (see below) |

## What it does not do

- **It does not execute remediation.** No approval workflow, no write path, no
  agent that acts. Scripts are shown for a human to run.
- **It does not OCR.** A scanned, image-only PDF is refused rather than ingested
  empty.
- **It does not do semantic retrieval.** Mapping is explicit annotation or keyword
  rules. That is a deliberate trade — auditable and stable, at the cost of missing
  a section written in vocabulary the rules do not know. Unmapped sections are
  reported on upload rather than silently ignored.
- **It does not alert.** No Slack, no email, no paging. Conditions are recorded and
  served over the API.
- **It does not store history.** Snapshots are an in-memory cache. Only condition
  firings are persisted, for the gap report.
- **It is single-tenant and unauthenticated.** No login, no RBAC, CORS wide open.
  Not deployable to a shared network as-is.
- **It has no Azure SQL support.** Several checks read `msdb` and
  `sys.dm_os_volume_stats`, which Azure SQL Database does not expose.
- **Volume names are unavailable on Linux.** `sys.dm_os_volume_stats` returns
  NULL for the mount point on SQL Server for Linux, so volumes are labelled by
  the directory holding their data files (`/var/opt/mssql/data`) and the
  disk-usage script lists every volume instead of filtering to one.

## Verified against a live instance

The monitoring engine has been run against SQL Server 2022 in the Compose stack,
not only against fixtures:

- all thirteen DMV queries execute, as a non-sysadmin account with the grants above
- every generated read-only diagnostic script executes without error
- a real blocking chain (an idle transaction plus three lock waiters) is detected
  end to end: the head of the chain, the statement it last ran, the intermediate
  blocker, the retrieved runbook section and the ordered actions

## Architecture

```
SQL Server fleet --poll 60s--> monitor.py (13 read-only DMV queries)
                                    |
                                    v
                             conditions.py ---- deterministic verdicts,
                                    |           ranked by blast radius
                     +--------------+--------------+
                     v              v              v
              runbooks.py      actions.py     gap_report.py
           condition-scoped   ordered by      what fired with
             retrieval +      blast radius,   no procedure
              citations       destructive last
                     +--------------+--------------+
                                    v
                              incident.py  --> frozen IncidentEvidence
                                    |
                     +--------------+--------------+
                     v                             v
               narrator.py                     reports.py
          (prose only; numbers           technical write-up +
           verified against the          business paragraph,
           evidence; cannot alter        both from the evidence
           a verdict)
```

- **Python 3.11 / FastAPI** — API and monitoring engine
- **SQLAlchemy + pyodbc** — pooling, retry, and a per-instance circuit breaker so
  an unreachable instance cannot hang a request
- **APScheduler** — background polling and condition-firing records
- **React 18 + TypeScript + Vite** — dashboard (Tailwind, Recharts, TanStack Query)
- **Groq** · `openai/gpt-oss-120b` — narration only, model id read from `GROQ_MODEL`
- **pypdf, python-docx** — runbook ingestion

## The AI panel

The `/ai/*` endpoints and the dashboard's "AI Brain" tab predate the runbook work.
They send the snapshot to the model and let it write freely: an explanation, a set
of suggested scripts, or an answer to a typed question. They are useful for
exploration and they are **not** subject to the safety boundary above — that
output is not verified against an evidence object. The Response and Write-up tabs
are the ones with the guarantees.

## Roadmap

- [x] Runbook ingestion; condition-scoped retrieval with citations
- [x] Ordered actions with risk semantics and rollbacks
- [x] Runbook gap report
- [x] Incident evidence object, dual-audience reports, verified narration
- [x] Read-only enforcement and permission scoping
- [ ] Approval workflow with an execution path and an audit trail
- [ ] Historical trending (time-series storage)
- [ ] Alerting on condition firing

---

Built by [Firezer Demese](https://firezerdemese.github.io) — Senior SQL Server DBA
