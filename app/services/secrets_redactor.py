"""Secrets redaction service.

Defense-in-depth measure: runs BEFORE any diff content is sent to an
LLM, replacing common secret patterns with placeholders. This is not
perfect detection — it's a best-effort filter to reduce the risk of
leaking credentials through the LLM pipeline.
"""

import logging
import re

logger = logging.getLogger("aegisai")

# Pattern for generic API key assignments
_RE_API_KEY = re.compile(
    r"""(
        (?i:api_key|apikey|api\.key)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]
    )""",
    re.VERBOSE,
)

# Pattern for AWS access keys
_RE_AWS_KEY = re.compile(r"(AKIA[0-9A-Z]{16})")

# Pattern for private key headers
_RE_PRIVATE_KEY = re.compile(
    r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----"
)

# Pattern for high-entropy strings assigned to sensitive variable names
_RE_SENSITIVE_ASSIGNMENT = re.compile(
    r"""(
        (?i:\b(?:secret|token|password|passwd|credential|auth_token|access_token
                  |refresh_token|api_secret|app_secret|client_secret|bearer
                  |private_key|ssh_key)\b)
        \s*[=:]\s*['\"][A-Za-z0-9_\-\.!@#$%^&*+=]{16,}['\"]
    )""",
    re.VERBOSE,
)


def redact_secrets(diff_text: str) -> str:
    """Redact common secret patterns from diff text.

    Replaces detected secrets with '[REDACTED_SECRET]' placeholder.
    Runs multiple regex patterns in sequence.

    Args:
        diff_text: The raw diff text to scan.

    Returns:
        The diff text with secrets replaced by placeholders.
    """
    original_length = len(diff_text)
    redacted = diff_text

    redacted = _RE_PRIVATE_KEY.sub("[REDACTED_SECRET]", redacted)
    redacted = _RE_AWS_KEY.sub("[REDACTED_SECRET]", redacted)
    redacted = _RE_API_KEY.sub("[REDACTED_SECRET]", redacted)
    redacted = _RE_SENSITIVE_ASSIGNMENT.sub("[REDACTED_SECRET]", redacted)

    if len(redacted) != original_length:
        logger.debug(
            "Secrets redactor: replaced %d chars with placeholders",
            original_length - len(redacted),
        )

    return redacted
