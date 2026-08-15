"""Tests for app.services.secrets_redactor — secret pattern detection and redaction."""

from app.services.secrets_redactor import redact_secrets


class TestRedactSecrets:
    def test_api_key_assignment(self):
        text = 'api_key = "sk-1234567890abcdef1234"'
        result = redact_secrets(text)
        assert "sk-1234567890abcdef1234" not in result
        assert "[REDACTED_SECRET]" in result

    def test_aws_access_key(self):
        text = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
        result = redact_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED_SECRET]" in result

    def test_private_key_block(self):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA0...\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact_secrets(text)
        assert "BEGIN RSA PRIVATE KEY" not in result
        assert "[REDACTED_SECRET]" in result

    def test_secret_assignment(self):
        text = 'secret = "aB3dE5fG7hI9jK1lM3nO"'
        result = redact_secrets(text)
        assert "aB3dE5fG7hI9jK1lM3nO" not in result
        assert "[REDACTED_SECRET]" in result

    def test_token_assignment(self):
        text = 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef12"'
        result = redact_secrets(text)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef12" not in result

    def test_password_assignment(self):
        text = 'password = "SuperSecretPass123!"'
        result = redact_secrets(text)
        assert "SuperSecretPass123!" not in result

    def test_no_secrets_unchanged(self):
        text = "x = 1\ny = 'hello'\nprint(x + y)"
        result = redact_secrets(text)
        assert result == text

    def test_short_strings_not_redacted(self):
        # Strings shorter than 16 chars should not be matched
        text = 'api_key = "short"'
        result = redact_secrets(text)
        assert "short" in result  # Not redacted — too short

    def test_multiple_secrets(self):
        text = (
            'api_key = "1234567890abcdef1234"\n'
            'secret = "abcdef1234567890abcd"\n'
            "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
        )
        result = redact_secrets(text)
        # Should have at least 2 redactions
        assert result.count("[REDACTED_SECRET]") >= 2

    def test_mixed_content(self):
        text = (
            "# Normal comment\n"
            "def hello():\n"
            "    api_key = '1234567890abcdef1234'\n"
            "    return 'ok'\n"
        )
        result = redact_secrets(text)
        assert "def hello():" in result
        assert "return 'ok'" in result
        assert "1234567890abcdef1234" not in result

    def test_colon_separator(self):
        text = 'api_key: "1234567890abcdef1234"'
        result = redact_secrets(text)
        assert "1234567890abcdef1234" not in result
