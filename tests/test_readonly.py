"""The monitoring connection observes and never writes.

Asserted against the actual queries in core/monitor.py, so a query added later
that writes fails this suite rather than reaching a production instance.
"""

from __future__ import annotations

import pytest

import core.monitor as monitor
from core.db_connection import DatabaseConnectionManager, WriteAttempted, assert_read_only


MONITOR_QUERIES = {
    name: getattr(monitor, name) for name in dir(monitor) if name.endswith("_SQL")
}


def test_the_monitor_defines_the_queries_this_suite_expects():
    assert len(MONITOR_QUERIES) >= 12, "core/monitor.py queries moved or were renamed"


@pytest.mark.parametrize("name", sorted(MONITOR_QUERIES))
def test_every_monitoring_query_is_a_read(name):
    assert_read_only(MONITOR_QUERIES[name])


@pytest.mark.parametrize("statement", [
    "KILL 62",
    "UPDATE Sales.OrderLines SET Status = 2",
    "DELETE FROM msdb.dbo.sysjobhistory",
    "DROP TABLE Sales.OrderLines",
    "TRUNCATE TABLE Sales.OrderLines",
    "ALTER DATABASE WideWorldImporters SET RECOVERY SIMPLE",
    "BACKUP DATABASE WideWorldImporters TO DISK = 'x.bak'",
    "RESTORE DATABASE WideWorldImporters FROM DISK = 'x.bak'",
    "DBCC FREEPROCCACHE",
    "DBCC INPUTBUFFER(62)",
    "EXEC msdb.dbo.sp_start_job @job_name = N'WWI Nightly Full Backup'",
    "EXECUTE sp_configure 'max server memory', 4096",
    "GRANT CONTROL SERVER TO sqlguardian",
    "SHUTDOWN WITH NOWAIT",
    "SELECT * INTO #staging FROM sys.databases",
])
def test_writes_are_refused(statement):
    with pytest.raises(WriteAttempted):
        assert_read_only(statement)


@pytest.mark.parametrize("statement", [
    "-- SELECT 1\nDELETE FROM Sales.OrderLines",
    "/* SELECT */ UPDATE Sales.OrderLines SET Status = 2",
    "SELECT 1; DROP TABLE Sales.OrderLines",
    "SELECT 1;\nKILL 62",
])
def test_a_write_hidden_behind_a_comment_or_a_second_statement_is_refused(statement):
    """Comments are stripped before the check, so nothing hides behind one."""
    with pytest.raises(WriteAttempted):
        assert_read_only(statement)


def test_a_keyword_inside_a_string_literal_does_not_trip_the_guard():
    """Refusing a legitimate read would push someone to bypass the guard."""
    assert_read_only(
        "SELECT name FROM sys.databases WHERE name = N'delete_me_2024' "
        "AND state_desc = 'ONLINE'"
    )


def test_a_cte_is_allowed():
    assert_read_only(
        "WITH waits AS (SELECT wait_type, wait_time_ms FROM sys.dm_os_wait_stats) "
        "SELECT TOP 10 * FROM waits ORDER BY wait_time_ms DESC"
    )


def test_execute_query_refuses_a_write_before_opening_a_connection():
    """The guard runs first, so an unregistered instance is never even reached."""
    manager = DatabaseConnectionManager()          # no instances registered at all
    with pytest.raises(WriteAttempted):
        manager.execute_query("KILL 62")


