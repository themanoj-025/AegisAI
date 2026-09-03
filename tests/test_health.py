"""Tests for the canonical shared health endpoints (app/health.py).

Covers the liveness probe (/health) and the Redis-backed readiness probe
(/health/ready) wired in app/main.py, exercising the module that is synced
from shared/aegis_common/health.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_liveness_probe(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readiness_ready_when_redis_up(client: TestClient) -> None:
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    with patch("app.main.get_redis", return_value=redis_mock):
        resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"][0]["name"] == "redis"
    assert body["checks"][0]["status"] == "up"


def test_readiness_503_when_redis_down(client: TestClient) -> None:
    redis_mock = MagicMock()
    redis_mock.ping.side_effect = ConnectionError("redis down")
    with patch("app.main.get_redis", return_value=redis_mock):
        resp = client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"][0]["status"] == "down"
    assert "redis down" in body["checks"][0]["error"]


def test_canonical_health_module_synced(client: TestClient) -> None:
    """The vendored module must still be the canonical copy."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    canonical = repo_root / "shared" / "aegis_common" / "health.py"
    if canonical.exists():
        vendored = repo_root / "AegisAI" / "app" / "health.py"
        assert vendored.read_text(encoding="utf-8") == canonical.read_text(encoding="utf-8")
