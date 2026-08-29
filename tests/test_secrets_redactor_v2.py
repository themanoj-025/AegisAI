"""Tests for secrets redactor service."""


from app.services.secrets_redactor import redact_secrets


class TestRedactSecrets:
    """Tests for redact_secrets."""

    def test_redacts_api_keys(self):
        text = "api_key=sk-1234567890abcdef"
        result = redact_secrets(text)
        assert "sk-1234567890abcdef" not in result
        assert "REDACTED" in result

    def test_redacts_passwords(self):
        text = "password=mysecret123"
        result = redact_secrets(text)
        assert "mysecret123" not in result

    def test_no_secrets_unchanged(self):
        text = "This is safe text"
        result = redact_secrets(text)
        assert "safe" in result

    def test_empty_string(self):
        result = redact_secrets("")
        assert result == ""
