"""Repository cloning and workspace management.

Handles cloning PR repositories into a local workspace directory for
analysis, and cleaning up after review is complete.
"""

import logging
import os
import random
import shutil
import string
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger("aegisai")


def _random_suffix(length: int = 8) -> str:
    """Generate a short random alphanumeric suffix for unique workspace paths."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def _build_authenticated_clone_url(clone_url: str, installation_token: str) -> str:
    """Inject an installation token into a GitHub clone URL.

    Transforms: https://github.com/owner/repo.git
    Into:       https://x-access-token:{token}@github.com/owner/repo.git
    """
    return clone_url.replace("https://", f"https://x-access-token:{installation_token}@", 1)


def clone_pr_repo(
    clone_url: str,
    installation_token: str,
    head_sha: str,
    pr_number: int,
    repo_full_name: str,
) -> str:
    """Clone a PR's repository at the specified head SHA.

    Returns the local path to the cloned repository.

    Uses a shallow clone (--depth=50) to keep it fast. After cloning,
    checks out the exact head_sha. The workspace path is namespaced by
    repo and PR number with a random suffix to avoid collisions.
    """
    # Parse owner/repo from full_name
    repo_owner, repo_name = repo_full_name.split("/", 1)

    # Build local workspace path
    workspace_base = Path(settings.workspace_dir)
    clone_path = workspace_base / f"{repo_owner}_{repo_name}" / f"pr_{pr_number}_{_random_suffix()}"
    clone_path = clone_path.resolve()

    # Ensure parent directory exists
    clone_path.parent.mkdir(parents=True, exist_ok=True)

    # Build authenticated URL
    auth_url = _build_authenticated_clone_url(clone_url, installation_token)

    try:
        logger.info(
            "Cloning repo %s (PR #%d) into %s",
            repo_full_name,
            pr_number,
            clone_path,
        )

        # Shallow clone
        result = subprocess.run(
            ["git", "clone", "--depth=50", auth_url, str(clone_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Git clone failed for {repo_full_name} (PR #{pr_number}): {result.stderr.strip()}"
            )

        # Checkout the head SHA
        logger.debug("Checking out head SHA %s for %s PR #%d", head_sha, repo_full_name, pr_number)
        checkout_result = subprocess.run(
            ["git", "-C", str(clone_path), "checkout", head_sha],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if checkout_result.returncode != 0:
            raise RuntimeError(
                f"Git checkout of {head_sha} failed for {repo_full_name} (PR #{pr_number}): "
                f"{checkout_result.stderr.strip()}"
            )

        logger.info(
            "Successfully cloned and checked out %s (PR #%d) at %s — path: %s",
            repo_full_name,
            pr_number,
            head_sha[:7],
            clone_path,
        )

        return str(clone_path)

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Git clone timed out for {repo_full_name} (PR #{pr_number})"
        )
    except Exception:
        # Clean up on failure
        if clone_path.exists():
            shutil.rmtree(clone_path, ignore_errors=True)
        raise


def cleanup_workspace(path: str) -> None:
    """Recursively delete a workspace directory after review is complete."""
    if not path or not os.path.exists(path):
        return

    try:
        shutil.rmtree(path)
        logger.debug("Cleaned up workspace: %s", path)
    except OSError as e:
        logger.warning("Failed to clean up workspace %s: %s", path, e)
