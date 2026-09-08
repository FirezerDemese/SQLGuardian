"""
SQLGuardian - FastAPI Application
REST API over the monitoring engine.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from loguru import logger


from core.logger import setup_logging
from core.db_connection import initialize_from_settings, db_manager
from core.scheduler import start_scheduler, stop_scheduler
from api.routes import health, monitoring, instances, ai, runbooks, incidents


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("SQLGuardian API starting up...")
    initialize_from_settings()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    db_manager.dispose_all()
    logger.info("SQLGuardian API shut down cleanly.")


app = FastAPI(
    title="SQLGuardian",
    description="SQL Server Health Monitoring API - built by Firezer Demese",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten this in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])
app.include_router(instances.router, prefix="/instances", tags=["Instances"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])
app.include_router(runbooks.router, prefix="/runbooks", tags=["Runbooks"])
app.include_router(incidents.router, prefix="/incidents", tags=["Incident response"])

DASHBOARD_DIST = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")

@app.get("/dashboard", include_in_schema=False)
async def redirect_dashboard_root():
    return FileResponse(os.path.join(DASHBOARD_DIST, "index.html"))

@app.get("/dashboard/{full_path:path}", include_in_schema=False)
async def serve_dashboard(full_path: str):
    """Serve the Vite-built React dashboard with SPA fallback for client-side routing."""
    asset = os.path.join(DASHBOARD_DIST, full_path)
    if full_path and os.path.isfile(asset):
        return FileResponse(asset)
    index = os.path.join(DASHBOARD_DIST, "index.html")
    return FileResponse(index)

@app.get("/", tags=["Root"])
def root():
    return {
        "app": "SQLGuardian",
        "version": "1.0.0",
        "docs": "/docs",
    }
