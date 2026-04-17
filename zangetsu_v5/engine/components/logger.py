"""Structured JSON logging for all engine components.

Produces one JSON object per log line. Supports log rotation,
context fields, and integration with the health monitor.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredLogger:
    """JSON-structured logger with rotation support.

    Integration:
        - CONSOLE_HOOK: log_level, log_file, log_rotation_mb
        - DASHBOARD_HOOK: log_stats
    """

    def __init__(
        self,
        name: str = "zangetsu_v5",
        level: str = "INFO",
        log_file: Optional[str] = None,
        rotation_mb: int = 50,
    ) -> None:
        self._name = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.handlers.clear()
        self._counts: Dict[str, int] = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0}

        formatter = _JsonFormatter()

        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        self._logger.addHandler(console)

        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(path),
                maxBytes=rotation_mb * 1024 * 1024,
                backupCount=5,
            )
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def debug(self, msg: str, **ctx: Any) -> None:
        self._counts["DEBUG"] += 1
        self._logger.debug(msg, extra={"ctx": ctx})

    def info(self, msg: str, **ctx: Any) -> None:
        self._counts["INFO"] += 1
        self._logger.info(msg, extra={"ctx": ctx})

    def warning(self, msg: str, **ctx: Any) -> None:
        self._counts["WARNING"] += 1
        self._logger.warning(msg, extra={"ctx": ctx})

    def error(self, msg: str, **ctx: Any) -> None:
        self._counts["ERROR"] += 1
        self._logger.error(msg, extra={"ctx": ctx})

    def arena_event(
        self, arena: str, event: str, round_num: int = 0, **ctx: Any
    ) -> None:
        """Structured arena event log."""
        self.info(
            "[" + arena + "] " + event,
            arena=arena,
            event=event,
            round=round_num,
            **ctx,
        )

    # DASHBOARD_HOOK: log_stats
    def health_check(self) -> Dict:
        return {
            "name": self._name,
            "level": self._logger.level,
            "handlers": len(self._logger.handlers),
            "counts": dict(self._counts),
        }


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        ctx = getattr(record, "ctx", None)
        if ctx:
            data["ctx"] = ctx
        if record.exc_info and record.exc_info[1]:
            data["exception"] = str(record.exc_info[1])
        return json.dumps(data, default=str)
