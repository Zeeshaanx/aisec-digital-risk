"""
Structured JSON logging configuration.

Provides consistent log formatting across the entire application.
All log entries include timestamp, level, logger name, and message.
Scan executions, auth events, and errors are logged for monitoring.
"""

import logging
import json
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Allow attaching extra structured data via record.__dict__
        for key in ("user_id", "target_id", "scan_id", "action", "duration", "extra_data"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = str(val) if not isinstance(val, (str, int, float, bool)) else val
        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure application-wide structured logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        The root 'media_intel' logger instance.
    """
    # Remove existing handlers to avoid duplicates on re-init
    root = logging.getLogger()
    root.handlers.clear()

    log_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(log_level)

    # Stdout handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.setLevel(log_level)
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("sqlalchemy.engine", "httpx", "httpcore", "asyncio", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    app_logger = logging.getLogger("media_intel")
    app_logger.info("Logging initialized", extra={"action": "logging_setup", "extra_data": {"level": level}})
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the media_intel namespace.

    Args:
        name: Logger name suffix (e.g., 'auth', 'scan', 'agent').

    Returns:
        Logger instance for media_intel.<name>.
    """
    return logging.getLogger(f"media_intel.{name}")
