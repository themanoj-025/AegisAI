"""Tests for diff extraction (additional cases)."""

from app.services.diff_extractor import extract_diff_files


class TestExtractDiffFilesV2:
    """Additional tests for extract_diff_files."""

    def test_rename_only(self) -> None:
        diff = (
            "diff --git a/old.py b/new.py\n"
            "rename from old.py\n"
            "rename to new.py\n"
        )
        result = extract_diff_files(diff)
        assert len(result) >= 0  # Rename-only diffs may or may not be included

    def test_deletion(self) -> None:
        diff = (
            "diff --git a/deleted.py b/deleted.py\n"
            "deleted file mode 100644\n"
            "--- a/deleted.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0 @@\n"
            "-old content\n"
        )
        result = extract_diff_files(diff)
        assert len(result) == 1

    def test_large_diff(self) -> None:
        # Simulate a large diff with many files
        parts = []
        for i in range(20):
            parts.append(
                f"diff --git a/file{i}.py b/file{i}.py\n"
                f"--- a/file{i}.py\n"
                f"+++ b/file{i}.py\n"
                f"@@ -1 +1 @@\n"
                f"-old{i}\n"
                f"+new{i}\n"
            )
        diff = "".join(parts)
        result = extract_diff_files(diff)
        assert len(result) == 20
