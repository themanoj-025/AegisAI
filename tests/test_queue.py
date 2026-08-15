"""Tests for app.services.queue — deduplication lock mechanism (mocked Redis)."""

from unittest.mock import MagicMock, patch

from app.services.queue import acquire_review_lock


class TestAcquireReviewLock:
    @patch("app.services.queue.get_redis")
    def test_acquires_lock_on_first_call(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = True
        mock_get_redis.return_value = mock_redis

        result = acquire_review_lock("org/repo", "abc123")
        assert result is True
        mock_redis.setnx.assert_called_once()
        mock_redis.expire.assert_called_once()

    @patch("app.services.queue.get_redis")
    def test_rejects_duplicate(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = False  # Lock already exists
        mock_get_redis.return_value = mock_redis

        result = acquire_review_lock("org/repo", "abc123")
        assert result is False

    @patch("app.services.queue.get_redis")
    def test_lock_key_format(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = True
        mock_get_redis.return_value = mock_redis

        acquire_review_lock("org/repo", "abc123def")
        call_args = mock_redis.setnx.call_args[0]
        assert call_args[0] == "review_lock:org/repo:abc123def"

    @patch("app.services.queue.get_redis")
    def test_custom_ttl(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = True
        mock_get_redis.return_value = mock_redis

        acquire_review_lock("org/repo", "abc123", ttl=120)
        mock_redis.expire.assert_called_once_with("review_lock:org/repo:abc123", 120)

    @patch("app.services.queue.get_redis")
    def test_default_ttl_is_600(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = True
        mock_get_redis.return_value = mock_redis

        acquire_review_lock("org/repo", "abc123")
        mock_redis.expire.assert_called_once_with("review_lock:org/repo:abc123", 600)
