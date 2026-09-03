"""Tests for the webhook retry queue with dead-letter handling.

Covers: the single-shot enqueue, retry persistence, the RQ retry job's
attempt tracking and DLQ promotion, DLQ admin operations (list/replay/
clear/stats), and the FastAPI admin endpoints.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services import webhook_retry as wr

EVENT = {
    "repo": "owner/repo",
    "pr_number": 42,
    "head_sha": "abc123def456",
    "base_sha": "def456abc123",
    "clone_url": "https://github.com/owner/repo.git",
    "installation_id": 7,
    "event": "pull_request",
    "action": "opened",
    "received_at": "2026-01-01T00:00:00+00:00",
}


class FakeRedis:
    """Minimal Redis stand-in supporting the list ops the DLQ uses."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}

    def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        lst = self.lists.get(key, [])
        if stop == -1 or stop >= len(lst):
            stop = len(lst) - 1
        return lst[start : stop + 1]

    def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    def lrem(self, key: str, count: int, value: str) -> int:
        lst = self.lists.get(key, [])
        removed = 0
        while value in lst and (count == 0 or removed < abs(count)):
            lst.remove(value)
            removed += 1
        return removed

    def delete(self, key: str) -> int:
        if self.lists.pop(key, None) is not None:
            return 1
        return 0


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


def _mock_queue(enqueue_raises: Exception | None = None) -> MagicMock:
    queue = MagicMock()
    if enqueue_raises is not None:
        queue.enqueue.side_effect = enqueue_raises
    return queue


# ── _enqueue_review_once ──────────────────────────────────────────────


def test_enqueue_review_once_queued(fake_redis: FakeRedis) -> None:
    queue = _mock_queue()
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "acquire_review_lock", return_value=True),
        patch.object(wr, "get_queue", return_value=queue),
    ):
        assert wr._enqueue_review_once(EVENT) == wr.STATUS_QUEUED
    queue.enqueue.assert_called_once()
    # review job retries configured
    kwargs = queue.enqueue.call_args.kwargs
    assert kwargs["job_timeout"] == 1800
    assert kwargs["retry"].max == 3


def test_enqueue_review_once_deduplicated(fake_redis: FakeRedis) -> None:
    queue = _mock_queue()
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "acquire_review_lock", return_value=False),
        patch.object(wr, "get_queue", return_value=queue),
    ):
        assert wr._enqueue_review_once(EVENT) == wr.STATUS_DEDUPLICATED
    queue.enqueue.assert_not_called()


def test_enqueue_review_once_failed_releases_lock(fake_redis: FakeRedis) -> None:
    queue = _mock_queue(enqueue_raises=OSError("redis down"))
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "acquire_review_lock", return_value=True),
        patch.object(wr, "get_queue", return_value=queue),
        patch.object(wr, "release_review_lock") as release,
    ):
        assert wr._enqueue_review_once(EVENT) == wr.STATUS_FAILED
    release.assert_called_once_with(EVENT["repo"], EVENT["head_sha"])


# ── enqueue_review_event (webhook path) ───────────────────────────────


def test_enqueue_review_event_falls_back_to_retry(fake_redis: FakeRedis) -> None:
    queue = _mock_queue(enqueue_raises=OSError("redis down"))
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "acquire_review_lock", return_value=True),
        patch.object(wr, "get_queue", return_value=queue),
        patch.object(wr, "release_review_lock"),
        patch.object(wr, "persist_webhook_event", return_value="retry-job-1") as persist,
    ):
        assert wr.enqueue_review_event(EVENT) == wr.STATUS_RETRYING
    persist.assert_called_once_with(EVENT)


def test_enqueue_review_event_returns_failed_when_persist_also_fails(
    fake_redis: FakeRedis,
) -> None:
    queue = _mock_queue(enqueue_raises=OSError("redis down"))
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "acquire_review_lock", return_value=True),
        patch.object(wr, "get_queue", return_value=queue),
        patch.object(wr, "release_review_lock"),
        patch.object(wr, "persist_webhook_event", side_effect=OSError("redis down")),
    ):
        assert wr.enqueue_review_event(EVENT) == wr.STATUS_FAILED


