"""Tests for structured logging module."""

import json
import logging

from app.logging.structured_logging import StructuredFormatter, setup_logging


class TestSetupLogging:
    """Tests for setup_logging."""

    def test_creates_handler(self):
        logger = logging.getLogger("aegisai.test_sl")
        original_handlers = logger.handlers[:]
        setup_logging()
        # Should not raise
        logger.handlers = original_handlers

    def test_structured_formatter(self):
        fmt = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="test message", args=(), exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "test message"
        assert parsed["level"] == "INFO"
