"""Tests for job queue service."""

import queue

from app.services.queue import JobQueue


class TestJobQueue:
    """Tests for the in-process job queue."""

    def test_enqueue_and_dequeue(self):
        jq = JobQueue()
        jq.enqueue({"type": "review", "repo": "owner/repo"})
        job = jq.dequeue()
        assert job is not None
        assert job["type"] == "review"

    def test_empty_queue_returns_none(self):
        jq = JobQueue()
        assert jq.dequeue() is None

    def test_fifo_order(self):
        jq = JobQueue()
        jq.enqueue({"id": 1})
        jq.enqueue({"id": 2})
        jq.enqueue({"id": 3})
        assert jq.dequeue()["id"] == 1
        assert jq.dequeue()["id"] == 2
        assert jq.dequeue()["id"] == 3

    def test_queue_size(self):
        jq = JobQueue()
        assert jq.size() == 0
        jq.enqueue({"id": 1})
        assert jq.size() == 1
        jq.dequeue()
        assert jq.size() == 0
