"""Tests for app.main — webhook signature verification, health check, and webhook handling."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app, verify_github_signature

client = TestClient(app)


# ── verify_github_signature ───────────────────────────────────────────


class TestVerifyGithubSignature:
    @patch("app.main.settings")
    def test_valid_signature(self, mock_settings):
        mock_settings.github_webhook_secret = "test-secret"
        payload = b'{"action": "opened"}'
        sig = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        header = f"sha256={sig}"
        assert verify_github_signature(payload, header) is True

    @patch("app.main.settings")
    def test_invalid_signature(self, mock_settings):
        mock_settings.github_webhook_secret = "test-secret"
        payload = b'{"action": "opened"}'
        assert verify_github_signature(payload, "sha256=bad_signature") is False

    @patch("app.main.settings")
    def test_missing_header(self, mock_settings):
        assert verify_github_signature(b"payload", None) is False

    @patch("app.main.settings")
    def test_empty_header(self, mock_settings):
        assert verify_github_signature(b"payload", "") is False

    @patch("app.main.settings")
    def test_missing_sha256_prefix(self, mock_settings):
        assert verify_github_signature(b"payload", "abc123") is False


# ── Health endpoint ───────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ── Webhook endpoint ──────────────────────────────────────────────────


class TestGithubWebhook:
    @patch("app.main.acquire_review_lock")
    @patch("app.main.get_queue")
    @patch("app.main.settings")
    def test_webhook_ignored_event_type(self, mock_settings, mock_queue, mock_lock):
        mock_settings.github_webhook_secret = "test-secret"
        payload = json.dumps({"action": "opened"}).encode()
        sig = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": f"sha256={sig}",
                "X-GitHub-Event": "push",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    @patch("app.main.acquire_review_lock")
    @patch("app.main.get_queue")
    @patch("app.main.settings")
    def test_webhook_ignored_action(self, mock_settings, mock_queue, mock_lock):
        mock_settings.github_webhook_secret = "test-secret"
        payload = json.dumps({"action": "closed", "pull_request": {}, "repository": {}}).encode()
        sig = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": f"sha256={sig}",
                "X-GitHub-Event": "pull_request",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    @patch("app.main.settings")
    def test_webhook_invalid_signature_rejected(self, mock_settings):
        mock_settings.github_webhook_secret = "test-secret"
        response = client.post(
            "/webhooks/github",
            content=b'{"action":"opened"}',
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "pull_request",
            },
        )
        assert response.status_code == 401

    @patch("app.main.acquire_review_lock", return_value=False)
    @patch("app.main.settings")
    def test_webhook_deduplicated(self, mock_settings, mock_lock):
        mock_settings.github_webhook_secret = "test-secret"
        pr_payload = {
            "action": "opened",
            "pull_request": {
                "number": 1,
                "head": {"sha": "abc123"},
                "base": {"sha": "def456"},
            },
            "repository": {"full_name": "org/repo", "clone_url": "https://github.com/org/repo.git"},
            "installation": {"id": 12345},
        }
        payload = json.dumps(pr_payload).encode()
        sig = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": f"sha256={sig}",
                "X-GitHub-Event": "pull_request",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deduplicated"

    @patch("app.main.acquire_review_lock", return_value=True)
    @patch("app.main.get_queue")
    @patch("app.main.settings")
    def test_webhook_enqueues_review(self, mock_settings, mock_queue, mock_lock):
        mock_settings.github_webhook_secret = "test-secret"
        mock_q = MagicMock()
        mock_queue.return_value = mock_q
        pr_payload = {
            "action": "opened",
            "pull_request": {
                "number": 1,
                "head": {"sha": "abc123"},
                "base": {"sha": "def456"},
            },
            "repository": {"full_name": "org/repo", "clone_url": "https://github.com/org/repo.git"},
            "installation": {"id": 12345},
        }
        payload = json.dumps(pr_payload).encode()
        sig = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": f"sha256={sig}",
                "X-GitHub-Event": "pull_request",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "received"
        mock_q.enqueue.assert_called_once()

    def test_security_headers_present(self):
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "Referrer-Policy" in response.headers
