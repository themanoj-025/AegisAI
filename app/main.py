"""FastAPI application for AegisAI — an AI-powered code review tool.

This module handles GitHub webhook events, verifies their authenticity,
and queues review jobs for processing.
"""

import hashlib
import hmac
import json
import secrets

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.logging.structured_logging import set_request_id, setup_logger
from app.services.queue import acquire_review_lock, get_queue
from app.workers.review_worker import run_review_job

try:
    from prometheus_client import Counter, Histogram, generate_latest

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False

logger = setup_logger("aegisai", context={"service": "aegisai", "version": "0.1.0"})

# ── Prometheus metrics ────────────────────────────────────────────────
if _PROM_AVAILABLE:
    REQUEST_COUNT = Counter(
        "aegisai_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "aegisai_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    WEBHOOK_RECEIVED = Counter(
        "aegisai_webhook_received_total", "Webhook events received", ["event", "action"])
    WEBHOOK_QUEUED = Counter(
        "aegisai_webhook_queued_total", "Review jobs enqueued", ["repo"])
    WEBHOOK_DUPES = Counter(
        "aegisai_webhook_deduped_total", "Deduplicated webhooks")

app = FastAPI(
    title="AegisAI",
    description="AI-powered code review tool with automated analysis and reporting.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "health",
            "description": "Service health check endpoints",
        },
        {
            "name": "webhooks",
            "description": "GitHub webhook integration for automated code reviews",
        },
        {
            "name": "reviews",
            "description": "Code review analysis and reporting",
        },
    ],
)
v1_router = APIRouter(prefix="/api/v1")
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> HTTPAuthorizationCredentials:
    """Verify API key from Authorization header. Enabled when AEGIS_API_KEY is set."""
    api_key = settings.aegis_api_key
    if not api_key:
        return credentials  # No key configured — open access
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not secrets.compare_digest(credentials.credentials, api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return credentials


# Apply auth to v1 routes (except health check)
log_level = "API key auth: ENABLED" if settings.aegis_api_key else "API key auth: DISABLED (open access)"
logger.info("%s", log_level)

# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# ── Rate Limiting ─────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def add_request_id_and_security_headers(request: Request, call_next) -> Any:
    import time as _time
    request.state.start_time = _time.time()
    """Add request ID and security headers to every response."""
    req_id = set_request_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    )
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"

    if _PROM_AVAILABLE:
        import time as _time

        path = request.url.path
        REQUEST_COUNT.labels(method=request.method, endpoint=path, status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=path).observe(
            _time.time() - request.state.start_time
            if hasattr(request.state, "start_time")
            else 0.0
        )

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


@v1_router.get("/health")
async def health_check() -> dict[str, Any]:
    """Simple health check endpoint for deployment probes."""
    return {"status": "ok"}


@app.post("/webhooks/github")
async def github_webhook(request: Request) -> Response:
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
        if _PROM_AVAILABLE:
            WEBHOOK_RECEIVED.labels(event=event_type, action="ignore").inc()
        return JSONResponse(
            status_code=200,
            content={
                "status": "ignored",
                "reason": f"unhandled event type: {event_type}",
            },
        )

    # Parse payload
    payload = json.loads(raw_body)
    action: str = payload.get("action", "")

    if action not in ("opened", "synchronize", "reopened"):
        if _PROM_AVAILABLE:
            WEBHOOK_RECEIVED.labels(event="pull_request", action=action).inc()
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

    if _PROM_AVAILABLE:
        WEBHOOK_RECEIVED.labels(event="pull_request", action=action).inc()

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
        if _PROM_AVAILABLE:
            WEBHOOK_DUPES.inc()
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
        if _PROM_AVAILABLE:
            WEBHOOK_QUEUED.labels(repo=repo_full_name).inc()
        logger.info(
            "Enqueued review job for %s PR #%d (head: %s)",
            repo_full_name,
            pr_number,
            head_sha[:7],
        )
    except (OSError, ValueError) as e:
        logger.error(
            "Failed to enqueue review job for %s PR #%d: %s",
            repo_full_name,
            pr_number,
            e,
        )
        return {"status": "error", "detail": "queue_failed"}

    return {"status": "received"}


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Prometheus metrics endpoint."""
    if not _PROM_AVAILABLE:
        return {"status": "prometheus_client not installed"}
    return Response(content=generate_latest(), media_type="text/plain")


app.include_router(v1_router)


@app.get("/health")
async def root_health_check() -> dict[str, Any]:
    """Root health check for Docker probes (backward compat)."""
    return {"status": "ok"}
