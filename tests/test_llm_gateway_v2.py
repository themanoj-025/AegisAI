"""Tests for LLM gateway provider selection and retry."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_gateway import _RetryableError, call_llm


class TestLLMGatewayV2:
    """Additional tests for LLM gateway."""

    def test_retryable_error_inherits_exception(self):
        err = _RetryableError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"

    def test_retryable_error_with_cause(self):
        try:
            raise ConnectionError("connection refused")
        except ConnectionError as orig:
            err = _RetryableError("retryable") from orig
            assert err.__cause__ is orig

    @patch("app.services.llm_gateway._get_provider")
    def test_call_llm_delegates_to_provider(self, mock_get):
        mock_provider = MagicMock()
        mock_provider.call.return_value = '{"result": "ok"}'
        mock_get.return_value = mock_provider
        result = call_llm("system", "user")
        assert result == '{"result": "ok"}'
        mock_provider.call.assert_called_once_with("system", "user", "json")

    @patch("app.services.llm_gateway._get_provider")
    def test_call_llm_text_format(self, mock_get):
        mock_provider = MagicMock()
        mock_provider.call.return_value = "plain text"
        mock_get.return_value = mock_provider
        result = call_llm("system", "user", response_format="text")
        assert result == "plain text"
        mock_provider.call.assert_called_once_with("system", "user", "text")
