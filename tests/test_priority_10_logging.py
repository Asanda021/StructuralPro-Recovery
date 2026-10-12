from pathlib import Path
import logging

from core.platform.logging import (
    BACKUP_COUNT,
    MAX_BYTES,
    RedactingFormatter,
    configure_logging,
    default_log_directory,
    install_exception_hook,
    redact,
)


def test_log_directory_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("STRUCTURALPRO_LOG_DIR", str(tmp_path))
    assert default_log_directory() == tmp_path


def test_redaction_hides_common_credentials():
    value = redact("token=abc123 password=hunter2 api_key=xyz")
    assert "[REDACTED]" in value
    assert "abc123" not in value
    assert "hunter2" not in value
    assert "xyz" not in value


def test_logging_is_idempotent_and_writes_to_rotating_file(tmp_path):
    logger = configure_logging(tmp_path)
    again = configure_logging(tmp_path)
    assert logger is again
    assert any("RotatingFileHandler" in type(h).__name__ for h in logger.handlers)
    assert MAX_BYTES > 0 and BACKUP_COUNT > 0
    logger.info("release logging smoke test")
    for handler in logger.handlers:
        handler.flush()
    assert (tmp_path / "structuralpro.log").exists()


def test_exception_hook_is_installed_without_replacing_keyboard_interrupt_behavior():
    logger = configure_logging(Path(__file__).parent / ".tmp-logging")
    install_exception_hook(logger)
    assert getattr(__import__("sys"), "_structuralpro_exception_hook", False)


def test_formatter_is_a_logging_formatter():
    assert isinstance(RedactingFormatter("%(message)s"), logging.Formatter)
