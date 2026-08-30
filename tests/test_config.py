"""Tests for app.config — Settings loading with defaults and environment overrides."""

import os
from unittest.mock import patch

from app.config import Settings

pytestmark = pytest.mark.slow
class TestSettings:
    def test_defaults_are_set(self) -> None:
        """Settings should have sensible defaults even without env vars."""
        with patch.dict(os.environ, {}, clear=False):
            s = Settings()
            # Defaults should be empty strings or known values
            assert s.llm_provider in ("anthropic", "openai")
            assert s.redis_url == "redis://localhost:6379"
            assert s.workspace_dir == "./workspace"
            assert s.claude_model == "claude-sonnet-4-20250514"
            assert s.openai_model == "gpt-4o"

    def test_env_override_works(self) -> None:
        """Environment variables should override defaults."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "REDIS_URL": "redis://prod:6379"}):
            s = Settings()
            assert s.llm_provider == "openai"
            assert s.redis_url == "redis://prod:6379"

    def test_settings_are_frozen(self) -> None:
        """Settings should be immutable after creation."""
        s = Settings()
        try:
            s.llm_provider = "changed"
            assert False, "Should have raised an error"
        except (AttributeError, ValueError, TypeError):
            pass  # Expected — frozen model

    def test_github_fields(self) -> None:
        """GitHub-related settings should be present."""
        s = Settings()
        assert hasattr(s, "github_app_id")
        assert hasattr(s, "github_private_key_path")
        assert hasattr(s, "github_webhook_secret")
