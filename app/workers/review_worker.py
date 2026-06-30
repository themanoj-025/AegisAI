"""Background worker for processing PR review jobs.

This module contains the RQ job function that is enqueued by the webhook
handler. It handles: authentication, cloning, diff extraction, AI review,
and posting results back to GitHub.
"""

import logging

from app.agents.security_agent import run_security_agent
from app.services.diff_extractor import get_pr_diff
from app.services.github_auth import get_installation_token
from app.services.github_reviewer import post_review
from app.services.repo_manager import cleanup_workspace, clone_pr_repo

logger = logging.getLogger("aegisai")


def run_review_job(
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    clone_url: str,
    installation_id: int,
) -> None:
    """Process a single PR review job.

    Called by the RQ worker when a job is dequeued. This function runs
    in a background process and should NOT be called from the webhook
    handler directly.
    """
    local_path = None
    try:
        logger.info(
            "Starting review job for %s PR #%d (head: %s)",
            repo_full_name,
            pr_number,
            head_sha[:7],
        )

        # Step 1: Get installation token
        installation_token = get_installation_token(installation_id)

        # Step 2: Clone the repository
        local_path = clone_pr_repo(
            clone_url, installation_token, head_sha, pr_number, repo_full_name
        )

        # Step 3: Extract the diff
        logger.info("Extracting diff for %s PR #%d", repo_full_name, pr_number)
        pr_files = get_pr_diff(local_path, base_sha, head_sha)
        logger.info(
            "Extracted %d changed files for %s PR #%d",
            len(pr_files),
            repo_full_name,
            pr_number,
        )

        # Step 4: Run the security agent
        logger.info("Running security agent for %s PR #%d", repo_full_name, pr_number)
        findings = run_security_agent(pr_files)
        logger.info(
            "Security agent found %d findings for %s PR #%d",
            len(findings),
            repo_full_name,
            pr_number,
        )

        # Log findings clearly
        if findings:
            logger.info("=== Findings for %s PR #%d ===", repo_full_name, pr_number)
            for i, finding in enumerate(findings, 1):
                logger.info(
                    "  %d. [%s] [%s] %s — %s",
                    i,
                    finding.get("severity", "unknown").upper(),
                    finding.get("category", "unknown"),
                    finding.get("file", "unknown"),
                    finding.get("description", "")[:120],
                )
            logger.info("=== End of findings ===")
        else:
            logger.info(
                "No findings for %s PR #%d — clean PR",
                repo_full_name,
                pr_number,
            )

        # Step 5: Post review to GitHub
        post_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            head_sha=head_sha,
            findings=findings,
            installation_token=installation_token,
            diff_files=pr_files,
        )
        logger.info(
            "Review job complete for %s PR #%d — results posted to GitHub",
            repo_full_name,
            pr_number,
        )

    except Exception as e:
        logger.error(
            "Review job failed for %s PR #%d: %s",
            repo_full_name,
            pr_number,
            e,
            exc_info=True,
        )
        raise
    finally:
        # Always clean up the workspace, even on failure
        if local_path:
            cleanup_workspace(local_path)
            logger.info(
                "Workspace cleaned up for %s PR #%d",
                repo_full_name,
                pr_number,
            )
