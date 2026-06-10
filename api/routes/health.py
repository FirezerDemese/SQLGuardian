"""
SQLGuardian - /health routes
Liveness, readiness, and current snapshot.
"""

from fastapi import APIRouter, HTTPException
from core.db_connection import db_manager
from core.scheduler import get_cached_snapshot, get_cache_info
from core.monitor import get_full_snapshot

router = APIRouter()


@router.get("/live")
def liveness():
    """Kubernetes-style liveness probe. Is the process alive?"""
    return {"status": "alive"}


@router.get("/ready")
def readiness():
    """Is the app ready to serve traffic? DB must be reachable."""
    result = db_manager.test_connection()
    if result["status"] != "connected":
        raise HTTPException(status_code=503, detail=result)
    return {"status": "ready", "db": result}


@router.get("/snapshot")
def snapshot(fresh: bool = False):
    """
    Return the latest health snapshot.
    Pass ?fresh=true to force a live query instead of using the cache.
    """
    if fresh:
        return get_full_snapshot()

    cached = get_cached_snapshot()
    if not cached:
        # No cached data yet - run live
        return get_full_snapshot()
    return cached


@router.get("/cache")
def cache_info():
    """Return scheduler cache metadata."""
    return get_cache_info()
