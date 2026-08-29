"""Tests for GitHub authentication service."""

import hashlib
import hmac
import json

import pytest

from app.services.github_auth import _parse_event, verify_webhook_signature


class TestVerifyWebhookSignature:
    """Tests for webhook signature verification."""

    def test_valid_signature(self):
        payload = b'{"action": "opened"}'
        secret = "my_secret"
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        assert verify_webhook_signature(b"payload", "sha256=wrong", "secret") is False

    def test_empty_signature(self):
        assert verify_webhook_signature(b"payload", "", "secret") is False

    def test_none_signature(self):
        assert verify_webhook_signature(b"payload", None, "secret") is False


class TestParseEvent:
    """Tests for _parse_event."""

    def test_valid_json(self):
        payload = json.dumps({"action": "opened", "pull_request": {"number": 1}}).encode()
        result = _parse_event(payload)
        assert result["action"] == "opened"
        assert result["pull_request"]["number"] == 1

    def test_invalid_json(self):
        with pytest.raises(ValueError):
            _parse_event(b"not json")
