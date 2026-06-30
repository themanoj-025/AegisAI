"""GitHub App authentication service.

Generates JWTs signed with the App's private key and exchanges them
for short-lived installation access tokens.
"""

import logging
import time
from pathlib import Path

import httpx
from jwt import PyJWTError

from app.config import settings

logger = logging.getLogger("aegisai")

# Cache for installation tokens: {installation_id: (token, expiry_timestamp)}
_token_cache: dict[int, tuple[str, float]] = {}

# Safety buffer: treat tokens as expired 2 minutes early
_EXPIRY_BUFFER_SECONDS = 120


def _read_private_key() -> str:
    """Read the GitHub App's private key from disk."""
    key_path = Path(settings.github_private_key_path)
    if not key_path.exists():
        raise FileNotFoundError(
            f"GitHub private key not found at {settings.github_private_key_path}. "
            "Set GITHUB_PRIVATE_KEY_PATH in your .env file."
        )
    return key_path.read_text()


def _generate_jwt() -> str:
    """Generate a signed JWT for GitHub App authentication.

    Returns a JWT signed with RS256 using the App's private key.
    The token is valid for a maximum of 10 minutes (per GitHub's limit).
    """
    import jwt

    private_key = _read_private_key()
    now = int(time.time())

    payload = {
        "iat": now - 60,  # issued 60s ago to allow for clock drift
        "exp": now + 600,  # expires in 10 minutes
        "iss": settings.github_app_id,
    }

    try:
        token = jwt.encode(payload, private_key, algorithm="RS256")
        return token
    except PyJWTError as e:
        raise RuntimeError(f"Failed to generate JWT: {e}") from e


def get_installation_token(installation_id: int) -> str:
    """Get a valid installation access token, using cache if available.

    Tokens last 1 hour from GitHub's side. We cache them in memory and
    check expiry before reuse, with a 2-minute safety buffer.
    """
    # Check cache
    if installation_id in _token_cache:
        cached_token, expiry = _token_cache[installation_id]
        if time.time() < (expiry - _EXPIRY_BUFFER_SECONDS):
            logger.debug("Using cached installation token for installation %d", installation_id)
            return cached_token
        logger.debug("Cached token for installation %d expired, fetching new one", installation_id)

    # Generate JWT and exchange for installation token
    jwt_token = _generate_jwt()

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    with httpx.Client() as client:
        response = client.post(url, headers=headers)

    if response.status_code == 401:
        raise PermissionError(
            f"GitHub API returned 401 for installation {installation_id}. "
            "Check your GITHUB_APP_ID and private key."
        )
    if response.status_code == 403:
        raise PermissionError(
            f"GitHub API returned 403 for installation {installation_id}. "
            "The App may not be installed on this account or lacks required permissions."
        )
    if response.status_code != 201:
        raise RuntimeError(
            f"Failed to get installation token (HTTP {response.status_code}): {response.text}"
        )

    data = response.json()
    token: str = data["token"]
    expires_at: str = data["expires_at"]

    # Parse expiry
    # GitHub returns ISO 8601 format: "2024-01-01T00:00:00Z"
    from datetime import datetime, timezone

    expiry_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    expiry_ts = expiry_dt.timestamp()

    # Cache the token
    _token_cache[installation_id] = (token, expiry_ts)
    logger.info(
        "Obtained new installation token for installation %d (expires at %s)",
        installation_id,
        expires_at,
    )

    return token