# ── persist_webhook_event ─────────────────────────────────────────────


def test_persist_webhook_event_enqueues_retry_job(fake_redis: FakeRedis) -> None:
    queue = MagicMock()
    queue.enqueue.return_value = MagicMock(id="retry-job-1")
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "Queue", return_value=queue),
    ):
        assert wr.persist_webhook_event(EVENT) == "retry-job-1"
    args, kwargs = queue.enqueue.call_args
    assert args[0] is wr.retry_webhook_enqueue
    assert args[1] == EVENT
    assert kwargs["retry"].max == 4  # max_attempts - 1


# ── retry_webhook_enqueue (worker job) ────────────────────────────────


def _current_job(meta: dict | None = None) -> MagicMock:
    job = MagicMock()
    job.meta = dict(meta or {})
    return job


def test_retry_webhook_enqueue_success(fake_redis: FakeRedis) -> None:
    job = _current_job()
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "get_current_job", return_value=job),
        patch.object(wr, "_enqueue_review_once", return_value=wr.STATUS_QUEUED),
        patch.object(wr, "move_to_dlq") as dlq,
    ):
        wr.retry_webhook_enqueue(EVENT)  # must not raise
    assert job.meta["attempt"] == 1
    dlq.assert_not_called()


def test_retry_webhook_enqueue_raises_below_max(fake_redis: FakeRedis) -> None:
    job = _current_job({"attempt": 1})
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "get_current_job", return_value=job),
        patch.object(wr, "_enqueue_review_once", return_value=wr.STATUS_FAILED),
        patch.object(wr, "move_to_dlq") as dlq,
        patch.object(
            wr, "settings", SimpleNamespace(webhook_retry_max_attempts=5)
        ),
    ):
        with pytest.raises(RuntimeError):
            wr.retry_webhook_enqueue(EVENT)
    assert job.meta["attempt"] == 2
    dlq.assert_not_called()  # RQ will re-enqueue with backoff instead


def test_retry_webhook_enqueue_dead_letters_at_max(fake_redis: FakeRedis) -> None:
    job = _current_job({"attempt": 4})
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "get_current_job", return_value=job),
        patch.object(wr, "_enqueue_review_once", return_value=wr.STATUS_FAILED),
        patch.object(wr, "move_to_dlq") as dlq,
        patch.object(
            wr, "settings", SimpleNamespace(webhook_retry_max_attempts=5)
        ),
    ):
        wr.retry_webhook_enqueue(EVENT)  # must NOT raise on final attempt
    assert job.meta["attempt"] == 5
    dlq.assert_called_once()
    assert dlq.call_args.kwargs["attempts"] == 5


# ── DLQ operations ────────────────────────────────────────────────────


def test_move_to_dlq_and_list_roundtrip(fake_redis: FakeRedis) -> None:
    with patch.object(wr, "get_redis", return_value=fake_redis):
        entry_id = wr.move_to_dlq(EVENT, error="boom", attempts=5)
        entries = wr.list_dlq()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["id"] == entry_id
    assert entry["error"] == "boom"
    assert entry["attempts"] == 5
    assert entry["event"] == EVENT
    assert "dead_lettered_at" in entry


def test_replay_dlq_removes_handled_keeps_failed(fake_redis: FakeRedis) -> None:
    with patch.object(wr, "get_redis", return_value=fake_redis):
        wr.move_to_dlq(EVENT, error="e1", attempts=5)
        wr.move_to_dlq(EVENT, error="e2", attempts=5)
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(
            wr, "enqueue_review_event", side_effect=[wr.STATUS_QUEUED, wr.STATUS_FAILED]
        ),
    ):
        # queued → removed from DLQ; failed → kept for another attempt
        assert wr.replay_dlq() == 1
    with patch.object(wr, "get_redis", return_value=fake_redis):
        remaining = wr.list_dlq()
    assert len(remaining) == 1
    assert remaining[0]["error"] == "e2"


