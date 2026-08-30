"""Tests for review worker."""


from app.workers.review_worker import ReviewWorker


class TestReviewWorker:
    """Tests for ReviewWorker."""

    def test_init(self) -> None:
        worker = ReviewWorker()
        assert worker is not None
