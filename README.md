# SQLGuardian

SQL Server health monitoring engine with REST API and Streamlit dashboard.
Built by Firezer Demese - Senior SQL Server DBA.

## What it monitors

| Check | DMV Used |
|---|---|
| CPU & Memory | `sys.dm_os_ring_buffers`, `sys.dm_os_sys_memory` |
| Blocking chains | `sys.dm_exec_requests`, `sys.dm_exec_sessions` |
| Top wait stats | `sys.dm_os_wait_stats` |
| Long-running queries | `sys.dm_exec_requests` + `sys.dm_exec_sql_text` |
| SQL Agent jobs | `msdb.dbo.sysjobs`, `sysjobhistory`, `sysjobactivity` |
| Disk / volume usage | `sys.dm_os_volume_stats` |
| Database status + backups | `sys.databases`, `msdb.dbo.backupset` |

## Stack

- **Python 3.11** - core engine
- **FastAPI** - REST API layer
- **SQLAlchemy + pyodbc** - SQL Server connectivity
- **APScheduler** - background polling
- **Streamlit** - dashboard
- **Docker Compose** - local dev environment (SQL Server 2022 Developer Edition)

## Quick start

```bash
# Clone and start everything
git clone <repo>
cd sqlguardian
./dev_start.sh
```

That's it. Visit:
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health/snapshot` | Full cached health snapshot |
| `GET /health/snapshot?fresh=true` | Force live query |
| `GET /monitoring/server` | CPU, memory, uptime |
| `GET /monitoring/blocking` | Active blocking chains |
| `GET /monitoring/waits` | Top wait types |
| `GET /monitoring/queries/long-running` | Queries over 30s |
| `GET /monitoring/jobs` | SQL Agent job status |
| `GET /monitoring/disk` | Volume disk usage |
| `GET /monitoring/databases` | Database status + backup health |
| `POST /instances/register` | Add a new instance to monitor |

## Project structure

```
sqlguardian/
- core/
  - db_connection.py    # Connection manager, pooling, retry
  - monitor.py          # All DMV queries - the brain
  - scheduler.py        # Background polling + in-memory cache
  - logger.py           # Loguru setup
- api/
  - main.py             # FastAPI app, startup/shutdown
  - routes/
    - health.py         # /health endpoints
    - monitoring.py     # /monitoring endpoints
    - instances.py      # /instances endpoints
- dashboard/
  - app.py              # Streamlit dashboard (Phase 2)
- config/
  - settings.py         # Pydantic settings from env vars
- scripts/
  - seed_dev.sql        # Dev SQL Server seed data
- docker/
  - Dockerfile.api
  - Dockerfile.dashboard
- docker-compose.yml
- dev_start.sh          # One-command bootstrap
```

## Environment variables

See `.env.example` for all available settings.
Key ones:

```
SQL_SERVER_HOST=localhost
SQL_SERVER_PASSWORD=your_password
CPU_CRITICAL_PCT=90
BLOCKING_CRITICAL_SECONDS=120
HEALTH_CHECK_INTERVAL_SECONDS=60
```

## Roadmap

- [x] Phase 1 - Core monitoring engine + REST API + Docker
- [ ] Phase 2 - Streamlit dashboard
- [ ] Phase 3 - Azure wire-up (Azure SQL, Managed Instance)
- [ ] Phase 4 - Alerting (Slack / email on severity flip)
- [ ] Phase 5 - Historical trending (time series storage)