def test_replay_dlq_selected_indexes(fake_redis: FakeRedis) -> None:
    with patch.object(wr, "get_redis", return_value=fake_redis):
        wr.move_to_dlq(EVENT, error="e1", attempts=5)
        wr.move_to_dlq(EVENT, error="e2", attempts=5)
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "enqueue_review_event", return_value=wr.STATUS_QUEUED),
    ):
        assert wr.replay_dlq(indexes=[1]) == 1
    with patch.object(wr, "get_redis", return_value=fake_redis):
        remaining = wr.list_dlq()
    assert len(remaining) == 1
    assert remaining[0]["error"] == "e1"


def test_clear_dlq(fake_redis: FakeRedis) -> None:
    with patch.object(wr, "get_redis", return_value=fake_redis):
        wr.move_to_dlq(EVENT, error="e1", attempts=5)
        wr.move_to_dlq(EVENT, error="e2", attempts=5)
        assert wr.clear_dlq() == 2
        assert wr.list_dlq() == []


def test_get_retry_stats(fake_redis: FakeRedis) -> None:
    retry_queue = MagicMock()
    retry_queue.count = 2
    default_queue = MagicMock()
    default_queue.count = 1
    default_queue.failed_job_registry.count = 3
    with (
        patch.object(wr, "get_redis", return_value=fake_redis),
        patch.object(wr, "Queue", side_effect=[retry_queue, default_queue]),
    ):
        wr.move_to_dlq(EVENT, error="e1", attempts=5)
        stats = wr.get_retry_stats()
    assert stats == {
        "dead_letter_count": 1,
        "retry_queue_pending": 2,
        "review_queue_pending": 1,
        "review_queue_failed": 3,
    }


def test_parse_backoff() -> None:
    assert wr._parse_backoff("60,300, 900 ") == [60, 300, 900]
    assert wr._parse_backoff("") == []


# ── Admin API endpoints ───────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_dlq_endpoints(client: TestClient) -> None:
    dlq_item = {"id": "1", "event": EVENT, "error": "boom", "attempts": 5}
    with (
        patch("app.main.list_dlq", return_value=[dlq_item]),
        patch("app.main.replay_dlq", return_value=2),
        patch("app.main.clear_dlq", return_value=3),
        patch("app.main.get_retry_stats", return_value={"dead_letter_count": 1}),
    ):
        resp = client.get("/api/v1/webhooks/dlq")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        assert resp.json()["items"][0]["id"] == "1"

        resp = client.post("/api/v1/webhooks/dlq/replay", json={"indexes": [0]})
        assert resp.status_code == 200
        assert resp.json()["replayed"] == 2

        resp = client.delete("/api/v1/webhooks/dlq")
        assert resp.status_code == 200
        assert resp.json()["removed"] == 3

        resp = client.get("/api/v1/webhooks/queue/stats")
        assert resp.status_code == 200
        assert resp.json()["dead_letter_count"] == 1


def test_webhook_failure_returns_503(client: TestClient) -> None:
    """When nothing can be persisted, return 503 so GitHub retries."""
    payload = json.dumps(
        {
            "action": "opened",
            "pull_request": {"number": 42, "head": {"sha": "abc123"}, "base": {"sha": "def456"}},
            "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
            "installation": {"id": 7},
        }
    ).encode()
    with (
        patch("app.main.verify_github_signature", return_value=True),
        patch("app.main.enqueue_review_event", return_value=wr.STATUS_FAILED),
    ):
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={"X-GitHub-Event": "pull_request"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "queue_unavailable"


def test_webhook_retrying_returns_accepted(client: TestClient) -> None:
    """A persisted retry is acknowledged immediately (200), never dropped."""
    payload = json.dumps(
        {
            "action": "synchronize",
            "pull_request": {"number": 42, "head": {"sha": "abc123"}, "base": {"sha": "def456"}},
            "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
            "installation": {"id": 7},
        }
    ).encode()
    with (
        patch("app.main.verify_github_signature", return_value=True),
        patch("app.main.enqueue_review_event", return_value=wr.STATUS_RETRYING),
    ):
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={"X-GitHub-Event": "pull_request"},
        )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "queued_for_retry"
