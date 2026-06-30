"""LLM Gateway — swappable AI provider abstraction.

Provides a single call_llm() function that routes requests to either
Anthropic's Claude or OpenAI's GPT models based on the LLM_PROVIDER
environment variable. Calling code never needs to know which provider
is active.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger("aegisai")


class _RetryableError(Exception):
    """Transient error that should be retried (rate limits, 5xx, etc.)."""


def _is_retryable(exception: BaseException) -> bool:
    """Check if an exception should trigger a retry."""
    return isinstance(exception, _RetryableError)


class _LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str, response_format: str = "json") -> str:
        ...


class _AnthropicProvider(_LLMProvider):
    """Anthropic/Claude implementation."""

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_model

    def call(self, system_prompt: str, user_prompt: str, response_format: str = "json") -> str:
        import anthropic

        extra_kwargs: dict[str, Any] = {}

        # Request JSON output — Claude works well with structured prompting
        if response_format == "json":
            # For Claude, we instruct it clearly in the system prompt
            actual_system = (
                system_prompt
                + "\n\nIMPORTANT: You MUST respond with valid JSON only, no surrounding text or markdown."
            )
        else:
            actual_system = system_prompt

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=actual_system,
                messages=[{"role": "user", "content": user_prompt}],
                **extra_kwargs,
            )
        except anthropic.RateLimitError as e:
            raise _RetryableError(f"Anthropic rate limited: {e}") from e
        except anthropic.InternalServerError as e:
            raise _RetryableError(f"Anthropic server error: {e}") from e
        except anthropic.APIStatusError as e:
            # 401, 403, 400 — non-retryable
            raise RuntimeError(f"Anthropic API error (non-retryable): {e}") from e

        # Log token usage
        usage = getattr(response, "usage", None)
        if usage:
            logger.info(
                "Anthropic API call | model=%s | input_tokens=%s | output_tokens=%s",
                self._model,
                getattr(usage, "input_tokens", "unknown"),
                getattr(usage, "output_tokens", "unknown"),
            )

        content = response.content[0].text
        return content


class _OpenAIProvider(_LLMProvider):
    """OpenAI/GPT implementation."""

    def __init__(self) -> None:
        import openai

        self._client = openai.OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def call(self, system_prompt: str, user_prompt: str, response_format: str = "json") -> str:
        import openai

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 4096,
        }

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            raise _RetryableError(f"OpenAI rate limited: {e}") from e
        except openai.InternalServerError as e:
            raise _RetryableError(f"OpenAI server error: {e}") from e
        except openai.APIStatusError as e:
            raise RuntimeError(f"OpenAI API error (non-retryable): {e}") from e

        # Log token usage
        usage = getattr(response, "usage", None)
        if usage:
            logger.info(
                "OpenAI API call | model=%s | input_tokens=%s | output_tokens=%s",
                self._model,
                getattr(usage, "prompt_tokens", "unknown"),
                getattr(usage, "completion_tokens", "unknown"),
            )

        content = response.choices[0].message.content or ""
        return content


# Singleton provider instance
_provider: _LLMProvider | None = None


def _get_provider() -> _LLMProvider:
    """Get or create the active LLM provider based on settings."""
    global _provider
    if _provider is not None:
        return _provider

    provider_name = settings.llm_provider.lower()
    if provider_name == "anthropic":
        _provider = _AnthropicProvider()
        logger.info("LLM provider: Anthropic/Claude")
    elif provider_name == "openai":
        _provider = _OpenAIProvider()
        logger.info("LLM provider: OpenAI/GPT")
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider_name}'. Must be 'anthropic' or 'openai'."
        )

    return _provider


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def call_llm(system_prompt: str, user_prompt: str, response_format: str = "json") -> str:
    """Call the configured LLM provider and return the response text.

    Args:
        system_prompt: The system-level instructions for the model.
        user_prompt: The user message content.
        response_format: "json" to request structured JSON output, or "text".

    Returns:
        The model's response as a string.

    Raises:
        RuntimeError: On non-retryable API errors.
    """
    provider = _get_provider()
    return provider.call(system_prompt, user_prompt, response_format)
