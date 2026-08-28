"""Tests for review worker."""

import pytest
from unittest.mock import MagicMock, patch

from app.workers.review_worker import ReviewWorker


class TestReviewWorker:
    """Tests for ReviewWorker."""

    def test_init(self):
        worker = ReviewWorker()
        assert worker is not None
