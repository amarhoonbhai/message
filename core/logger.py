"""
Structured logging configuration for all services.

Creates rotating file handlers for worker, scheduler, and error logs,
plus a console handler for development.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def setup_service_logging(
    service_name: str,
    *,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """
    Configure structured logging for a named service.

    Creates:
      - logs/{service_name}.log   (all INFO+ messages, 10 MB rotating × 5)
      - logs/errors.log           (ERROR+ from all services, shared)
      - Console handler           (if console=True)

    Returns the root logger so third-party loggers can be silenced afterward.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if root.handlers:
        return root

    # ── Service-specific file handler ───────────────────────────────────
    service_fh = RotatingFileHandler(
        os.path.join(LOG_DIR, f"{service_name}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    service_fh.setLevel(level)
    service_fh.setFormatter(fmt)
    root.addHandler(service_fh)

    # ── Shared error log ────────────────────────────────────────────────
    error_fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "errors.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_fh.setLevel(logging.ERROR)
    error_fh.setFormatter(fmt)
    root.addHandler(error_fh)

    # ── Console handler ─────────────────────────────────────────────────
    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    # Silence noisy third-party loggers
    for noisy in (
        "telethon", "telethon.network", "telethon.crypto",
        "telethon.extensions", "httpx", "asyncio",
    ):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    return root
