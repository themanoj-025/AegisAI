"""Redis queue setup for background job processing.

Provides Redis connection management, queue access, and a deduplication
lock mechanism to prevent processing the same webhook event twice.
"""

import logging
import time

import redis

from app.config import settings

logger = logging.getLogger("aegisai")

# Redis connection — lazily initialized
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Get or create a Redis connection."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        logger.info("Connected to Redis at %s", settings.redis_url)
    return _redis_client


def get_queue() -> "rq.Queue":
    """Get the default RQ queue."""
    from rq import Queue

    return Queue(connection=get_redis())


def acquire_review_lock(repo_full_name: str, head_sha: str, ttl: int = 600) -> bool:
    """Try to acquire a deduplication lock for a given PR commit.

    Uses Redis SETNX to ensure we don't enqueue duplicate reviews for the
    same head SHA. Returns True if the lock was acquired (i.e., this is a
    new/unique event), False if a review is already in progress or was
    done recently.

    The default TTL is 10 minutes (600 seconds), after which the lock
    auto-expires.
    """
    key = f"review_lock:{repo_full_name}:{head_sha}"
    redis_client = get_redis()
    acquired = redis_client.setnx(key, str(time.time()))
    if acquired:
        redis_client.expire(key, ttl)
        return True
    return False
