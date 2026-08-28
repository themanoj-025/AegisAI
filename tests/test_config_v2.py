"""Tests for configuration settings."""

import pytest

from app.config import Settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_settings_singleton(self):
        from app.config import settings
        assert settings is not None

    def test_has_required_fields(self):
        from app.config import settings
        assert hasattr(settings, "anthropic_api_key")
        assert hasattr(settings, "openai_api_key")
        assert hasattr(settings, "llm_provider")
        assert hasattr(settings, "workspace_dir")
