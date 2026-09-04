"""Tests for ``get_pr_diff`` (git subprocess wrapper)."""

from unittest.mock import Mock, patch

import pytest

import app.services.diff_extractor as de


class TestGetPrDiff:
    """Tests for get_pr_diff with a mocked subprocess."""

    def _sample_diff(self) -> str:
        return (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )

    def test_success_parses_diff(self) -> None:
        proc = Mock(returncode=0, stdout=self._sample_diff(), stderr="")
        with patch("app.services.diff_extractor.subprocess.run", return_value=proc) as m:
            result = de.get_pr_diff("/repo", "base", "head")
        m.assert_called_once()
        assert result == [
            {
                "filename": "app.py",
                "status": "modified",
                "diff_text": "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n",
            }
        ]

    def test_binary_files_filtered(self) -> None:
        diff = (
            "diff --git a/image.png b/image.png\n"
            "Binary files a/image.png and b/image.png differ\n"
            + self._sample_diff()
        )
        proc = Mock(returncode=0, stdout=diff, stderr="")
        with patch("app.services.diff_extractor.subprocess.run", return_value=proc):
            result = de.get_pr_diff("/repo", "base", "head")
        assert [f["filename"] for f in result] == ["app.py"]

    def test_timeout_raises_runtime_error(self) -> None:
        import subprocess

        with patch(
            "app.services.diff_extractor.subprocess.run",
            side_effect=subprocess.TimeoutExpired("git diff", 60),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                de.get_pr_diff("/repo", "base", "head")

    def test_nonzero_exit_raises_runtime_error(self) -> None:
        proc = Mock(returncode=1, stdout="", stderr="fatal: bad revision")
        with patch("app.services.diff_extractor.subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="git diff failed"):
                de.get_pr_diff("/repo", "base", "head")

    def test_large_diff_truncated(self) -> None:
        lines = ["@@ -0,0 +1 @@\n", "+x\n"] * 3000
        diff = "diff --git a/big.py b/big.py\n" + "".join(lines)
        proc = Mock(returncode=0, stdout=diff, stderr="")
        with patch("app.services.diff_extractor.subprocess.run", return_value=proc):
            result = de.get_pr_diff("/repo", "base", "head")
        assert len(result) == 1
        assert "# [TRUNCATED" in result[0]["diff_text"]
