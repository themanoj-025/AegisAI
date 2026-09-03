"""Webhook retry queue with dead-letter handling.

When a valid GitHub webhook event cannot be enqueued for review (transient
Redis or RQ failure), the event is persisted and retried with exponential
backoff by the ``webhook-retry`` RQ queue. Events that exhaust all attempts
are moved to a dead-letter queue (DLQ) in Redis for inspection and manual
replay via the admin API.

Flow
----
webhook handler
    └─ enqueue_review_event(event)
         ├─ "queued"        → review job enqueued on the default queue
         ├─ "deduplicated"  → a review is already in flight for this head SHA
         ├─ "retrying"      → enqueue failed; retry job persisted (backoff)
         └─ "failed"        → nothing persisted; caller should return 503 so
                              GitHub retries the webhook natively

retry worker (webhook-retry queue)
    └─ retry_webhook_enqueue(event)
         ├─ enqueue succeeds            → done
         ├─ still failing, attempts < max → raise → RQ re-enqueues (backoff)
         └─ still failing, attempts == max → move_to_dlq(event) → done
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from rq import Queue, Retry, get_current_job

from app.config import settings
from app.services.queue import acquire_review_lock, get_queue, get_redis, release_review_lock
from app.workers.review_worker import run_review_job

logger = logging.getLogger("aegisai")

# Redis keys for the dead-letter queue (a list of JSON entries)
DLQ_KEY = "webhook:dlq"

# Redis-backed counters — incremented in the worker where DLQ moves happen,
# read by the API process for /metrics and the stats endpoint.
DLQ_MOVES_KEY = "webhook:dlq:moves_total"  # integer counter
DLQ_MOVES_BY_REPO_KEY = "webhook:dlq:moves_by_repo"  # hash: repo -> count

# Event statuses returned by enqueue_review_event / _enqueue_review_once
STATUS_QUEUED = "queued"
STATUS_DEDUPLICATED = "deduplicated"
STATUS_RETRYING = "retrying"
STATUS_FAILED = "failed"


def _parse_backoff(raw: str) -> list[int]:
    """Parse a comma-separated backoff string into a list of seconds."""
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _enqueue_review_once(event: dict[str, Any]) -> str:
    """Attempt to enqueue a review job exactly once.

    Returns one of STATUS_QUEUED / STATUS_DEDUPLICATED / STATUS_FAILED.
    On failure the deduplication lock is released so a later retry can
    re-acquire it instead of being treated as a duplicate.
    """
    repo: str = event["repo"]
    head_sha: str = event["head_sha"]

    if not acquire_review_lock(repo, head_sha):
        return STATUS_DEDUPLICATED

    try:
        queue = get_queue()
        queue.enqueue(
            run_review_job,
            repo,
            event["pr_number"],
            head_sha,
            event["base_sha"],
            event["clone_url"],
            event["installation_id"],
            job_timeout=settings.review_job_timeout,
            retry=Retry(max=settings.review_job_max_retries, interval=_parse_backoff(settings.review_job_backoff)),
        )
        return STATUS_QUEUED
    except Exception as e:
        logger.warning(
            "Enqueue failed for %s PR #%d (head %s): %s",
            repo,
            event["pr_number"],
            head_sha[:7],
            e,
        )
        release_review_lock(repo, head_sha)
        return STATUS_FAILED


def enqueue_review_event(event: dict[str, Any]) -> str:
    """Enqueue a webhook event for review, falling back to the retry queue.

    Returns one of STATUS_QUEUED / STATUS_DEDUPLICATED / STATUS_RETRYING /
    STATUS_FAILED. STATUS_FAILED means nothing was persisted and the caller
    should return an error status so GitHub retries the webhook natively.
    """
    status = _enqueue_review_once(event)
    if status != STATUS_FAILED:
        return status

    try:
        persist_webhook_event(event)
        return STATUS_RETRYING
    except Exception as e:
        logger.error(
            "Failed to persist retry for %s PR #%d — event will be dropped: %s",
            event["repo"],
            event["pr_number"],
            e,
        )
        return STATUS_FAILED


def persist_webhook_event(event: dict[str, Any]) -> str:
    """Persist a webhook event to the retry queue for later processing.

    The retry job itself uses RQ Retry with exponential backoff; each
    execution attempts the real enqueue. Returns the retry job id.
    """
    queue = Queue(settings.webhook_retry_queue, connection=get_redis())
    job = queue.enqueue(
        retry_webhook_enqueue,
        event,
        job_timeout=60,
        retry=Retry(max=settings.webhook_retry_max_attempts - 1, interval=_parse_backoff(settings.webhook_retry_backoff)),
        result_ttl=7 * 86400,
    )
    logger.warning(
        "Webhook event queued for retry: repo=%s pr=%d job=%s",
        event["repo"],
        event["pr_number"],
        job.id,
    )
    return job.id


def retry_webhook_enqueue(event: dict[str, Any]) -> None:
    """RQ job: retry enqueuing a review job for a persisted webhook event.

    Runs on the ``webhook-retry`` queue. Tracks the attempt count in the
    job meta; on the final failed attempt the event is moved to the DLQ
    instead of raising (so RQ does not keep retrying a doomed job).
    """
    job = get_current_job()
    meta = dict(job.meta or {})
    attempt = int(meta.get("attempt", 0)) + 1
    meta["attempt"] = attempt
    job.meta = meta
    job.save_meta()

    status = _enqueue_review_once(event)
    if status != STATUS_FAILED:
        if status == STATUS_QUEUED:
            logger.info(
                "Retry succeeded for %s PR #%d (attempt %d)",
                event["repo"],
                event["pr_number"],
                attempt,
            )
        else:
            logger.info(
                "Retry skipped for %s PR #%d (attempt %d) — deduplicated",
                event["repo"],
                event["pr_number"],
                attempt,
            )
        return

    if attempt >= settings.webhook_retry_max_attempts:
        move_to_dlq(
            event,
            error=f"enqueue failed after {attempt} attempts",
            attempts=attempt,
        )
        return

    raise RuntimeError(
        f"webhook enqueue failed on attempt {attempt}/{settings.webhook_retry_max_attempts} "
        f"for {event['repo']} PR #{event['pr_number']}"
    )


# ── Dead-letter queue ──────────────────────────────────────────────────


def _notify_dead_letter(entry: dict[str, Any]) -> None:
    """Best-effort ops notification for a dead-lettered event.

    POSTs a Slack-compatible payload to settings.alert_webhook_url. Never
    raises: alerting must not fail the retry job or lose the DLQ entry.
    """
    url = settings.alert_webhook_url
    if not url:
        return
    event = entry["event"]
    try:
        resp = httpx.post(
            url,
            json={
                "text": (
                    f"⚠️ *AegisAI: webhook event dead-lettered*\n"
                    f"repo: `{event['repo']}`\n"
                    f"PR: #{event['pr_number']} (head `{event['head_sha'][:7]}`)\n"
                    f"attempts: {entry['attempts']}\n"
                    f"error: {entry['error']}\n"
                    f"dead-lettered at: {entry['dead_lettered_at']}\n"
                    f"Replay: POST /api/v1/webhooks/dlq/replay"
                ),
                "mrkdwn": True,
            },
            timeout=3.0,
        )
        logger.info("DLQ alert sent (status=%s)", resp.status_code)
    except Exception as e:
        logger.warning("Failed to send DLQ alert to ops webhook: %s", e)


def move_to_dlq(event: dict[str, Any], error: str, attempts: int) -> str:
    """Append an event to the dead-letter queue for manual inspection/replay.

    Also bumps the Redis-backed dead-letter counters (shared between the
    worker, which moves events here, and the API process, which exposes
    them via /metrics) and fires the ops alert webhook if configured.
    """
    entry = {
        "id": f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}",
        "event": event,
        "error": error[:500],
        "attempts": attempts,
        "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
    }
    redis_client = get_redis()
    redis_client.rpush(DLQ_KEY, json.dumps(entry))
    redis_client.incr(DLQ_MOVES_KEY)
    redis_client.hincrby(DLQ_MOVES_BY_REPO_KEY, event["repo"], 1)
    logger.error(
        "Webhook event dead-lettered: repo=%s pr=%d error=%s",
        event["repo"],
        event["pr_number"],
        error,
    )
    _notify_dead_letter(entry)
    return entry["id"]


def list_dlq(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent dead-lettered events (oldest first)."""
    raw_entries = get_redis().lrange(DLQ_KEY, 0, limit - 1)
    return [json.loads(entry) for entry in raw_entries]


