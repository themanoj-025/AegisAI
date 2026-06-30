"""Diff extraction service.

Runs `git diff` on a cloned repository and parses the output into
per-file structured data, filtering out noise files and applying
size limits.
"""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("aegisai")

# Patterns for files to skip
_NOISE_PATTERNS = re.compile(
    r"("
    r"package-lock\.json$"
    r"|yarn\.lock$"
    r"|poetry\.lock$"
    r"|pnpm-lock\.yaml$"
    r"|\.min\.js$"
    r"|\.min\.css$"
    r"|node_modules/"
    r"|vendor/"
    r"|dist/"
    r"|build/"
    r"|\.next/"
    r"|__pycache__/"
    r")",
    re.IGNORECASE,
)

_MAX_DIFF_LINES_PER_FILE = 4000
_MAX_TOTAL_FILES_WARN = 50


def _is_noise_file(filename: str) -> bool:
    """Check if a file should be skipped (lockfiles, minified, vendor, etc.)."""
    return bool(_NOISE_PATTERNS.search(filename))


def _parse_diff_output(diff_text: str) -> list[dict]:
    """Parse raw git diff output into per-file structured dicts.

    Returns a list of dicts with keys: filename, status, diff_text.
    """
    files: list[dict] = []
    current_file: dict | None = None
    current_diff_lines: list[str] = []

    for line in diff_text.splitlines(keepends=True):
        # New file header: diff --git a/path b/path
        if line.startswith("diff --git "):
            # Save previous file if any
            if current_file is not None:
                current_file["diff_text"] = "".join(current_diff_lines)
                if not _is_noise_file(current_file["filename"]):
                    files.append(current_file)
                current_file = None
                current_diff_lines = []

            # Parse the b/ path
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3][2:]  # Remove "b/" prefix
                current_file = {
                    "filename": b_path,
                    "status": "modified",  # Will be overridden below if different
                    "diff_text": "",
                }
            continue

        # New file indicator
        if line.startswith("new file mode "):
            if current_file:
                current_file["status"] = "added"
            continue

        # Deleted file indicator
        if line.startswith("deleted file mode "):
            if current_file:
                current_file["status"] = "deleted"
            continue

        # Renamed file
        if line.startswith("rename from "):
            if current_file:
                current_file["status"] = "renamed"
            continue

        # Binary files — mark and skip
        if line.startswith("Binary files "):
            if current_file:
                current_file["status"] = "binary"
            continue

        # Accumulate diff lines
        if current_file is not None:
            current_diff_lines.append(line)

    # Don't forget the last file
    if current_file is not None:
        current_file["diff_text"] = "".join(current_diff_lines)
        if not _is_noise_file(current_file["filename"]):
            files.append(current_file)

    return files


def get_pr_diff(repo_path: str, base_sha: str, head_sha: str) -> list[dict]:
    """Get the diff between two SHAs, parsed into per-file structures.

    Args:
        repo_path: Local path to the cloned repository.
        base_sha: The base commit SHA (typically the target branch).
        head_sha: The head commit SHA (typically the PR branch).

    Returns:
        A list of dicts, each containing:
            - filename: relative path of the changed file
            - status: "added", "modified", "deleted", or "renamed"
            - diff_text: the diff hunk text for this file

    Files matching noise patterns (lockfiles, minified, vendor) are
    automatically excluded. Diffs over 4000 lines are truncated.
    """
    try:
        result = subprocess.run(
            ["git", "diff", base_sha, head_sha, "--unified=3"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=repo_path,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git diff timed out for {repo_path}")

    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    diff_text = result.stdout
    files = _parse_diff_output(diff_text)

    # Apply size cutoffs and filter binary/skipped
    processed_files = []
    total_files = 0

    for f in files:
        if f["status"] == "binary":
            logger.debug("Skipping binary file: %s", f["filename"])
            continue

        total_files += 1
        lines = f["diff_text"].count("\n")

        if lines > _MAX_DIFF_LINES_PER_FILE:
            logger.warning(
                "Large diff truncated: %s (%d lines, max %d)",
                f["filename"],
                lines,
                _MAX_DIFF_LINES_PER_FILE,
            )
            # Truncate the diff text
            truncated_lines = f["diff_text"].splitlines(keepends=True)
            f["diff_text"] = "".join(truncated_lines[:_MAX_DIFF_LINES_PER_FILE])
            f["diff_text"] += (
                f"\n# [TRUNCATED: diff was {lines} lines, "
                f"showing first {_MAX_DIFF_LINES_PER_FILE}]\n"
            )

        processed_files.append(f)

    if total_files > _MAX_TOTAL_FILES_WARN:
        logger.warning(
            "Large PR detected: %d changed files after filtering noise — "
            "consider implementing rate/size limiting",
            total_files,
        )

    logger.info(
        "Extracted diff for %s: %d files (%d total changed before filtering)",
        repo_path,
        len(processed_files),
        total_files,
    )

    return processed_files
