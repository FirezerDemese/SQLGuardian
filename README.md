<div align="center">

# 🛡️ SQLGuardian

### Ask the AI why your SQL Server is slow. Get a T-SQL fix back in seconds.

An AI-powered SQL Server health-monitoring platform that reads live DMV telemetry, explains incidents in plain English, and generates remediation T-SQL — grounded in real server data, never guessed.

[![Live Demo](https://img.shields.io/badge/▶_Live_Demo-7c3aed?style=for-the-badge)](https://firezerdemese.github.io/sqlguardian-demo/)
&nbsp;
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![SQL Server](https://img.shields.io/badge/SQL_Server_2022-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

</div>

---

## What it is

SQLGuardian polls a fleet of SQL Server instances every 60 seconds across **seven DMV-based health checks**, caches the telemetry, and puts an LLM in front of it that can:

- **Explain** the current health of an instance for two audiences at once — a technical DBA breakdown *and* a one-paragraph management summary, from the same snapshot.
- **Suggest** concrete remediation steps, each with ready-to-run T-SQL, a risk level, and an explicit *"approval required"* flag before anything destructive.
- **Answer** natural-language questions ("why is my server slow?", "are my backups current?") grounded in the live snapshot — with the supporting DMV data cited alongside the answer.

The AI reasons **only over real telemetry it is handed**. It names the head blocker, weighs the safe options, and explains the trade-offs before ever suggesting a `KILL`.

## Try it now (no SQL Server needed)

**▶ [Live interactive demo](https://firezerdemese.github.io/sqlguardian-demo/)** — a simulated 4-instance fleet with one live incident. Open the `primary` instance → **Blocking** to see an active blocking chain (head blocker SPID 62 starving four sessions on `Sales.OrderLines`), then open **AI Brain** to watch it get explained and remediated. Fully client-side; no backend behind the page.

## The seven checks

| Check | DMVs used |
|---|---|
| **CPU & memory** | `sys.dm_os_ring_buffers`, `sys.dm_os_sys_memory` |
| **Blocking chains** | `sys.dm_exec_requests`, `sys.dm_exec_sessions` |
| **Top wait stats** | `sys.dm_os_wait_stats` (delta + cumulative) |
| **Long-running queries** | `sys.dm_exec_requests` + `sys.dm_exec_sql_text` |
| **SQL Agent jobs** | `msdb.dbo.sysjobs`, `sysjobhistory`, `sysjobactivity` |
| **Disk / volume usage** | `sys.dm_os_volume_stats` |
| **Database status + backups** | `sys.databases`, `msdb.dbo.backupset` |

## Architecture

```
┌────────────────────┐     poll 60s      ┌──────────────────────┐
│  SQL Server fleet   │◄─────────────────│  Monitor (DMV queries)│
│  (N instances)      │   SQLAlchemy+pyodbc└──────────┬───────────┘
└────────────────────┘                              │ in-memory cache
                                                     ▼
┌────────────────────┐   REST/JSON      ┌──────────────────────┐
│  React 18 + Vite    │◄────────────────│  FastAPI API layer    │
│  dashboard (Tailwind│                  │  /health /monitoring  │
│  + Recharts)        │                  │  /ai/{explain,suggest,ask}
└────────────────────┘                  └──────────┬───────────┘
                                                     ▼ evidence-grounded prompt
                                          ┌──────────────────────┐
                                          │  Groq · Llama 3.3-70B │
                                          └──────────────────────┘
```

## Tech stack

- **Python 3.11** — core monitoring engine
- **FastAPI** — REST API layer, auto-generated OpenAPI docs
- **SQLAlchemy + pyodbc** — SQL Server connectivity with pooling & retry
- **APScheduler** — background polling + in-memory snapshot cache
- **React 18 + TypeScript + Vite** — dashboard (Tailwind CSS, Recharts, TanStack Query, Radix UI)
- **Groq** · `llama-3.3-70b-versatile` — the AI reasoning layer
- **Docker Compose** — one-command local environment incl. SQL Server 2022 Developer Edition

## Quick start (local, real SQL Server)

```bash
git clone https://github.com/Firezerdemese/sqlguardian.git
cd sqlguardian
./dev_start.sh
```

Then visit:
- **Dashboard** — http://localhost:8000/dashboard/
- **API** — http://localhost:8000
- **Swagger docs** — http://localhost:8000/docs

<details>
<summary><b>Frontend hot-reload for dashboard development</b></summary>

```bash
docker compose up -d sqlserver sqlguardian-api      # backend
cd dashboard && npm install && npm run dev          # Vite dev server on :5173
```

</details>

## Key API endpoints

| Endpoint | Description |
|---|---|
| `GET /health/snapshot` | Full cached health snapshot (add `?fresh=true` to force a live query) |
| `GET /monitoring/blocking` | Active blocking chains with head-blocker session IDs and locked SQL |
| `GET /monitoring/waits` | Top wait types (delta or cumulative) |
| `GET /monitoring/jobs` | SQL Agent job status |
| `GET /monitoring/databases` | Database status + backup health |
| `POST /ai/explain` | Dual-audience health explanation |
| `POST /ai/suggest` | Remediation steps with risk-rated T-SQL |
| `POST /ai/ask` | Natural-language Q&A grounded in the live snapshot |
| `GET /instances/` · `POST /instances/register` | Manage the monitored fleet |

## Building the static demo

The dashboard ships a demo mode that runs entirely on fixtures — no backend required — used for the hosted live demo above:

```bash
cd dashboard
VITE_DEMO=true VITE_BASE=/sqlguardian-demo/ npm run build   # → dist/ (static, deployable to any host)
```

## Roadmap

- [x] Core monitoring engine + REST API + Docker
- [x] React dashboard (fleet view, AI Brain, blocking/waits/jobs/databases)
- [x] Static demo mode for zero-backend hosting
- [ ] Azure wire-up (Azure SQL, Managed Instance)
- [ ] Alerting (Slack / email on severity flip)
- [ ] Historical trending (time-series storage)

---

<div align="center">

**Built by [Firezer Demese](https://firezerdemese.github.io)** — Senior SQL Server DBA · Data & AI Tooling Engineer

</div>
