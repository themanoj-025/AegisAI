"""Tests for main app routes."""


from app.main import create_app


class TestCreateApp:
    """Tests for create_app factory."""

    def test_creates_app(self):
        app = create_app()
        assert app is not None

    def test_has_webhook_route(self):
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/webhook" in routes

    def test_has_health_route(self):
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/health" in routes
