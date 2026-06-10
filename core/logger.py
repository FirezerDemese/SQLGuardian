"""
SQLGuardian - Logging Setup
Structured logging to console + rotating file using loguru.
"""

import sys
from loguru import logger
from config.settings import settings


def setup_logging() -> None:
    """Configure loguru for the application."""
    logger.remove()  # Remove default handler

    # Console - human readable
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File - JSON structured, rotating, 7-day retention
    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
        level=settings.log_level,
        rotation="100 MB",
        retention="7 days",
        compression="zip",
        serialize=False,
    )

    logger.info(f"SQLGuardian logging initialized | env={settings.guardian_env} | level={settings.log_level}")
