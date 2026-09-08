"""
SQLGuardian - Background Scheduler
Runs health checks on a timer and caches results in memory.
Future: push alerts to Slack/email when severity flips to critical.
"""

from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from core.monitor import get_full_snapshot, get_blocking
from core.conditions import detect_conditions
from core.gap_report import record_firings
from config.settings import settings


# ---------------------------------------------------------------------------
# In-memory cache - stores latest results from each check
# ---------------------------------------------------------------------------
_cache: dict = {
    "last_snapshot": None,
    "last_blocking": None,
    "last_jobs": None,
    "last_conditions": (),
    "snapshot_count": 0,
    "last_error": None,
}

# Firings are logged once per condition per continuous episode, not once per
# poll. A blocking chain lasting an hour is one entry in the gap report, not
# sixty - otherwise the report measures polling frequency instead of pain.
_open_conditions: set = set()


def get_cached_snapshot() -> Optional[dict]:
    return _cache["last_snapshot"]


def get_cached_conditions() -> tuple:
    return _cache["last_conditions"]


def get_cache_info() -> dict:
    return {
        "snapshot_count": _cache["snapshot_count"],
        "last_snapshot_time": _cache["last_snapshot"]["snapshot_time"] if _cache["last_snapshot"] else None,
        "last_error": _cache["last_error"],
    }


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _run_full_snapshot():
    """Scheduled job: run all checks and update cache."""
    try:
        snapshot = get_full_snapshot()
        _cache["last_snapshot"] = snapshot
        _cache["snapshot_count"] += 1
        _cache["last_error"] = None

        severity = snapshot.get("overall_severity", "unknown")
        logger.info(f"Scheduled snapshot #{_cache['snapshot_count']} complete | severity={severity}")

        conditions = detect_conditions(snapshot)
        _cache["last_conditions"] = conditions
        _record_new_firings(conditions, snapshot.get("instance", "primary"))

        # TODO Phase 2: trigger alert if severity == "critical"

    except Exception as e:
        _cache["last_error"] = {"time": datetime.utcnow().isoformat(), "error": str(e)}
        logger.error(f"Scheduled snapshot failed: {e}")


def _record_new_firings(conditions, instance: str) -> None:
    """Log a firing the first time a condition appears, and again only if it clears.

    Keeps the runbook gap report a count of incidents rather than a count of
    polls.
    """
    global _open_conditions
    current = {c.code.value for c in conditions}
    newly_fired = [c for c in conditions if c.code.value not in _open_conditions]
    if newly_fired:
        try:
            record_firings(newly_fired, instance=instance)
        except Exception as e:
            logger.error(f"Could not record condition firings: {e}")
    _open_conditions = current


def _run_blocking_check():
    """Frequent blocking check between full snapshots."""
    try:
        result = get_blocking()
        _cache["last_blocking"] = result
        if result.get("severity") in ("warning", "critical"):
            logger.warning(
                f"Blocking detected: {result['blocked_session_count']} sessions, "
                f"max wait {result['max_wait_seconds']}s"
            )
    except Exception as e:
        logger.error(f"Blocking check failed: {e}")


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.warning("Scheduler already running.")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Full snapshot every N seconds (default 60)
    _scheduler.add_job(
        _run_full_snapshot,
        trigger=IntervalTrigger(seconds=settings.health_check_interval_seconds),
        id="full_snapshot",
        name="Full Health Snapshot",
        replace_existing=True,
        max_instances=1,  # Don't stack if previous run is still going
    )

    # Blocking check twice as often
    _scheduler.add_job(
        _run_blocking_check,
        trigger=IntervalTrigger(seconds=max(15, settings.health_check_interval_seconds // 4)),
        id="blocking_check",
        name="Blocking Chain Check",
        replace_existing=True,
        max_instances=1,
    )

    # Run one immediately so the API has data right away - but on a scheduler
    # thread, not inline. Called inline, an unreachable SQL Server blocks
    # startup for as long as every DMV query takes to exhaust its retries, and
    # takes the whole API down with it: the runbook corpus, the gap report and
    # the dashboard do not need a database to be useful.
    _scheduler.add_job(
        _run_full_snapshot,
        trigger="date",
        run_date=datetime.now(timezone.utc),
        id="initial_snapshot",
        name="Initial Health Snapshot",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started | snapshot_interval={settings.health_check_interval_seconds}s"
    )


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
