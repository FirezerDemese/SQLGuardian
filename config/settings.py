"""
SQLGuardian - Application Settings
All config pulled from environment variables. Never hardcode secrets.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # SQL Server connection
    sql_server_host: str = Field("localhost", env="SQL_SERVER_HOST")
    sql_server_port: int = Field(1433, env="SQL_SERVER_PORT")
    sql_server_user: str = Field("sa", env="SQL_SERVER_USER")
    # Not required at import time. Every unit test, the runbook corpus, the gap
    # report and the whole dashboard work with no database credential at all -
    # refusing to construct Settings without one means `pytest` on a fresh clone
    # dies with a pydantic trace instead of running. The credential is required
    # to CONNECT, and initialize_from_settings() says so in a sentence.
    sql_server_password: str = Field("", env="SQL_SERVER_PASSWORD")
    sql_server_database: str = Field("master", env="SQL_SERVER_DATABASE")

    # App
    guardian_env: str = Field("development", env="GUARDIAN_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("logs/sqlguardian.log", env="LOG_FILE")

    # A monitoring probe should not wait half a minute to admit that a host is
    # not answering; the poll interval is 60s.
    db_connect_timeout_seconds: int = Field(10, env="DB_CONNECT_TIMEOUT_SECONDS")

    # How long to stop querying an instance after a connection failure. A
    # snapshot is thirteen queries; without this, one unreachable instance
    # means thirteen retry sequences and a request that hangs for minutes.
    db_unreachable_cooldown_seconds: int = Field(30, env="DB_UNREACHABLE_COOLDOWN_SECONDS")

    # Monitoring thresholds
    cpu_warning_pct: float = Field(75.0, env="CPU_WARNING_PCT")
    cpu_critical_pct: float = Field(90.0, env="CPU_CRITICAL_PCT")
    memory_warning_pct: float = Field(80.0, env="MEMORY_WARNING_PCT")
    memory_critical_pct: float = Field(95.0, env="MEMORY_CRITICAL_PCT")
    disk_warning_pct: float = Field(80.0, env="DISK_WARNING_PCT")
    disk_critical_pct: float = Field(90.0, env="DISK_CRITICAL_PCT")
    blocking_warning_seconds: int = Field(30, env="BLOCKING_WARNING_SECONDS")
    blocking_critical_seconds: int = Field(120, env="BLOCKING_CRITICAL_SECONDS")

    # Scheduler
    health_check_interval_seconds: int = Field(60, env="HEALTH_CHECK_INTERVAL_SECONDS")
    job_check_interval_seconds: int = Field(120, env="JOB_CHECK_INTERVAL_SECONDS")

    # Log space (used by the LOG_GROWTH condition)
    log_used_warning_pct: float = Field(75.0, env="LOG_USED_WARNING_PCT")
    log_used_critical_pct: float = Field(90.0, env="LOG_USED_CRITICAL_PCT")

    # Long-running request threshold (used by the LONG_RUNNING_REQUEST condition)
    long_query_warning_seconds: int = Field(30, env="LONG_QUERY_WARNING_SECONDS")
    long_query_critical_seconds: int = Field(300, env="LONG_QUERY_CRITICAL_SECONDS")

    # Backup age (used by the BACKUP_AGE_EXCEEDED condition)
    backup_age_warning_hours: int = Field(25, env="BACKUP_AGE_WARNING_HOURS")
    backup_age_critical_hours: int = Field(48, env="BACKUP_AGE_CRITICAL_HOURS")

    # LLM narration layer.
    # Model id is config, not code: Groq retires models on a published schedule
    # (llama-3.3-70b-versatile and llama-3.1-8b-instant were retired 2026-08-16),
    # so the next retirement is an env change, not a code change.
    groq_api_key: str = Field("", env="GROQ_API_KEY")
    groq_model: str = Field("openai/gpt-oss-120b", env="GROQ_MODEL")
    groq_api_url: str = Field(
        "https://api.groq.com/openai/v1/chat/completions", env="GROQ_API_URL"
    )
    groq_timeout_seconds: float = Field(45.0, env="GROQ_TIMEOUT_SECONDS")

    # Runbook corpus + incident history live on disk so they survive a restart.
    runbook_store_dir: str = Field("data/runbooks/store", env="RUNBOOK_STORE_DIR")
    incident_store_dir: str = Field("data/incidents", env="INCIDENT_STORE_DIR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
