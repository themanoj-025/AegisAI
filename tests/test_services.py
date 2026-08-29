"""Tests for AegisAI services: secrets redaction, diff extraction, circuit breaker."""

import pytest

from app.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from app.services.diff_extractor import _is_noise_file, _parse_diff_output
from app.services.secrets_redactor import redact_secrets

# ── Secrets Redactor ────────────────────────────────────────────────────────


class TestRedactSecrets:
    """Tests for the secrets redaction service."""

    def test_no_secrets_unchanged(self) -> None:
        text = "def hello():\n    return 'world'"
        assert redact_secrets(text) == text

    def test_api_key_redacted(self) -> None:
        text = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"'
        result = redact_secrets(text)
        assert "sk-abcde" not in result
        assert "[REDACTED_SECRET]" in result

    def test_aws_key_redacted(self) -> None:
        text = "AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(text)
        assert "AKIA" not in result
        assert "[REDACTED_SECRET]" in result

    def test_private_key_redacted(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        result = redact_secrets(text)
        assert "BEGIN" not in result
        assert "[REDACTED_SECRET]" in result

    def test_password_assignment_redacted(self) -> None:
        text = 'password = "supersecret12345678"'
        result = redact_secrets(text)
        assert "supersecret" not in result
        assert "[REDACTED_SECRET]" in result

    def test_token_assignment_redacted(self) -> None:
        text = 'auth_token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"'
        result = redact_secrets(text)
        assert "ghp_" not in result
        assert "[REDACTED_SECRET]" in result

    def test_bearer_token_redacted(self) -> None:
        text = 'bearer = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"'
        result = redact_secrets(text)
        assert "eyJhbGci" not in result

    def test_short_string_not_redacted(self) -> None:
        text = 'api_key = "short"'
        result = redact_secrets(text)
        assert result == text

    def test_multiple_secrets(self) -> None:
        text = (
            'api_key = "abcdefghijklmnopqrstuvwxyz1234"\n'
            "AWS_KEY = AKIAIOSFODNN7EXAMPLE\n"
            'password = "mysecretpassword12345"'
        )
        result = redact_secrets(text)
        assert result.count("[REDACTED_SECRET]") == 3

    def test_empty_string(self) -> None:
        assert redact_secrets("") == ""


# ── Diff Extractor ──────────────────────────────────────────────────────────


class TestIsNoiseFile:
    """Tests for the noise file filter."""

    def test_package_lock(self) -> None:
        assert _is_noise_file("package-lock.json")

    def test_yarn_lock(self) -> None:
        assert _is_noise_file("yarn.lock")

    def test_poetry_lock(self) -> None:
        assert _is_noise_file("poetry.lock")

    def test_min_js(self) -> None:
        assert _is_noise_file("bundle.min.js")

    def test_node_modules(self) -> None:
        assert _is_noise_file("node_modules/package/index.js")

    def test_vendor_dir(self) -> None:
        assert _is_noise_file("vendor/some/file.py")

    def test_pycache(self) -> None:
        assert _is_noise_file("__pycache__/module.cpython-312.pyc")

    def test_normal_file_not_noise(self) -> None:
        assert not _is_noise_file("src/main.py")

    def test_test_file_not_noise(self) -> None:
        assert not _is_noise_file("tests/test_api.py")


class TestParseDiffOutput:
    """Tests for the git diff parser."""

    def test_single_modified_file(self) -> None:
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "+import sys\n"
            " def main():\n"
            "     pass\n"
        )
        files = _parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["filename"] == "src/main.py"
        assert files[0]["status"] == "modified"
        assert "import sys" in files[0]["diff_text"]

    def test_new_file(self) -> None:
        diff = (
            "diff --git a/new.txt b/new.txt\n"
            "new file mode 100644\n"
            "index 0000000..abc1234\n"
            "--- /dev/null\n"
            "+++ b/new.txt\n"
            "@@ -0,0 +1 @@\n"
            "+hello world\n"
        )
        files = _parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "added"

    def test_deleted_file(self) -> None:
        diff = (
            "diff --git a/old.txt b/old.txt\n"
            "deleted file mode 100644\n"
            "index abc1234..0000000\n"
            "--- a/old.txt\n"
            "+++ /dev/null\n"
        )
        files = _parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "deleted"

    def test_renamed_file(self) -> None:
        diff = (
            "diff --git a/old.py b/new.py\n"
            "rename from old.py\n"
            "rename to new.py\n"
            "--- a/old.py\n"
            "+++ b/new.py\n"
        )
        files = _parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "renamed"

    def test_noise_files_filtered(self) -> None:
        diff = (
            "diff --git a/package-lock.json b/package-lock.json\n"
            "--- a/package-lock.json\n"
            "+++ b/package-lock.json\n"
            "@@ -1,2 +1,3 @@\n"
            "+new line\n"
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,2 +1,3 @@\n"
            "+import sys\n"
        )
        files = _parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["filename"] == "src/main.py"

    def test_multiple_files(self) -> None:
        diff = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1 +1,2 @@\n"
            "+line1\n"
            "diff --git b/b.py b/b.py\n"
            "--- a/b.py\n"
            "+++ b/b.py\n"
            "@@ -1 +1,2 @@\n"
            "+line2\n"
        )
        files = _parse_diff_output(diff)
        assert len(files) == 2

    def test_empty_diff(self) -> None:
        assert _parse_diff_output("") == []


# ── Circuit Breaker ─────────────────────────────────────────────────────────


class TestCircuitBreaker:
    """Tests for the circuit breaker state machine."""

    def test_initial_state_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_is_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.is_open()

    def test_context_manager_closes_on_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=5)
        with cb:
            pass  # success
        assert cb.state == CircuitState.CLOSED

    def test_context_manager_records_failure(self) -> None:
        cb = CircuitBreaker(failure_threshold=5)
        with pytest.raises(ValueError), cb:
            raise ValueError("test")
        assert cb._failure_count == 1

    def test_context_manager_open_raises(self) -> None:
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError), cb:
            pass

    def test_success_count_increments(self) -> None:
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_success()
        cb.record_success()
        assert cb._success_count == 2

    def test_recovery_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        import time
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_opens_on_failure(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        import time
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
