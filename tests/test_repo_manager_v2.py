"""Tests for repo manager (clone logic)."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.repo_manager import clone_pr_repo

pytestmark = pytest.mark.integration



class TestClonePrRepo:
    """Tests for clone_pr_repo."""

    @patch("app.services.repo_manager.subprocess.run")
    def test_successful_clone(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        # Mock the checkout too
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # clone
            MagicMock(returncode=0, stderr=""),  # checkout
        ]
        with patch("app.services.repo_manager.Path.mkdir"):
            with patch("app.services.repo_manager.Path.resolve", return_value="/tmp/test"):
                result = clone_pr_repo(
                    clone_url="https://github.com/owner/repo.git",
                    installation_token="ghp_test",
                    head_sha="abc123",
                    pr_number=1,
                    repo_full_name="owner/repo",
                )
                assert result is not None

    @patch("app.services.repo_manager.subprocess.run")
    def test_clone_failure_raises(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: repository not found")
        with patch("app.services.repo_manager.Path.mkdir"):
            with patch("app.services.repo_manager.Path.resolve", return_value="/tmp/test"):
                with pytest.raises(RuntimeError, match="Git clone failed"):
                    clone_pr_repo(
                        clone_url="https://github.com/owner/repo.git",
                        installation_token="ghp_test",
                        head_sha="abc123",
                        pr_number=1,
                        repo_full_name="owner/repo",
                    )

    @patch("app.services.repo_manager.subprocess.run")
    def test_checkout_failure_raises(self, mock_run) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # clone succeeds
            MagicMock(returncode=1, stderr="fatal: bad object abc123"),  # checkout fails
        ]
        with patch("app.services.repo_manager.Path.mkdir"):
            with patch("app.services.repo_manager.Path.resolve", return_value="/tmp/test"):
                with pytest.raises(RuntimeError, match="checkout.*failed"):
                    clone_pr_repo(
                        clone_url="https://github.com/owner/repo.git",
                        installation_token="ghp_test",
                        head_sha="abc123",
                        pr_number=1,
                        repo_full_name="owner/repo",
                    )