def test_remediation_tsql_is_never_executed_by_the_monitoring_path():
    """Generated T-SQL is shown to a DBA to run themselves; it is not executable here.

    Every suggested script - including the KILL - would be refused if anything
    tried to route it through the monitoring connection.
    """
    from core.actions import build_action_plan
    from core.conditions import detect_conditions

    manager = DatabaseConnectionManager()
    snapshot = {
        "blocking": {
            "blocked_session_count": 2, "head_blocker_count": 1, "max_wait_seconds": 300,
            "head_blockers": [{"session_id": 62, "current_sql": "UPDATE x SET y = 1"}],
            "blocked_sessions": [{"session_id": 71, "wait_seconds": 300,
                                  "wait_type": "LCK_M_S", "database_name": "WWI"}],
        },
    }
    condition = detect_conditions(snapshot)[0]
    plan = build_action_plan(condition)
    scripts = [a["tsql"] for a in plan["actions"] if a["tsql"]]
    assert scripts

    refused = 0
    for script in scripts:
        try:
            manager.execute_query(script)
        except WriteAttempted:
            refused += 1
        except ValueError:
            pass       # a pure read got past the guard and hit "no instance registered"
    assert refused >= 1, "the KILL script should have been refused by the guard"


def test_settings_load_without_a_database_credential():
    """A fresh clone must be able to run `pytest` before anyone writes a .env.

    None of these tests touch a database. Requiring SQL_SERVER_PASSWORD to
    construct Settings meant the whole suite died at import with a pydantic
    validation trace, which is the first thing a reviewer would see.

    _env_file=None reads no .env and no repo state, so this asserts the field
    default itself rather than whatever happens to be on this machine.
    """
    from config.settings import Settings

    bare = Settings(_env_file=None)
    assert bare.sql_server_password == ""
    assert bare.sql_server_host == "localhost"
    assert bare.groq_model == "openai/gpt-oss-120b"


def test_connecting_without_a_credential_fails_with_a_sentence(monkeypatch):
    """The credential is required to connect, and the error says what to do."""
    import core.db_connection as db

    # Patch the settings object db_connection actually holds, not a fresh
    # import of it - they can be different objects.
    monkeypatch.setattr(db.settings, "sql_server_password", "")
    with pytest.raises(db.MissingCredential, match="SQL_SERVER_PASSWORD is not set"):
        db.initialize_from_settings()


def test_a_transient_blip_is_retried_rather_than_treated_as_an_outage():
    """The circuit breaker must sit outside the retry, not inside it.

    When the breaker opened on the first failed attempt it short-circuited
    tenacity's own retry, so a momentary connection error blanked every
    remaining query in the snapshot instead of being retried once.
    """
    from contextlib import contextmanager
    from sqlalchemy.exc import OperationalError

    manager = DatabaseConnectionManager()
    manager.register_instance("t", "127.0.0.1", 1, "sa", "x", "master", is_default=True)

    attempts = {"n": 0}

    @contextmanager
    def flaky(name=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OperationalError("blip", None, Exception("transient"))
        yield type("Conn", (), {
            "execute": lambda self, *a, **k: type("Result", (), {
                "keys": lambda self: ["x"],
                "fetchall": lambda self: [(1,)],
            })()
        })()

    manager.get_connection = flaky
    assert manager.execute_query("SELECT 1 AS x") == [{"x": 1}]
    assert attempts["n"] == 2, "the retry did not run"
    assert manager._breaker == {}, "a recovered blip must not leave the breaker open"


def test_a_sustained_outage_opens_the_breaker_and_later_queries_fail_immediately():
    """One retry sequence is paid once; the rest of the snapshot fails fast."""
    from contextlib import contextmanager
    from sqlalchemy.exc import OperationalError
    from core.db_connection import InstanceUnreachable

    manager = DatabaseConnectionManager()
    manager.register_instance("t", "127.0.0.1", 1, "sa", "x", "master", is_default=True)

    calls = {"n": 0}

    @contextmanager
    def always_down(name=None):
        calls["n"] += 1
        raise OperationalError("down", None, Exception("unreachable"))
        yield  # pragma: no cover

    manager.get_connection = always_down

    with pytest.raises(OperationalError):
        manager.execute_query("SELECT 1 AS x")
    after_first = calls["n"]
    assert after_first == 2, "both retry attempts should have been used"

    for _ in range(12):
        with pytest.raises(InstanceUnreachable):
            manager.execute_query("SELECT 1 AS x")
    assert calls["n"] == after_first, "the breaker should have stopped further connections"
