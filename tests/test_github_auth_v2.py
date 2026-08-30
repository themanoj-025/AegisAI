"""Tests for GitHub auth service (installation token)."""



from app.services.github_auth import verify_webhook_signature


class TestVerifyWebhookSignatureV2:
    """Additional tests for webhook signature verification."""

    def test_hex_digest_format(self) -> None:
        import hashlib
        import hmac
        payload = b"test payload"
        secret = "test_secret"
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, secret) is True

    def test_wrong_secret(self) -> None:
        import hashlib
        import hmac
        payload = b"test payload"
        sig = "sha256=" + hmac.new(b"wrong_secret", payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, "correct_secret") is False

    def test_empty_payload(self) -> None:
        import hashlib
        import hmac
        secret = "test"
        sig = "sha256=" + hmac.new(secret.encode(), b"", hashlib.sha256).hexdigest()
        assert verify_webhook_signature(b"", sig, secret) is True
