"""Tests for security agent."""

import pytest
from unittest.mock import MagicMock, patch

from app.agents.security_agent import SecurityAgent


class TestSecurityAgent:
    """Tests for SecurityAgent."""

    def test_init(self):
        agent = SecurityAgent()
        assert agent is not None

    def test_analyze_diff_empty(self):
        agent = SecurityAgent()
        result = agent.analyze_diff([], "test context")
        assert isinstance(result, list)
