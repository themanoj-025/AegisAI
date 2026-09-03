#!/usr/bin/env python3
"""Entrypoint for the AegisAI background worker process.

Run this in a separate terminal from the FastAPI server:
    python worker.py

This starts an RQ worker that listens for jobs on the default queue
and processes them using the functions registered in app.workers.
"""

import logging
import sys

import redis
from rq import Worker

from app.config import settings

logger = logging.getLogger("aegisai")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s | worker | %(levelname)s | %(message)s"))
logger.addHandler(handler)


def main() -> None:
    """Start the RQ worker, listening on the default and retry queues."""
    logger.info("Starting AegisAI worker...")
    logger.info("Redis URL: %s", settings.redis_url)

    from app.services.webhook_retry import retry_webhook_enqueue
    from app.workers.review_worker import run_review_job

    _ = run_review_job        # register the review job function with RQ
    _ = retry_webhook_enqueue  # register the webhook retry job function with RQ

    queues = ["default", settings.webhook_retry_queue]
    logger.info("Listening on queues: %s", ", ".join(queues))
    worker = Worker(queues, connection=redis.Redis.from_url(settings.redis_url))
    worker.work()


if __name__ == "__main__":
    main()
