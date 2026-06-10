"""
SQLGuardian - /monitoring routes
Individual check endpoints. Each one can target a specific instance.
"""

from fastapi import APIRouter, Query
from typing import Optional

from core.monitor import (
    get_server_health,
    get_blocking,
    get_wait_stats,
    get_long_running_queries,
    get_agent_jobs,
    get_disk_usage,
    get_database_status,
)

router = APIRouter()


@router.get("/server")
def server_health(instance: Optional[str] = Query(None, description="Instance name (default: primary)")):
    """CPU, memory, and uptime."""
    return get_server_health(instance)


@router.get("/blocking")
def blocking(instance: Optional[str] = Query(None)):
    """Active blocking chains and head blockers."""
    return get_blocking(instance)


@router.get("/waits")
def wait_stats(instance: Optional[str] = Query(None)):
    """Top 15 wait types (benign background waits excluded)."""
    return get_wait_stats(instance)


@router.get("/queries/long-running")
def long_running(
    min_seconds: int = Query(30, description="Min elapsed seconds"),
    instance: Optional[str] = Query(None),
):
    """Currently running queries exceeding the threshold."""
    return get_long_running_queries(min_seconds, instance)


@router.get("/jobs")
def agent_jobs(instance: Optional[str] = Query(None)):
    """SQL Agent job status - last run, failures, currently running."""
    return get_agent_jobs(instance)


@router.get("/disk")
def disk_usage(instance: Optional[str] = Query(None)):
    """Volume-level disk usage for all drives hosting SQL Server files."""
    return get_disk_usage(instance)


@router.get("/databases")
def database_status(instance: Optional[str] = Query(None)):
    """Database states, sizes, backup health."""
    return get_database_status(instance)
