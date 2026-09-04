"""Tests for the RQ review worker job function."""

from unittest.mock import patch

import pytest

from app.workers.review_worker import run_review_job

ARGS = ("owner/repo", 7, "a" * 40, "b" * 40, "https://github.com/owner/repo.git", 42)


class TestRunReviewJob:
    def test_success_posts_review_and_cleans_up(self) -> None:
        with (
            patch("app.workers.review_worker.get_installation_token", return_value="tok") as m_token,
            patch("app.workers.review_worker.clone_pr_repo", return_value="/tmp/ws") as m_clone,
            patch("app.workers.review_worker.get_pr_diff", return_value=[{"filename": "a.py"}]) as m_diff,
            patch("app.workers.review_worker.run_security_agent", return_value=[]) as m_agent,
            patch("app.workers.review_worker.post_review") as m_post,
            patch("app.workers.review_worker.cleanup_workspace") as m_cleanup,
        ):
            run_review_job(*ARGS)

        m_token.assert_called_once_with(42)
        m_clone.assert_called_once()
        m_diff.assert_called_once()
        m_agent.assert_called_once_with([{"filename": "a.py"}])
        m_post.assert_called_once()
        m_cleanup.assert_called_once_with("/tmp/ws")

    def test_failure_re_raises_and_cleans_up(self) -> None:
        with (
            patch(
                "app.workers.review_worker.get_installation_token",
                side_effect=RuntimeError("no token"),
            ),
            patch("app.workers.review_worker.cleanup_workspace") as m_cleanup,
        ):
            with pytest.raises(RuntimeError, match="no token"):
                run_review_job(*ARGS)
        m_cleanup.assert_not_called()  # workspace never created

    def test_failure_after_clone_cleans_up_workspace(self) -> None:
        with (
            patch("app.workers.review_worker.get_installation_token", return_value="tok"),
            patch("app.workers.review_worker.clone_pr_repo", return_value="/tmp/ws"),
            patch("app.workers.review_worker.get_pr_diff", side_effect=RuntimeError("diff failed")),
            patch("app.workers.review_worker.cleanup_workspace") as m_cleanup,
        ):
            with pytest.raises(RuntimeError, match="diff failed"):
                run_review_job(*ARGS)
        m_cleanup.assert_called_once_with("/tmp/ws")
