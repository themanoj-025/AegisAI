"""GitHub PR review posting service.

Posts AegisAI's findings back to GitHub as a proper PR review with
inline comments where possible, and a summary comment at the top.
"""

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger("aegisai")

_GITHUB_API_BASE = "https://api.github.com"


def _build_review_body(
    findings: list[dict],
    diff_files: list[dict],
) -> dict[str, Any]:
    """Build the GitHub PR review payload from findings.

    Constructs a summary comment and inline comments. Findings that can't
    be confidently mapped to a line are included only in the summary.

    Args:
        findings: List of finding dicts from the security agent.
        diff_files: The original diff file list (for line number mapping).

    Returns:
        A dict suitable for POST to /repos/{owner}/{repo}/pulls/{number}/reviews
    """
    # Severity breakdown
    severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        sev = f.get("severity", "low").lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Build summary
    if findings:
        summary_parts = [
            f"## AegisAI Security Review",
            f"",
            f"Found **{len(findings)}** potential issue(s):",
            f"",
        ]
        if severity_counts.get("critical"):
            summary_parts.append(f"- 🔴 Critical: {severity_counts['critical']}")
        if severity_counts.get("high"):
            summary_parts.append(f"- 🟠 High: {severity_counts['high']}")
        if severity_counts.get("medium"):
            summary_parts.append(f"- 🟡 Medium: {severity_counts['medium']}")
        if severity_counts.get("low"):
            summary_parts.append(f"- 🟢 Low: {severity_counts['low']}")
        summary_parts.append(f"")
        summary_parts.append(f"*This is an automated review by AegisAI.*")
    else:
        summary_parts = [
            f"## AegisAI Security Review",
            f"",
            f"✅ **No security issues found.**",
            f"",
            f"*This is an automated review by AegisAI.*",
        ]

    summary_body = "\n".join(summary_parts)

    # Build inline comments for findings with high confidence
    comments = []
    summary_only_findings = []

    for finding in findings:
        if finding.get("low_confidence", True):
            summary_only_findings.append(finding)
            continue

        file_name = finding.get("file", "")
        line_hint = finding.get("line_hint", "")

        # Try to map line_hint to a line number in the diff
        line_number = _map_hint_to_line(line_hint, file_name, diff_files)

        comment_body = (
            f"**{finding.get('severity', 'unknown').upper()}** | "
            f"*{finding.get('category', 'unknown')}*\n\n"
            f"{finding.get('description', '')}\n\n"
            f"**Recommendation:** {finding.get('recommendation', '')}"
        )

        if line_number is not None:
            comments.append({
                "path": file_name,
                "line": line_number,
                "body": comment_body,
            })
        else:
            summary_only_findings.append(finding)

    # Add summary-only findings to the body
    if summary_only_findings:
        summary_parts.append(f"\n---\n### Issues without line attribution")
        for i, f in enumerate(summary_only_findings, 1):
            summary_parts.append(
                f"\n**{i}. [{f.get('severity', 'unknown').upper()}] "
                f"{f.get('category', 'unknown')} — {f.get('file', 'unknown')}**"
                f"\n{f.get('description', '')}"
                f"\n*Recommendation:* {f.get('recommendation', '')}"
            )
        summary_body = "\n".join(summary_parts)

    return {
        "body": summary_body,
        "event": "COMMENT",
        "comments": comments,
    }


def _map_hint_to_line(line_hint: str, filename: str, diff_files: list[dict]) -> int | None:
    """Try to map a line_hint to a line number within the diff.

    Searches for the line_hint text in the file's diff hunk and returns
    the line number if found. Uses the diff's hunk header (@@ ... @@)
    to compute the target line number.

    This is a best-effort mapping — if it fails, the finding is included
    in the summary body instead.
    """
    if not line_hint:
        return None

    # Find the file's diff text
    file_diff = ""
    for f in diff_files:
        if f["filename"] == filename:
            file_diff = f["diff_text"]
            break

    if not file_diff:
        return None

    # Parse unified diff hunk headers to find line numbers
    # Format: @@ -start,count +start,count @@
    lines = file_diff.splitlines()

    target_line = 0
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            # Parse the hunk header
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                target_line = int(match.group(1))

        # Check if this line (minus the diff prefix) matches the hint
        if line.startswith("+") or line.startswith(" "):
            actual_line = line[1:] if line.startswith("+") else line[1:]
            if line_hint in actual_line or actual_line in line_hint:
                return target_line

        # Advance line counter for context and added lines
        if line.startswith("+") or line.startswith(" "):
            target_line += 1

    return None


def post_review(
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    findings: list[dict],
    installation_token: str,
    diff_files: list[dict] | None = None,
) -> dict[str, Any]:
    """Post AegisAI's findings as a GitHub PR review.

    Uses GitHub's "Create a review for a pull request" REST API.
    Posts as a COMMENT event (not REQUEST_CHANGES or APPROVE).

    Args:
        repo_full_name: "owner/repo" format.
        pr_number: Pull request number.
        head_sha: The head commit SHA.
        findings: List of finding dicts from the security agent.
        installation_token: GitHub App installation access token.
        diff_files: The diff file list (for line number mapping), optional.

    Returns:
        The GitHub API response JSON.

    Raises:
        RuntimeError: If the API call fails.
    """
    if diff_files is None:
        diff_files = []

    # Build the review payload
    review_data = _build_review_body(findings, diff_files)

    url = f"{_GITHUB_API_BASE}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {installation_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    logger.info(
        "Posting review to %s PR #%d: %d findings, %d inline comments",
        repo_full_name,
        pr_number,
        len(findings),
        len(review_data.get("comments", [])),
    )

    with httpx.Client() as client:
        response = client.post(
            url,
            headers=headers,
            content=json.dumps(review_data),
        )

    if response.status_code == 422:
        # Common issue: line number mapping is wrong or diff position is stale
        logger.error(
            "GitHub review API returned 422 for %s PR #%d: %s",
            repo_full_name,
            pr_number,
            response.text,
        )
        # Fall back to summary-only review (no inline comments)
        logger.info("Falling back to summary-only review for %s PR #%d", repo_full_name, pr_number)
        fallback_data = {
            "body": review_data["body"],
            "event": "COMMENT",
            "comments": [],
        }
        with httpx.Client() as client:
            fallback_response = client.post(
                url,
                headers=headers,
                content=json.dumps(fallback_data),
            )
        if fallback_response.status_code not in (200, 201):
            raise RuntimeError(
                f"GitHub review API failed (HTTP {fallback_response.status_code}) "
                f"for {repo_full_name} PR #{pr_number}: {fallback_response.text}"
            )
        return fallback_response.json()

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"GitHub review API failed (HTTP {response.status_code}) "
            f"for {repo_full_name} PR #{pr_number}: {response.text}"
        )

    result = response.json()
    review_id = result.get("id", "unknown")
    logger.info(
        "Successfully posted review (ID: %s) to %s PR #%d",
        review_id,
        repo_full_name,
        pr_number,
    )

    return result
