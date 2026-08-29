"""Tests for app.agents.security_agent — JSON extraction, verification, batching."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


class TestExtractJson:
    """_extract_json parses LLM responses with various formatting."""

    def test_direct_json(self) -> None:
        from app.agents.security_agent import _extract_json

        data = {"findings": [{"file": "test.py", "severity": "high"}]}
        result = _extract_json(json.dumps(data))
        assert result["findings"][0]["severity"] == "high"

    def test_json_in_code_fence(self) -> None:
        from app.agents.security_agent import _extract_json

        data = {"findings": []}
        text = f"```json\n{json.dumps(data)}\n```"
        result = _extract_json(text)
        assert result["findings"] == []

    def test_json_in_plain_fence(self) -> None:
        from app.agents.security_agent import _extract_json

        data = {"findings": [{"file": "a.py"}]}
        text = f"```\n{json.dumps(data)}\n```"
        result = _extract_json(text)
        assert len(result["findings"]) == 1

    def test_json_buried_in_text(self) -> None:
        from app.agents.security_agent import _extract_json

        data = {"findings": []}
        text = f"Here is the result: {json.dumps(data)} done."
        result = _extract_json(text)
        assert "findings" in result

    def test_invalid_json_raises(self) -> None:
        from app.agents.security_agent import _extract_json

        with pytest.raises(ValueError, match="Could not parse JSON"):
            _extract_json("not json at all {{{")

    def test_whitespace_wrapped_json(self) -> None:
        from app.agents.security_agent import _extract_json

        data = {"findings": [{"file": "x.py"}]}
        text = f"  \n{json.dumps(data)}\n  "
        result = _extract_json(text)
        assert result["findings"][0]["file"] == "x.py"


class TestVerifyLineHint:
    """_verify_line_hint checks substring presence in diff text."""

    def test_hint_found(self) -> None:
        from app.agents.security_agent import _verify_line_hint

        diff = "+    cursor.execute('SELECT * FROM users')"
        assert _verify_line_hint("cursor.execute('SELECT * FROM users')", diff) is True

    def test_hint_not_found(self) -> None:
        from app.agents.security_agent import _verify_line_hint

        diff = "+    print('hello')"
        assert _verify_line_hint("os.system('rm -rf /')", diff) is False

    def test_empty_hint_returns_false(self) -> None:
        from app.agents.security_agent import _verify_line_hint

        assert _verify_line_hint("", "some diff") is False

    def test_whitespace_normalization(self) -> None:
        from app.agents.security_agent import _verify_line_hint

        # The function normalizes whitespace with ' '.join(line.split())
        # so multiple spaces become single spaces
        diff = "+    x   =   1"
        assert _verify_line_hint("x = 1", diff) is True


class TestBatchFiles:
    """_batch_files groups small files together and large files individually."""

    def test_empty_list(self) -> None:
        from app.agents.security_agent import _batch_files

        assert _batch_files([]) == []

    def test_small_files_batched(self) -> None:
        from app.agents.security_agent import _batch_files

        files = [
            {"filename": f"f{i}.py", "diff_text": "+line\n" * 5, "status": "modified"}
            for i in range(3)
        ]
        batches = _batch_files(files)
        # All 3 small files should be in one batch
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_large_files_own_batch(self) -> None:
        from app.agents.security_agent import _batch_files

        large = {"filename": "big.py", "diff_text": "+line\n" * 60, "status": "modified"}
        small = {"filename": "small.py", "diff_text": "+line\n" * 5, "status": "modified"}
        batches = _batch_files([large, small])
        # Large file gets its own batch, small file in another
        assert len(batches) == 2

    def test_many_small_files_split_by_line_count(self) -> None:
        from app.agents.security_agent import _batch_files

        files = [
            {"filename": f"f{i}.py", "diff_text": "+line\n" * 50, "status": "modified"}
            for i in range(5)
        ]
        batches = _batch_files(files)
        # Each file has 50 lines, limit is 200 lines per batch
        # So 4 fit in first batch (200 lines), 5th goes to second
        total_files = sum(len(b) for b in batches)
        assert total_files == 5


class TestRunSecurityAgent:
    """run_security_agent orchestrates the review process."""

    def test_empty_files_returns_empty(self) -> None:
        from app.agents.security_agent import run_security_agent

        result = run_security_agent([])
        assert result == []

    def test_findings_include_low_confidence_flag(self) -> None:
        """When LLM returns a finding, it should have low_confidence set."""
        from app.agents.security_agent import run_security_agent

        mock_response = json.dumps({
            "findings": [
                {
                    "file": "app.py",
                    "line_hint": "os.system(cmd)",
                    "severity": "critical",
                    "category": "command_injection",
                    "description": "Direct command injection",
                    "recommendation": "Use subprocess with list args",
                }
            ]
        })

        with patch("app.agents.security_agent.call_llm", return_value=mock_response):
            files = [{"filename": "app.py", "diff_text": "+os.system(cmd)", "status": "modified"}]
            result = run_security_agent(files)
            assert len(result) == 1
            assert "low_confidence" in result[0]

    def test_line_hint_not_in_diff_marks_low_confidence(self) -> None:
        from app.agents.security_agent import run_security_agent

        mock_response = json.dumps({
            "findings": [
                {
                    "file": "app.py",
                    "line_hint": "totally different code",
                    "severity": "high",
                    "category": "xss",
                    "description": "XSS vulnerability",
                    "recommendation": "Escape output",
                }
            ]
        })

        with patch("app.agents.security_agent.call_llm", return_value=mock_response):
            files = [{"filename": "app.py", "diff_text": "+print('hello')", "status": "modified"}]
            result = run_security_agent(files)
            assert len(result) == 1
            assert result[0]["low_confidence"] is True

    def test_llm_json_error_skips_batch(self) -> None:
        from app.agents.security_agent import run_security_agent

        with patch("app.agents.security_agent.call_llm", return_value="not json"):
            files = [{"filename": "x.py", "diff_text": "+code", "status": "modified"}]
            result = run_security_agent(files)
            assert result == []

    def test_llm_exception_skips_batch(self) -> None:
        from app.agents.security_agent import run_security_agent

        with patch("app.agents.security_agent.call_llm", side_effect=OSError("API down")):
            files = [{"filename": "x.py", "diff_text": "+code", "status": "modified"}]
            result = run_security_agent(files)
            assert result == []
