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
    sql_server_password: str = Field(..., env="SQL_SERVER_PASSWORD")
    sql_server_database: str = Field("master", env="SQL_SERVER_DATABASE")

    # App
    guardian_env: str = Field("development", env="GUARDIAN_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("logs/sqlguardian.log", env="LOG_FILE")

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
