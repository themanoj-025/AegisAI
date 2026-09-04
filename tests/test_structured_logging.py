"""Tests for structured logging module."""

import json
import logging

from app.logging.structured_logging import JSONFormatter, setup_logger


class TestSetupLogger:
    """Tests for setup_logger."""

    def test_creates_logger_with_handlers(self, tmp_path) -> None:
        logger = setup_logger("aegisai.test_sl_a", log_dir=str(tmp_path))
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 2  # rotating file handler + console

    def test_json_formatter(self) -> None:
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "test message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"

    def test_json_formatter_includes_request_id(self) -> None:
        from app.logging.structured_logging import set_request_id

        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="with context",
            args=(),
            exc_info=None,
        )
        set_request_id("req-123")
        try:
            parsed = json.loads(fmt.format(record))
        finally:
            from app.logging.structured_logging import request_id_var

            request_id_var.set(None)
        assert parsed["request_id"] == "req-123"
