"""Tests for LLM Gateway abstraction layer."""

from unittest.mock import patch

import pytest

from app.services.llm_gateway import _get_provider, _is_retryable, _RetryableError

pytestmark = pytest.mark.unit



class TestIsRetryable:
    """Tests for _is_retryable helper."""

    def test_retryable_error_is_retryable(self) -> None:
        assert _is_retryable(_RetryableError("transient")) is True

    def test_value_error_not_retryable(self) -> None:
        assert _is_retryable(ValueError("bad")) is False

    def test_runtime_error_not_retryable(self) -> None:
        assert _is_retryable(RuntimeError("bad")) is False

    def test_os_error_not_retryable(self) -> None:
        assert _is_retryable(OSError("bad")) is False


class TestGetProvider:
    """Tests for _get_provider (requires env vars)."""

    def test_unknown_provider_raises(self) -> None:
        import app.services.llm_gateway as mod

        mod._provider = None
        with patch("app.services.llm_gateway.settings") as mock_settings:
            mock_settings.llm_provider = "unknown"
            with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
                _get_provider()

    @patch("app.services.llm_gateway.settings")
    def test_anthropic_provider_created(self, mock_settings) -> None:
        import app.services.llm_gateway as mod

        mod._provider = None
        mock_settings.llm_provider = "anthropic"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.claude_model = "claude-3"
        # Don't actually instantiate anthropic client — just check the branch
        with patch("anthropic.Anthropic"):
            provider = _get_provider()
            assert isinstance(provider, mod._AnthropicProvider)
        mod._provider = None  # cleanup

    @patch("app.services.llm_gateway.settings")
    def test_openai_provider_created(self, mock_settings) -> None:
        import app.services.llm_gateway as mod

        mod._provider = None
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4"
        with patch("openai.OpenAI"):
            provider = _get_provider()
            assert isinstance(provider, mod._OpenAIProvider)
        mod._provider = None  # cleanup


class TestRetryableError:
    """Tests for _RetryableError."""

    def test_message_preserved(self) -> None:
        err = _RetryableError("rate limited")
        assert str(err) == "rate limited"

    def test_is_exception(self) -> None:
        assert issubclass(_RetryableError, Exception)
