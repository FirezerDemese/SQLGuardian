"""
SQLGuardian - Background Scheduler
Runs health checks on a timer and caches results in memory.
Future: push alerts to Slack/email when severity flips to critical.
"""

from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from core.monitor import get_full_snapshot, get_blocking, get_agent_jobs
from config.settings import settings


# ---------------------------------------------------------------------------
# In-memory cache - stores latest results from each check
# ---------------------------------------------------------------------------
_cache: dict = {
    "last_snapshot": None,
    "last_blocking": None,
    "last_jobs": None,
    "snapshot_count": 0,
    "last_error": None,
}


def get_cached_snapshot() -> Optional[dict]:
    return _cache["last_snapshot"]


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

        # TODO Phase 2: trigger alert if severity == "critical"

    except Exception as e:
        _cache["last_error"] = {"time": datetime.utcnow().isoformat(), "error": str(e)}
        logger.error(f"Scheduled snapshot failed: {e}")


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

    _scheduler.start()
    logger.info(
        f"Scheduler started | snapshot_interval={settings.health_check_interval_seconds}s"
    )

    # Run one immediately so the API has data right away
    _run_full_snapshot()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
