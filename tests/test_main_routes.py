"""Tests for the app's registered routes."""

from app.main import app


def _paths() -> list[str]:
    """All route paths — from the OpenAPI schema, which includes mounted routers."""
    return list(app.openapi()["paths"].keys())


class TestAppRoutes:
    def test_has_webhook_route(self) -> None:
        assert "/webhooks/github" in _paths()

    def test_has_health_route(self) -> None:
        paths = _paths()
        assert "/health" in paths

    def test_has_readiness_route(self) -> None:
        paths = _paths()
        assert "/health/ready" in paths

    def test_has_dlq_admin_route(self) -> None:
        paths = _paths()
        assert "/api/v1/webhooks/dlq" in paths

    def test_has_metrics_route(self) -> None:
        assert "/metrics" in _paths()
