"""Tests for diff extraction service."""

from app.services.diff_extractor import extract_diff_files, parse_diff


class TestExtractDiffFiles:
    """Tests for extract_diff_files."""

    def test_empty_diff(self) -> None:
        result = extract_diff_files("")
        assert result == []

    def test_single_file_diff(self) -> None:
        diff = (
            "diff --git a/app.py b/app.py\n"
            "index abc..def 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,3 +1,4 @@\n"
            " def main():\n"
            "-    pass\n"
            "+    print('hello')\n"
            "+    return 0\n"
        )
        result = extract_diff_files(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "app.py"

    def test_multi_file_diff(self) -> None:
        diff = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/b.py b/b.py\n"
            "--- a/b.py\n"
            "+++ b/b.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = extract_diff_files(diff)
        assert len(result) == 2

    def test_binary_files_skipped(self) -> None:
        diff = (
            "diff --git a/image.png b/image.png\n"
            "Binary files a/image.png and b/image.png differ\n"
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = extract_diff_files(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "app.py"


class TestParseDiff:
    """Tests for parse_diff."""

    def test_additions_and_deletions(self) -> None:
        diff_text = (
            "@@ -1,3 +1,4 @@\n"
            " def main():\n"
            "-    pass\n"
            "+    print('hello')\n"
            "+    return 0\n"
        )
        result = parse_diff(diff_text)
        assert result["additions"] == 2
        assert result["deletions"] == 1
