"""
SQLGuardian - Database Connection Manager
Handles SQL Server connections with retry logic, pooling, and health checks.
"""

import re
import time

# Imported for its side effect: SQLAlchemy's mssql+pyodbc dialect needs the
# driver present, and failing here gives a clear error at import time rather
# than an obscure one on the first query.
import pyodbc  # noqa: F401
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from typing import Optional, Generator
from contextlib import contextmanager

from config.settings import settings


# ---------------------------------------------------------------------------
# Read-only guard
# ---------------------------------------------------------------------------
# The monitoring connection observes and never writes. That is enforced here
# rather than asserted in a README: every statement this manager executes has
# to pass WriteAttempted, and tests/test_readonly.py exercises the guard
# against the full set of queries in core/monitor.py.
#
# The account SQLGuardian connects with needs, and only needs:
#   VIEW SERVER STATE      - the sys.dm_* dynamic management views
#   VIEW ANY DEFINITION    - object names behind sql_handle
#   CONNECT to msdb + SQLAgentReaderRole - Agent job history
#   VIEW ANY DATABASE      - database list and backup history
# sysadmin is not required and should not be granted.

class WriteAttempted(PermissionError):
    """A statement that is not a read was submitted on the monitoring connection."""


_FORBIDDEN_VERBS = (
    "insert", "update", "delete", "merge", "truncate", "drop", "create", "alter",
    "grant", "revoke", "deny", "backup", "restore", "kill", "shutdown", "reconfigure",
    "dbcc", "exec", "execute", "sp_", "xp_", "waitfor", "bulk", "openrowset", "into",
)

# Comments and string literals are stripped before checking so that a T-SQL
# keyword inside a comment or a quoted name cannot trip the guard, and so that
# a write cannot be hidden behind one either.
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r"N?'(?:[^']|'')*'")


def assert_read_only(sql: str) -> None:
    """Raise WriteAttempted unless `sql` is a read.

    Allows SELECT and WITH (a CTE that ends in SELECT). Everything else is
    refused, including EXEC of a read-only stored procedure - SQLGuardian has
    no reason to call one, and allowing EXEC would make the guard meaningless.
    """
    stripped = _STRING_RE.sub("''", _BLOCK_COMMENT_RE.sub(" ", _LINE_COMMENT_RE.sub(" ", sql)))
    normalised = " ".join(stripped.split()).lower()
    if not normalised:
        raise WriteAttempted("Empty statement submitted on the monitoring connection.")

    if not normalised.startswith(("select ", "select\t", "with ", "(select")):
        verb = normalised.split(" ", 1)[0]
        raise WriteAttempted(
            f"The monitoring connection is read-only; refused a statement starting "
            f"with '{verb}'."
        )

    for verb in _FORBIDDEN_VERBS:
        # sp_ / xp_ prefixes are also matched after a schema qualifier, so
        # msdb.dbo.sp_start_job cannot slip past on the dot.
        pattern = rf"(?:^|[\s(;]){re.escape(verb)}(?:[\s(]|$)" if not verb.endswith("_") \
            else rf"(?:^|[\s(;.]){re.escape(verb)}"
        if re.search(pattern, normalised):
            raise WriteAttempted(
                f"The monitoring connection is read-only; refused a statement "
                f"containing '{verb.strip()}'."
            )


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
        f"Connection Timeout={settings.db_connect_timeout_seconds};"
    )


class InstanceUnreachable(ConnectionError):
    """The instance failed to connect recently and is inside its cooldown window."""


class DatabaseConnectionManager:
    """
    Manages SQL Server connections for SQLGuardian.
    Supports multiple monitored instances, connection pooling, and auto-retry.

    Includes a per-instance circuit breaker. A health snapshot runs thirteen
    queries; without a breaker, an unreachable instance means thirteen
    independent retry sequences with exponential backoff, and a snapshot
    request that hangs for minutes. A monitoring tool has to stay responsive
    exactly when the thing it monitors is down, so the first connection failure
    opens the breaker and the remaining queries fail immediately with the
    original error. The checks then report as failed rather than as healthy -
    see core/conditions.failed_checks.
    """

    def __init__(self):
        self._engines: dict[str, object] = {}
        self._instance_configs: dict[str, dict] = {}
        self._default_instance: Optional[str] = None
        # name -> (open_until_monotonic, error message)
        self._breaker: dict[str, tuple[float, str]] = {}

    # -- circuit breaker ---------------------------------------------------

    def _breaker_check(self, name: str) -> None:
        entry = self._breaker.get(name)
        if entry is None:
            return
        open_until, message = entry
        if time.monotonic() < open_until:
            raise InstanceUnreachable(
                f"[{name}] is unreachable and inside its "
                f"{settings.db_unreachable_cooldown_seconds}s cooldown: {message}"
            )
        del self._breaker[name]

    def _breaker_open(self, name: str, error: Exception) -> None:
        self._breaker[name] = (
            time.monotonic() + settings.db_unreachable_cooldown_seconds,
            str(error).split("\n")[0][:300],
        )
        logger.warning(
            f"[{name}] connection failed; skipping further queries for "
            f"{settings.db_unreachable_cooldown_seconds}s."
        )

    def _breaker_close(self, name: str) -> None:
        if self._breaker.pop(name, None) is not None:
            logger.info(f"[{name}] is reachable again.")

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
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError),
        reraise=True,
    )
    def _execute_with_retry(
        self,
        sql: str,
        name: str,
        params: Optional[dict],
    ) -> list[dict]:
        """One query, retried on a transient connection error.

        Deliberately separate from execute_query: the circuit breaker has to sit
        OUTSIDE this, or the breaker it opens on the first failure short-circuits
        the retry it was supposed to allow, and a momentary network blip blanks a
        whole snapshot instead of being retried.
        """
        with self.get_connection(name) as conn:
            result = conn.execute(text(sql), params or {})
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def execute_query(
        self,
        sql: str,
        instance_name: Optional[str] = None,
        params: Optional[dict] = None,
    ) -> list[dict]:
        """Execute a read-only query and return results as a list of dicts.

        Raises WriteAttempted before opening a connection if `sql` is anything
        other than a read. The guard runs on every call, including callers
        added later that have never read this docstring.

        Layering, outermost first: read-only guard, circuit breaker, retry.
        """
        assert_read_only(sql)
        name = instance_name or self._default_instance
        self._breaker_check(name)
        try:
            rows = self._execute_with_retry(sql, name, params)
        except OperationalError as exc:
            # Retries are exhausted by the time this propagates, so the instance
            # is genuinely not answering rather than briefly busy.
            self._breaker_open(name, exc)
            raise
        self._breaker_close(name)
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


class MissingCredential(RuntimeError):
    """No SQL Server password is configured, so no instance can be monitored."""


def initialize_from_settings() -> None:
    """Bootstrap the db_manager from app settings on startup.

    The credential is checked here rather than at import time, so the parts of
    SQLGuardian that need no database - the runbook corpus, the gap report, the
    tests - keep working without one, and the failure that does matter arrives
    as a sentence instead of a validation trace.
    """
    if not settings.sql_server_password:
        raise MissingCredential(
            "SQL_SERVER_PASSWORD is not set, so no SQL Server instance can be "
            "monitored. Copy .env.example to .env and set it. The runbook and "
            "reporting features do not need it."
        )
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