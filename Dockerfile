# syntax=docker/dockerfile:1
# ═══════════════════════════════════════════════════════════════════════
# AegisAI — AI-Powered Code Review (FastAPI receiver + RQ worker)
#
# Build targets:
#   api     (default) — uvicorn app.main:app  (webhook receiver, :8000)
#   worker            — python worker.py      (RQ background worker)
#   dev               — hot-reload uvicorn for local development
#
# Usage:
#   docker build --target api -t aegisai/api .
#   docker build --target worker -t aegisai/worker .
#   docker compose up -d          # full stack (redis + api + worker)
# ═══════════════════════════════════════════════════════════════════════

# ── Base stage: shared runtime ─────────────────────────────────────────
FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="AegisAI"
LABEL org.opencontainers.image.description="Automated security-focused code review for GitHub pull requests"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.vendor="AegisAI"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Runtime system deps:
#   - git  : the worker clones PR repositories (app/services/repo_manager.py)
#   - curl : used by the healthcheck
#   - tini : proper PID-1 signal handling / zombie reaping
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Deps stage: Python dependencies (cache-friendly layer) ────────────
FROM base AS deps

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── API stage: FastAPI webhook receiver ───────────────────────────────
FROM deps AS api

# Create a non-root runtime user with a fixed UID
RUN useradd --create-home --uid 10001 aegisai && \
    mkdir -p /app/workspace && \
    chown -R aegisai:aegisai /app

COPY app/ ./app/
COPY worker.py ./

USER aegisai

EXPOSE 8000

# /health is served by FastAPI (app/main.py)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Worker stage: RQ background worker ────────────────────────────────
FROM deps AS worker

RUN useradd --create-home --uid 10001 aegisai && \
    mkdir -p /app/workspace && \
    chown -R aegisai:aegisai /app

COPY app/ ./app/
COPY worker.py ./

USER aegisai

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "worker.py"]

# ── Dev stage: hot reload + lint/test tooling for local development ───
FROM deps AS dev

# flake8 (lint) is used by make lint inside the dev container; pytest
# comes from the base deps requirements but is pinned here for clarity.
RUN pip install --no-cache-dir flake8 pytest pytest-cov

RUN useradd --create-home --uid 10001 aegisai && \
    mkdir -p /app/workspace && \
    chown -R aegisai:aegisai /app

COPY app/ ./app/
COPY worker.py ./

USER aegisai

EXPOSE 8000

# --reload requires a mounted source tree (see docker-compose.dev.yml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
