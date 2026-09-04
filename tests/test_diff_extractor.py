"""Tests for the diff parser (``_parse_diff_output``).

The public entry point ``get_pr_diff`` shells out to ``git``; its behavior
is covered in test_diff_extractor_v2.py. These tests exercise the parser
directly with canned git-diff text.
"""

import app.services.diff_extractor as de


class TestParseDiffOutput:
    """Tests for _parse_diff_output."""

    def test_empty_diff(self) -> None:
        assert de._parse_diff_output("") == []

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
        result = de._parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "app.py"
        assert result[0]["status"] == "modified"
        assert "-    pass\n" in result[0]["diff_text"]

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
        result = de._parse_diff_output(diff)
        assert [f["filename"] for f in result] == ["a.py", "b.py"]

    def test_added_status(self) -> None:
        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "index 000..abc\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1 @@\n"
            "+content\n"
        )
        result = de._parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["status"] == "added"

    def test_deleted_status(self) -> None:
        diff = (
            "diff --git a/deleted.py b/deleted.py\n"
            "deleted file mode 100644\n"
            "--- a/deleted.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0 @@\n"
            "-old content\n"
        )
        result = de._parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "deleted.py"
        assert result[0]["status"] == "deleted"

    def test_renamed_status(self) -> None:
        diff = (
            "diff --git a/old.py b/new.py\n"
            "rename from old.py\n"
            "rename to new.py\n"
            "index abc..def 100644\n"
        )
        result = de._parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["filename"] == "new.py"
        assert result[0]["status"] == "renamed"

    def test_noise_files_excluded(self) -> None:
        diff = (
            "diff --git a/package-lock.json b/package-lock.json\n"
            "--- a/package-lock.json\n"
            "+++ b/package-lock.json\n"
            "@@ -1 +1 @@\n"
            "-a\n"
            "+b\n"
            "diff --git a/node_modules/x/index.js b/node_modules/x/index.js\n"
            "--- a/node_modules/x/index.js\n"
            "+++ b/node_modules/x/index.js\n"
            "@@ -1 +1 @@\n"
            "-a\n"
            "+b\n"
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = de._parse_diff_output(diff)
        assert [f["filename"] for f in result] == ["app.py"]

    def test_binary_file_marked(self) -> None:
        diff = (
            "diff --git a/image.png b/image.png\n"
            "Binary files a/image.png and b/image.png differ\n"
        )
        result = de._parse_diff_output(diff)
        assert len(result) == 1
        assert result[0]["status"] == "binary"
