"""Production-safe local logging and crash reporting primitives."""
from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOGGER_NAME = "structuralpro"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5
_SECRET_RE = re.compile(
    r"(?i)(password|passwd|token|api[_-]?key|secret|private[_-]?key|authorization)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def default_log_directory() -> Path:
    """Return a writable per-user log directory without requiring admin rights."""
    override = os.environ.get("STRUCTURALPRO_LOG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "StructuralPro" / "logs"
    return Path.home() / ".structuralpro" / "logs"


def redact(text: str) -> str:
    """Remove common credential-like key/value material from log text."""
    return _SECRET_RE.sub(r"\1\2[REDACTED]", str(text))


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(log_directory: Optional[Path] = None) -> logging.Logger:
    """Configure idempotent rotating file + stderr logging for the desktop app."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    directory = (log_directory or default_log_directory()).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    formatter = RedactingFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        directory / "structuralpro.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.WARNING)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def install_exception_hook(logger: Optional[logging.Logger] = None) -> logging.Logger:
    """Install a process-level hook that records uncaught exceptions."""
    logger = logger or configure_logging()
    if getattr(sys, "_structuralpro_exception_hook", False):
        return logger

    def handle(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Unhandled application exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle
    sys._structuralpro_exception_hook = True
    return logger
