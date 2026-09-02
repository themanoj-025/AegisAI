"""Tests for GitHub PR review posting service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.github_reviewer import _build_review_body, _map_hint_to_line, post_review

pytestmark = pytest.mark.integration



class TestBuildReviewBody:
    """Tests for _build_review_body."""

    def test_no_findings(self) -> None:
        result = _build_review_body([], [])
        assert "No security issues found" in result["body"]
        assert result["event"] == "COMMENT"
        assert result["comments"] == []

    def test_critical_findings(self) -> None:
        findings = [
            {
                "severity": "critical",
                "category": "sql_injection",
                "description": "SQL injection vulnerability",
                "recommendation": "Use parameterized queries",
                "file": "app/db.py",
                "line_hint": "cursor.execute",
                "low_confidence": False,
            }
        ]
        result = _build_review_body(findings, [])
        assert "Critical: 1" in result["body"]
        assert "AegisAI Security Review" in result["body"]

    def test_mixed_severity_findings(self) -> None:
        findings = [
            {"severity": "critical", "category": "a", "description": "d", "recommendation": "r", "file": "f", "line_hint": "l", "low_confidence": True},
            {"severity": "high", "category": "b", "description": "d", "recommendation": "r", "file": "f", "line_hint": "l", "low_confidence": True},
            {"severity": "medium", "category": "c", "description": "d", "recommendation": "r", "file": "f", "line_hint": "l", "low_confidence": True},
            {"severity": "low", "category": "d", "description": "d", "recommendation": "r", "file": "f", "line_hint": "l", "low_confidence": True},
        ]
        result = _build_review_body(findings, [])
        assert "Critical: 1" in result["body"]
        assert "High: 1" in result["body"]
        assert "Medium: 1" in result["body"]
        assert "Low: 1" in result["body"]

    def test_inline_comment_when_not_low_confidence(self) -> None:
        findings = [
            {
                "severity": "high",
                "category": "xss",
                "description": "XSS vulnerability",
                "recommendation": "Escape output",
                "file": "app/template.py",
                "line_hint": "render_template",
                "low_confidence": False,
            }
        ]
        diff_files = [
            {
                "filename": "app/template.py",
                "diff_text": "@@ -1,5 +1,5 @@\n def render_template():\n-    return html\n+    return render_template()\n",
            }
        ]
        result = _build_review_body(findings, diff_files)
        assert len(result["comments"]) == 1
        assert result["comments"][0]["path"] == "app/template.py"

    def test_low_confidence_falls_to_summary(self) -> None:
        findings = [
            {
                "severity": "low",
                "category": "info",
                "description": "Minor issue",
                "recommendation": "Consider",
                "file": "app/main.py",
                "line_hint": "something",
                "low_confidence": True,
            }
        ]
        result = _build_review_body(findings, [])
        assert result["comments"] == []
        assert "without line attribution" in result["body"]


class TestMapHintToLine:
    """Tests for _map_hint_to_line."""

    def test_empty_hint_returns_none(self) -> None:
        assert _map_hint_to_line("", "file.py", []) is None

    def test_no_matching_file_returns_none(self) -> None:
        diff_files = [{"filename": "other.py", "diff_text": "some diff"}]
        assert _map_hint_to_line("hint", "file.py", diff_files) is None

    def test_matching_hint_returns_line(self) -> None:
        diff_files = [
            {
                "filename": "app.py",
                "diff_text": "@@ -1,3 +1,4 @@\n def main():\n+    secret = os.environ.get('KEY')\n     return secret\n",
            }
        ]
        result = _map_hint_to_line("secret = os.environ.get", "app.py", diff_files)
        assert result is not None
        assert isinstance(result, int)


class TestPostReview:
    """Tests for post_review (mocked HTTP)."""

    @patch("app.services.github_reviewer.httpx.Client")
    def test_successful_review(self, mock_client_cls) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 12345}
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client_cls.return_value)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.post.return_value = mock_response

        result = post_review(
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="abc123",
            findings=[],
            installation_token="ghp_test",
        )
        assert result["id"] == 12345

    @patch("app.services.github_reviewer.httpx.Client")
    def test_422_fallback_to_summary(self, mock_client_cls) -> None:
        mock_422 = MagicMock()
        mock_422.status_code = 422
        mock_422.text = "Unprocessable"
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"id": 99}

        client_instance = MagicMock()
        client_instance.post.side_effect = [mock_422, mock_200]
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=client_instance)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = post_review(
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="abc123",
            findings=[{"severity": "high", "category": "xss", "description": "d", "recommendation": "r", "file": "f", "line_hint": "l", "low_confidence": False}],
            installation_token="ghp_test",
            diff_files=[{"filename": "f", "diff_text": "@@ -1 +1 @@\n+l"}],
        )
        assert result["id"] == 99
        assert client_instance.post.call_count == 2

    @patch("app.services.github_reviewer.httpx.Client")
    def test_api_error_raises_runtime(self, mock_client_cls) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client_cls.return_value)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value.post.return_value = mock_response

        with pytest.raises(RuntimeError, match="GitHub review API failed"):
            post_review(
                repo_full_name="owner/repo",
                pr_number=1,
                head_sha="abc123",
                findings=[],
                installation_token="ghp_test",
            )
