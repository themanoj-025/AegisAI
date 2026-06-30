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
from rq import Connection, Worker

from app.config import settings

logger = logging.getLogger("aegisai")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter("%(asctime)s | worker | %(levelname)s | %(message)s")
)
logger.addHandler(handler)


def main():
    """Start the RQ worker, listening on the default queue."""
    logger.info("Starting AegisAI worker...")
    logger.info("Redis URL: %s", settings.redis_url)

    from app.workers.review_worker import run_review_job  # noqa: F401 — register the job function

    connection = Connection(redis.Redis.from_url(settings.redis_url))
    worker = Worker(["default"], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
