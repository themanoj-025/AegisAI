"""Tests for app.services.diff_extractor — noise filtering, diff parsing, and structured output."""

import subprocess
from unittest.mock import MagicMock, patch

from app.services.diff_extractor import _is_noise_file, _parse_diff_output, get_pr_diff

# ── _is_noise_file ────────────────────────────────────────────────────


class TestIsNoiseFile:
    def test_lockfiles_detected(self):
        assert _is_noise_file("package-lock.json") is True
        assert _is_noise_file("yarn.lock") is True
        assert _is_noise_file("poetry.lock") is True
        assert _is_noise_file("pnpm-lock.yaml") is True

    def test_minified_files_detected(self):
        assert _is_noise_file("app.min.js") is True
        assert _is_noise_file("styles.min.css") is True

    def test_vendor_dirs_detected(self):
        assert _is_noise_file("node_modules/foo/index.js") is True
        assert _is_noise_file("vendor/baz.py") is True

    def test_build_dirs_detected(self):
        assert _is_noise_file("dist/bundle.js") is True
        assert _is_noise_file("build/app.py") is True
        assert _is_noise_file(".next/server/index.js") is True
        assert _is_noise_file("__pycache__/module.pyc") is True

    def test_normal_files_not_noise(self):
        assert _is_noise_file("src/app.py") is False
        assert _is_noise_file("README.md") is False
        assert _is_noise_file("tests/test_main.py") is False
        assert _is_noise_file("Dockerfile") is False

    def test_case_insensitive(self):
        assert _is_noise_file("PACKAGE-LOCK.JSON") is True
        assert _is_noise_file("Yarn.lock") is True
        assert _is_noise_file("NODE_MODULES/foo.js") is True


# ── _parse_diff_output ────────────────────────────────────────────────


class TestParseDiffOutput:
    def test_single_modified_file(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "+import sys\n"
            " print('hello')\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "src/app.py"
        assert result[0]["status"] == "modified"
        assert "import sys" in result[0]["diff_text"]

    def test_new_file(self):
        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "+print('new')\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "new.py"
        assert result[0]["status"] == "added"

    def test_deleted_file(self):
        diff = (
            "diff --git a/old.py b/old.py\n"
            "deleted file mode 100644\n"
            "--- a/old.py\n"
            "+++ /dev/null\n"
            "-print('old')\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "old.py"
        assert result[0]["status"] == "deleted"

    def test_multiple_files(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "+print('a')\n"
            "diff --git a/b.py b/b.py\n"
            "--- a/b.py\n"
            "+++ b/b.py\n"
            "+print('b')\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 2
        filenames = {f["filename"] for f in result}
        assert filenames == {"a.py", "b.py"}

    def test_noise_files_excluded(self):
        diff = (
            "diff --git a/package-lock.json b/package-lock.json\n"
            "+++ b/package-lock.json\n"
            "+noise\n"
            "diff --git a/src/main.py b/src/main.py\n"
            "+++ b/src/main.py\n"
            "+print('real')\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "src/main.py"

    def test_empty_diff(self):
        result = _parse_diff_output("")
        assert result == []

    def test_renamed_file(self):
        diff = (
            "diff --git a/old_name.py b/new_name.py\n"
            "rename from old_name.py\n"
            "rename to new_name.py\n"
            "--- a/old_name.py\n"
            "+++ b/new_name.py\n"
            "+print('renamed')\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "new_name.py"
        assert result[0]["status"] == "renamed"

    def test_binary_file_marked(self):
        diff = (
            "diff --git a/image.png b/image.png\n"
            "Binary files a/image.png and b/image.png differ\n"
        )
        result = _parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["status"] == "binary"


# ── get_pr_diff (mocked git subprocess) ──────────────────────────────


class TestGetPrDiff:
    @patch("app.services.diff_extractor.subprocess.run")
    def test_returns_parsed_files(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "diff --git a/src/app.py b/src/app.py\n" "+++ b/src/app.py\n" "+print('hello')\n"
            ),
            stderr="",
        )
        result = get_pr_diff("/tmp/repo", "abc123", "def456")
        assert len(result) == 1
        assert result[0]["filename"] == "src/app.py"
        mock_run.assert_called_once()

    @patch("app.services.diff_extractor.subprocess.run")
    def test_git_diff_failure_raises(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=128,
            stdout="",
            stderr="fatal: bad revision",
        )
        try:
            get_pr_diff("/tmp/repo", "abc123", "def456")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "git diff failed" in str(e)

    @patch("app.services.diff_extractor.subprocess.run")
    def test_timeout_raises(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=60)
        try:
            get_pr_diff("/tmp/repo", "abc123", "def456")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "timed out" in str(e)

    @patch("app.services.diff_extractor.subprocess.run")
    def test_truncates_large_diff(self, mock_run):
        # Generate a diff with >4000 lines
        big_diff = "diff --git a/big.py b/big.py\n+++ b/big.py\n"
        big_diff += "\n".join(f"+line{i}" for i in range(4100))
        mock_run.return_value = MagicMock(returncode=0, stdout=big_diff, stderr="")
        result = get_pr_diff("/tmp/repo", "abc123", "def456")
        assert len(result) == 1
        assert "TRUNCATED" in result[0]["diff_text"]

    @patch("app.services.diff_extractor.subprocess.run")
    def test_skips_binary_files(self, mock_run):
        diff = (
            "diff --git a/img.png b/img.png\n"
            "Binary files a/img.png and b/img.png differ\n"
            "diff --git a/src/main.py b/src/main.py\n"
            "+++ b/src/main.py\n"
            "+print('ok')\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=diff, stderr="")
        result = get_pr_diff("/tmp/repo", "abc123", "def456")
        assert len(result) == 1
        assert result[0]["filename"] == "src/main.py"
