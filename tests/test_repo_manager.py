import pytest

pytestmark = pytest.mark.integration

"""Tests for repository cloning and workspace management."""

import os
import tempfile

from app.services.repo_manager import _build_authenticated_clone_url, _random_suffix, cleanup_workspace


class TestRandomSuffix:
    """Tests for _random_suffix."""

    def test_default_length(self) -> None:
        suffix = _random_suffix()
        assert len(suffix) == 8

    def test_custom_length(self) -> None:
        suffix = _random_suffix(12)
        assert len(suffix) == 12

    def test_alphanumeric(self) -> None:
        suffix = _random_suffix()
        assert suffix.isalnum()
        assert suffix.islower()


class TestBuildAuthenticatedCloneUrl:
    """Tests for _build_authenticated_clone_url."""

    def test_injects_token(self) -> None:
        url = "https://github.com/owner/repo.git"
        result = _build_authenticated_clone_url(url, "ghp_test123")
        assert "x-access-token:ghp_test123" in result
        assert result.startswith("https://")

    def test_preserves_path(self) -> None:
        url = "https://github.com/owner/repo.git"
        result = _build_authenticated_clone_url(url, "token")
        assert "/owner/repo.git" in result


class TestCleanupWorkspace:
    """Tests for cleanup_workspace."""

    def test_cleanup_existing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "workspace")
            os.makedirs(test_path)
            with open(os.path.join(test_path, "file.txt"), "w") as f:
                f.write("test")
            cleanup_workspace(test_path)
            assert not os.path.exists(test_path)

    def test_cleanup_nonexistent_dir(self) -> None:
        cleanup_workspace("/nonexistent/path/that/does/not/exist")

    def test_cleanup_empty_string(self) -> None:
        cleanup_workspace("")

    def test_cleanup_none(self) -> None:
        cleanup_workspace(None)