def _remove_dlq_entry_by_id(entry_id: str) -> bool:
    """Remove a single DLQ entry by id. Returns True if removed."""
    redis_client = get_redis()
    for raw in redis_client.lrange(DLQ_KEY, 0, -1):
        entry = json.loads(raw)
        if entry.get("id") == entry_id:
            redis_client.lrem(DLQ_KEY, 1, raw)
            return True
    return False


def replay_dlq(indexes: list[int] | None = None) -> int:
    """Re-enqueue dead-lettered events for processing.

    By default replays the entire DLQ. ``indexes`` selects specific
    entries by their position in list_dlq(). Entries that are successfully
    handled (queued, retrying, or deduplicated) are removed from the DLQ;
    entries that still fail to persist are kept for another attempt.
    Returns the number of entries replayed.
    """
    entries = list_dlq(limit=1000)
    selected = (
        [entries[i] for i in indexes if 0 <= i < len(entries)]
        if indexes is not None
        else entries
    )

    replayed = 0
    for entry in selected:
        status = enqueue_review_event(entry["event"])
        if status in (STATUS_QUEUED, STATUS_RETRYING, STATUS_DEDUPLICATED):
            _remove_dlq_entry_by_id(entry["id"])
            replayed += 1
            logger.info(
                "Replayed DLQ entry %s for %s PR #%d (status=%s)",
                entry["id"],
                entry["event"]["repo"],
                entry["event"]["pr_number"],
                status,
            )
    return replayed


