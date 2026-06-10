"""
SQLGuardian - Database Connection Manager
Handles SQL Server connections with retry logic, pooling, and health checks.
"""

import pyodbc
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from typing import Optional, Generator
from contextlib import contextmanager

from config.settings import settings


def build_connection_string(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> str:
    """Build a raw pyodbc connection string for SQL Server."""
    return (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
        f"Connection Timeout=30;"
    )


class DatabaseConnectionManager:
    """
    Manages SQL Server connections for SQLGuardian.
    Supports multiple monitored instances, connection pooling, and auto-retry.
    """

    def __init__(self):
        self._engines: dict[str, object] = {}
        self._instance_configs: dict[str, dict] = {}
        self._default_instance: Optional[str] = None

    def register_instance(
        self,
        name: str,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str = "master",
        is_default: bool = False,
    ) -> None:
        """Register a SQL Server instance to monitor."""
        self._instance_configs[name] = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
        }

        conn_str = build_connection_string(host, port, user, password, database)

        engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={conn_str}",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
        )

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = __import__("time").time()

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            elapsed = __import__("time").time() - context._query_start_time
            if elapsed > 5.0:
                logger.warning(f"[{name}] Slow monitoring query: {elapsed:.2f}s")

        self._engines[name] = engine

        if is_default or self._default_instance is None:
            self._default_instance = name

        logger.info(f"Registered SQL Server instance: [{name}] @ {host}:{port}/{database}")

    @contextmanager
    def get_connection(self, instance_name: Optional[str] = None) -> Generator:
        """Get a connection to a registered instance. Use as a context manager."""
        name = instance_name or self._default_instance
        if name not in self._engines:
            raise ValueError(f"Unknown instance: '{name}'. Register it first.")
        engine = self._engines[name]
        with engine.connect() as conn:
            yield conn

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(OperationalError),
        reraise=True,
    )
    def execute_query(
        self,
        sql: str,
        instance_name: Optional[str] = None,
        params: Optional[dict] = None,
    ) -> list[dict]:
        """Execute a query and return results as a list of dicts."""
        name = instance_name or self._default_instance
        with self.get_connection(name) as conn:
            result = conn.execute(text(sql), params or {})
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows

    def test_connection(self, instance_name: Optional[str] = None) -> dict:
        """Test connectivity to an instance and return basic server info."""
        name = instance_name or self._default_instance
        try:
            rows = self.execute_query(
                "SELECT @@SERVERNAME AS server_name, @@VERSION AS version, GETDATE() AS server_time",
                instance_name=name,
            )
            return {"status": "connected", "instance": name, **rows[0]}
        except Exception as e:
            logger.error(f"Connection test failed for [{name}]: {e}")
            return {"status": "failed", "instance": name, "error": str(e)}

    def get_registered_instances(self) -> list[str]:
        """Return list of all registered instance names."""
        return list(self._engines.keys())

    def dispose_all(self) -> None:
        """Dispose all engine connection pools. Call on shutdown."""
        for name, engine in self._engines.items():
            engine.dispose()
            logger.info(f"Disposed connection pool for [{name}]")


# ---------------------------------------------------------------------------
# Module-level singleton - imported everywhere in the app
# ---------------------------------------------------------------------------
db_manager = DatabaseConnectionManager()


def initialize_from_settings() -> None:
    """Bootstrap the db_manager from app settings on startup."""
    db_manager.register_instance(
        name="primary",
        host=settings.sql_server_host,
        port=settings.sql_server_port,
        user=settings.sql_server_user,
        password=settings.sql_server_password,
        database=settings.sql_server_database,
        is_default=True,
    )
    logger.info("Database manager initialized from settings.")