"""Security Review agent.

The centerpiece of AegisAI Phase 1: takes a parsed diff, sends it to
an LLM for security analysis, and returns structured, line-anchored
findings with a lightweight hallucination guard.
"""

import json
import logging
import re
from typing import Any

from app.services.llm_gateway import call_llm
from app.services.secrets_redactor import redact_secrets

logger = logging.getLogger("aegisai")

_SYSTEM_PROMPT = """You are a senior application security engineer reviewing a code diff.

Look specifically for these vulnerability types in the code changes:
- SQL injection
- Cross-site scripting (XSS)
- Cross-Site Request Forgery (CSRF) gaps
- Hardcoded secrets / credentials (look for patterns like random-looking strings, placeholder values like "abc123", "changeme", "password123", etc.)
- Insecure deserialization
- Path traversal
- Server-Side Request Forgery (SSRF)
- Broken authentication / authorization logic
- Insecure Direct Object References (IDOR)
- Unsafe use of eval/exec or similar dynamic-execution constructs
- Command injection
- Insecure cryptographic practices

CRITICAL RULES:
1. ONLY flag issues you can point to with HIGH CONFIDENCE in the ACTUAL diff content provided.
2. Do NOT give hypothetical advice or generic security tips.
3. If a file has zero genuine findings, return an empty findings array.
4. Do NOT manufacture low-value findings just to have output.
5. Be specific — reference actual variable names, function names, and patterns from the code.

Respond with valid JSON matching this exact schema:
{
  "findings": [
    {
      "file": "string - exact filename as provided",
      "line_hint": "string - the literal line of code or closest identifiable snippet the issue relates to",
      "severity": "critical | high | medium | low",
      "category": "string, e.g. sql_injection, hardcoded_secret, xss, command_injection",
      "description": "string - what the issue is, specific to this code, not generic",
      "recommendation": "string - concrete fix suggestion"
    }
  ]
}

IMPORTANT: Respond with ONLY the JSON. No surrounding text, no markdown formatting."""


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block within markdown code fences
    json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find anything that looks like a JSON object
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse JSON from LLM response")


def _verify_line_hint(line_hint: str, diff_text: str) -> bool:
    """Simple substring check to verify a line_hint actually exists in the diff."""
    if not line_hint:
        return False
    # Normalize whitespace for comparison
    normalized_hint = " ".join(line_hint.split())
    normalized_diff = " ".join(diff_text.split())
    return normalized_hint in normalized_diff


def _batch_files(files: list[dict]) -> list[list[dict]]:
    """Batch files into groups for more efficient LLM calls.

    Small files (< 50 diff lines) are batched together; large files
    are sent individually to avoid overwhelming the context window.
    """
    small_files = []
    large_files = []

    for f in files:
        line_count = f["diff_text"].count("\n")
        if line_count < 50:
            small_files.append(f)
        else:
            large_files.append(f)

    batches = []
    # Batch small files together (up to 5 per batch or ~200 lines)
    current_batch = []
    current_lines = 0
    for f in small_files:
        flines = f["diff_text"].count("\n")
        if current_lines + flines > 200 or len(current_batch) >= 5:
            batches.append(current_batch)
            current_batch = [f]
            current_lines = flines
        else:
            current_batch.append(f)
            current_lines += flines
    if current_batch:
        batches.append(current_batch)

    # Each large file gets its own batch
    for f in large_files:
        batches.append([f])

    return batches


def run_security_agent(pr_files: list[dict]) -> list[dict]:
    """Run the security review agent on a list of changed files.

    Args:
        pr_files: List of dicts from get_pr_diff(), each containing
                  filename, status, and diff_text.

    Returns:
        A flat list of findings dicts, each with keys:
            file, line_hint, severity, category, description,
            recommendation, and low_confidence (bool).
    """
    all_findings: list[dict] = []

    if not pr_files:
        logger.info("Security agent: no files to review")
        return all_findings

    # Batch files for efficient LLM calls
    batches = _batch_files(pr_files)
    logger.info(
        "Security agent: reviewing %d files in %d batches",
        len(pr_files),
        len(batches),
    )

    for batch_idx, batch in enumerate(batches):
        # Build the user prompt with redacted diffs
        prompt_parts = []
        for f in batch:
            redacted_diff = redact_secrets(f["diff_text"])
            prompt_parts.append(
                f"--- File: {f['filename']} (status: {f['status']}) ---\n{redacted_diff}"
            )

        user_prompt = (
            "Review the following code changes for security vulnerabilities.\n\n"
            + "\n\n".join(prompt_parts)
        )

        try:
            response_text = call_llm(_SYSTEM_PROMPT, user_prompt, response_format="json")
            result = _extract_json(response_text)
            batch_findings = result.get("findings", [])

            if not batch_findings:
                logger.debug("Batch %d: no findings", batch_idx)
                continue

            # Add file info and run verification pass
            for finding in batch_findings:
                finding_file = finding.get("file", "")
                line_hint = finding.get("line_hint", "")

                # Find the corresponding file's diff text
                file_diff = ""
                for f in pr_files:
                    if f["filename"] == finding_file:
                        file_diff = f["diff_text"]
                        break

                # Verification: check that line_hint actually appears in the diff
                is_confident = _verify_line_hint(line_hint, file_diff)
                if not is_confident:
                    logger.warning(
                        "Low confidence finding in %s: line_hint '%s' not found in diff — marking",
                        finding_file,
                        line_hint[:80],
                    )

                finding["low_confidence"] = not is_confident
                all_findings.append(finding)

            logger.info(
                "Batch %d: found %d findings (%d low confidence)",
                batch_idx,
                len(batch_findings),
                sum(1 for f in batch_findings if f.get("low_confidence", False)),
            )

        except ValueError as e:
            logger.error(
                "Batch %d: failed to parse LLM response as JSON: %s — skipping batch",
                batch_idx,
                e,
            )
        except Exception as e:
            logger.error(
                "Batch %d: unexpected error: %s — skipping batch",
                batch_idx,
                e,
                exc_info=True,
            )

    logger.info(
        "Security agent complete: %d total findings across %d files",
        len(all_findings),
        len(pr_files),
    )

    return all_findings