def clear_dlq() -> int:
    """Remove all dead-lettered events. Returns the number removed."""
    redis_client = get_redis()
    count = redis_client.llen(DLQ_KEY)
    if count:
        redis_client.delete(DLQ_KEY)
    return count


def get_dlq_metrics() -> dict[str, Any]:
    """Return dead-letter counters for Prometheus exposure.

    These are Redis-backed so the worker (which performs DLQ moves) and the
    API process (which serves /metrics) share the same numbers.
    """
    redis_client = get_redis()
    by_repo = redis_client.hgetall(DLQ_MOVES_BY_REPO_KEY) or {}
    return {
        "dead_letter_moves_total": int(redis_client.get(DLQ_MOVES_KEY) or 0),
        "dead_letter_current": redis_client.llen(DLQ_KEY),
        "dead_letter_by_repo": {k: int(v) for k, v in by_repo.items()},
    }


def get_retry_stats() -> dict[str, Any]:
    """Return queue health stats for ops dashboards/admin API."""
    redis_client = get_redis()
    retry_queue = Queue(settings.webhook_retry_queue, connection=redis_client)
    default_queue = Queue(connection=redis_client)
    return {
        "dead_letter_count": redis_client.llen(DLQ_KEY),
        "dead_letter_moves_total": int(redis_client.get(DLQ_MOVES_KEY) or 0),
        "retry_queue_pending": retry_queue.count,
        "review_queue_pending": default_queue.count,
        "review_queue_failed": default_queue.failed_job_registry.count,
    }
