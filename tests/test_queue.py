"""Tests for the Redis queue / review-lock helpers."""


class _FakeRedis:
    """Minimal redis.Redis stand-in supporting the lock ops used by queue.py."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def setnx(self, key: str, value: str) -> bool:
        if key in self._data:
            return False
        self._data[key] = value
        return True

    def expire(self, key: str, ttl: int) -> bool:
        return key in self._data

    def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0

    def ping(self) -> bool:
        return True


class TestReviewLock:
    def test_acquire_returns_true_first_time(self, monkeypatch) -> None:
        fake = _FakeRedis()
        monkeypatch.setattr("app.services.queue.get_redis", lambda: fake)
        from app.services.queue import acquire_review_lock

        assert acquire_review_lock("owner/repo", "abc123") is True

    def test_duplicate_acquire_returns_false(self, monkeypatch) -> None:
        fake = _FakeRedis()
        monkeypatch.setattr("app.services.queue.get_redis", lambda: fake)
        from app.services.queue import acquire_review_lock

        assert acquire_review_lock("owner/repo", "abc123") is True
        assert acquire_review_lock("owner/repo", "abc123") is False

    def test_lock_key_isolation_between_prs(self, monkeypatch) -> None:
        fake = _FakeRedis()
        monkeypatch.setattr("app.services.queue.get_redis", lambda: fake)
        from app.services.queue import acquire_review_lock

        assert acquire_review_lock("owner/repo", "sha1") is True
        assert acquire_review_lock("owner/repo", "sha2") is True

    def test_release_allows_reacquire(self, monkeypatch) -> None:
        fake = _FakeRedis()
        monkeypatch.setattr("app.services.queue.get_redis", lambda: fake)
        from app.services.queue import acquire_review_lock, release_review_lock

        assert acquire_review_lock("owner/repo", "abc123") is True
        release_review_lock("owner/repo", "abc123")
        assert acquire_review_lock("owner/repo", "abc123") is True


class TestGetQueue:
    def test_returns_rq_queue_with_connection(self, monkeypatch) -> None:
        fake = _FakeRedis()
        monkeypatch.setattr("app.services.queue.get_redis", lambda: fake)
        from app.services.queue import get_queue

        queue = get_queue()
        assert queue is not None
        assert queue.connection is fake
