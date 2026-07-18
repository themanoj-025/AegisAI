"""FastAPI application for AegisAI — an AI-powered code review tool.

This module handles GitHub webhook events, verifies their authenticity,
and queues review jobs for processing.
"""

import hashlib
import hmac
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.queue import acquire_review_lock, get_queue
from app.workers.review_worker import run_review_job

logger = logging.getLogger("aegisai")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
)
logger.addHandler(handler)

app = FastAPI(title="AegisAI", version="0.1.0")

# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none';"
    )
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"  # enable when HTTPS
    return response


def verify_github_signature(payload: bytes, signature_header: str | None) -> bool:
    """Verify the X-Hub-Signature-256 header using HMAC-SHA256.

    Uses hmac.compare_digest to prevent timing attacks.
    """
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    expected_prefix = "sha256="
    if not signature_header.startswith(expected_prefix):
        logger.warning("Invalid signature format: missing sha256= prefix")
        return False

    received_sig = signature_header[len(expected_prefix) :]
    secret = settings.github_webhook_secret.encode("utf-8")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(received_sig, expected_sig)


@app.get("/health")
async def health_check():
    """Simple health check endpoint for deployment probes."""
    return {"status": "ok"}


@app.post("/webhooks/github")
async def github_webhook(request: Request):
    """Receive, verify, and acknowledge GitHub webhook events.

    Reads the raw request body for signature verification, validates the
    event type and action, extracts relevant PR metadata, and queues the
    review job for background processing.
    """
    # Read raw body before any JSON parsing — signature is over raw bytes
    raw_body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(raw_body, signature):
        logger.warning("Webhook rejected: invalid or missing signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event type
    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type != "pull_request":
        logger.debug("Ignoring event type: %s", event_type)
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": f"unhandled event type: {event_type}"},
        )

    # Parse payload
    payload = json.loads(raw_body)
    action: str = payload.get("action", "")

    if action not in ("opened", "synchronize", "reopened"):
        logger.debug("Ignoring pull_request action: %s", action)
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": f"unhandled action: {action}"},
        )

    # Extract PR metadata
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    installation = payload.get("installation", {})

    repo_full_name: str = repo.get("full_name", "")
    pr_number: int = pr.get("number", 0)
    head_sha: str = pr.get("head", {}).get("sha", "")
    base_sha: str = pr.get("base", {}).get("sha", "")
    clone_url: str = repo.get("clone_url", "")
    installation_id: int = installation.get("id", 0)

    # Log the event clearly
    logger.info(
        "Webhook received | event=pull_request | action=%s | repo=%s | pr=%d | head_sha=%s",
        action,
        repo_full_name,
        pr_number,
        head_sha,
    )

    # Deduplication: check if a review is already in progress for this head SHA
    if not acquire_review_lock(repo_full_name, head_sha):
        logger.info(
            "Dedup: review already in progress/completed for %s PR #%d (head: %s)",
            repo_full_name,
            pr_number,
            head_sha[:7],
        )
        return {"status": "deduplicated"}

    # Enqueue the review job for background processing
    try:
        queue = get_queue()
        queue.enqueue(
            run_review_job,
            repo_full_name,
            pr_number,
            head_sha,
            base_sha,
            clone_url,
            installation_id,
        )
        logger.info(
            "Enqueued review job for %s PR #%d (head: %s)",
            repo_full_name,
            pr_number,
            head_sha[:7],
        )
    except Exception as e:
        logger.error(
            "Failed to enqueue review job for %s PR #%d: %s",
            repo_full_name,
            pr_number,
            e,
        )
        return {"status": "error", "detail": "queue_failed"}

    return {"status": "received"}
