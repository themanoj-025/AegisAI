"""Tests for GitHub App installation-token service."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.services.github_auth as auth


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self) -> dict:
        return self._json


class _FakeClient:
    """Context-manager httpx.Client stand-in returning a canned response."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def post(self, url: str, headers: dict) -> _FakeResponse:
        return self._response


def _expires_in(minutes: int = 60) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(autouse=True)
def _clear_token_cache():
    auth._token_cache.clear()
    yield
    auth._token_cache.clear()


class TestGetInstallationToken:
    def test_success_returns_token_and_caches(self, monkeypatch) -> None:
        monkeypatch.setattr(auth, "_generate_jwt", lambda: "jwt-token")
        resp = _FakeResponse(201, {"token": "inst-token", "expires_at": _expires_in()})
        monkeypatch.setattr(auth.httpx, "Client", lambda: _FakeClient(resp))

        token = auth.get_installation_token(123)
        assert token == "inst-token"
        assert 123 in auth._token_cache

        # Second call must reuse the cache (no new HTTP request)
        auth.httpx.Client = Mock(side_effect=AssertionError("should not call HTTP"))
        assert auth.get_installation_token(123) == "inst-token"

    def test_401_raises_permission_error(self, monkeypatch) -> None:
        monkeypatch.setattr(auth, "_generate_jwt", lambda: "jwt-token")
        resp = _FakeResponse(401, text="unauthorized")
        monkeypatch.setattr(auth.httpx, "Client", lambda: _FakeClient(resp))
        with pytest.raises(PermissionError):
            auth.get_installation_token(123)

    def test_403_raises_permission_error(self, monkeypatch) -> None:
        monkeypatch.setattr(auth, "_generate_jwt", lambda: "jwt-token")
        resp = _FakeResponse(403, text="forbidden")
        monkeypatch.setattr(auth.httpx, "Client", lambda: _FakeClient(resp))
        with pytest.raises(PermissionError):
            auth.get_installation_token(123)

    def test_unexpected_status_raises_runtime_error(self, monkeypatch) -> None:
        monkeypatch.setattr(auth, "_generate_jwt", lambda: "jwt-token")
        resp = _FakeResponse(500, text="boom")
        monkeypatch.setattr(auth.httpx, "Client", lambda: _FakeClient(resp))
        with pytest.raises(RuntimeError, match="HTTP 500"):
            auth.get_installation_token(123)


class TestPrivateKey:
    def test_missing_key_file_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(
            auth,
            "settings",
            SimpleNamespace(github_private_key_path="/nonexistent/gh-key.pem"),
        )
        with pytest.raises(FileNotFoundError, match="private key not found"):
            auth._read_private_key()

    def test_reads_key_file(self, monkeypatch, tmp_path) -> None:
        key_file = tmp_path / "gh-key.pem"
        key_file.write_text("PRIVATE KEY CONTENTS", encoding="utf-8")
        monkeypatch.setattr(
            auth,
            "settings",
            SimpleNamespace(github_private_key_path=str(key_file)),
        )
        assert auth._read_private_key() == "PRIVATE KEY CONTENTS"
