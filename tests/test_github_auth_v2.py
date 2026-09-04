"""Tests for webhook signature verification (lives in app.main)."""

import hashlib
import hmac
from types import SimpleNamespace

import app.main as main


def _sig(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestVerifyGithubSignature:
    def test_valid_signature(self, monkeypatch) -> None:
        monkeypatch.setattr(main, "settings", SimpleNamespace(github_webhook_secret="my_secret"))
        payload = b'{"action": "opened"}'
        assert main.verify_github_signature(payload, _sig(payload, "my_secret")) is True

    def test_wrong_secret_rejected(self, monkeypatch) -> None:
        monkeypatch.setattr(main, "settings", SimpleNamespace(github_webhook_secret="correct"))
        payload = b"test payload"
        assert main.verify_github_signature(payload, _sig(payload, "wrong")) is False

    def test_empty_payload_valid(self, monkeypatch) -> None:
        monkeypatch.setattr(main, "settings", SimpleNamespace(github_webhook_secret="secret"))
        assert main.verify_github_signature(b"", _sig(b"", "secret")) is True

    def test_missing_signature_rejected(self, monkeypatch) -> None:
        monkeypatch.setattr(main, "settings", SimpleNamespace(github_webhook_secret="secret"))
        assert main.verify_github_signature(b"payload", None) is False
        assert main.verify_github_signature(b"payload", "") is False

    def test_bad_prefix_rejected(self, monkeypatch) -> None:
        monkeypatch.setattr(main, "settings", SimpleNamespace(github_webhook_secret="secret"))
        payload = b"payload"
        raw = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
        assert main.verify_github_signature(payload, raw) is False  # missing sha256=
