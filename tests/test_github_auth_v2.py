"""Tests for GitHub auth service (installation token)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.github_auth import verify_webhook_signature


class TestVerifyWebhookSignatureV2:
    """Additional tests for webhook signature verification."""

    def test_hex_digest_format(self):
        import hashlib
        import hmac
        payload = b"test payload"
        secret = "test_secret"
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, secret) is True

    def test_wrong_secret(self):
        import hashlib
        import hmac
        payload = b"test payload"
        sig = "sha256=" + hmac.new(b"wrong_secret", payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, "correct_secret") is False

    def test_empty_payload(self):
        import hashlib
        import hmac
        secret = "test"
        sig = "sha256=" + hmac.new(secret.encode(), b"", hashlib.sha256).hexdigest()
        assert verify_webhook_signature(b"", sig, secret) is True
