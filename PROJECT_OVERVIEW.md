# AegisAI — AI-Powered Automated Code Review

> Automated security-focused code review for GitHub pull requests using LLM-powered analysis.

[![CI](https://github.com/user/aegisai/actions/workflows/ci.yml/badge.svg)](https://github.com/user/aegisai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](pyproject.toml)

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Tech Stack & Core Technologies](#2-tech-stack--core-technologies)
- [3. High-Level Architecture](#3-high-level-architecture)
- [4. Complete Folder Structure Tree](#4-complete-folder-structure-tree)
- [5. Exhaustive File-by-File & Folder-by-Folder Breakdown](#5-exhaustive-file-by-file--folder-by-folder-breakdown)
- [6. Data Models & Schemas](#6-data-models--schemas)
- [7. API Surface](#7-api-surface)
- [8. Configuration & Environment Variables](#8-configuration--environment-variables)
- [9. Build, Run & Deployment Instructions](#9-build-run--deployment-instructions)
- [10. Data & Control Flow Walkthroughs](#10-data--control-flow-walkthroughs)
- [11. Dependency Graph Summary](#11-dependency-graph-summary)
- [12. Testing Strategy](#12-testing-strategy)
- [13. Known Issues, Technical Debt & Assumptions](#13-known-issues-technical-debt--assumptions)
- [14. Glossary](#14-glossary)
- [15. Appendix](#15-appendix)

---

## 1. Executive Summary

**AegisAI** is an AI-powered automated code review tool designed to integrate directly with GitHub as a GitHub App. It listens for pull request webhook events, clones the repository, extracts diffs, runs them through a Large Language Model (LLM) security analysis pipeline, and posts structured, line-anchored security findings back to the pull request as inline comments and a summary review.

The project solves the problem of **manual security review bottlenecks** in software development teams. By automating the initial security pass on every PR, it helps developers catch vulnerabilities like SQL injection, XSS, hardcoded secrets, command injection, and broken authentication early — before human reviewers even look at the code.

**Target users**: Development teams using GitHub who want an automated security layer in their CI/CD pipeline without replacing human code review entirely.

**Who it's for**: DevSecOps engineers, security-conscious development teams, and open-source maintainers who want automated security scanning on every pull request.

**Why it exists**: Manual security reviews are slow, inconsistent, and often skipped under time pressure. AegisAI provides a consistent, always-on first pass that flags real issues with high confidence and posts them directly where developers already work — on the PR.

*Note: The core security analysis logic, LLM integration, and GitHub webhook handling are all explicitly documented in the source code. The target user profile and problem statement are inferred from the architecture and feature set.*

---

## 2. Tech Stack & Core Technologies

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Language | Python | 3.11+ | Primary language for all backend services |
| Web Framework | FastAPI | ≥0.115.0 | Webhook receiver HTTP server |
| ASGI Server | Uvicorn | ≥0.32.0 | Production ASGI server with hot reload |
| Task Queue | RQ (Redis Queue) | ≥1.16.0,<2.0 | Background job processing for review tasks |
| Cache/Queue Store | Redis | ≥5.2.0 | Job queue backend + deduplication locks |
| LLM Provider (Primary) | Anthropic Claude | ≥0.45.0 | AI security analysis (claude-sonnet-4-20250514) |
| LLM Provider (Alt) | OpenAI GPT | ≥1.55.0 | Alternative AI provider (gpt-4o) |
| Retry Library | Tenacity | ≥9.0.0 | Exponential backoff retries for LLM calls |
| HTTP Client | httpx | ≥0.28.0 | GitHub API communication |
| Auth/JWT | PyJWT[crypto] | ≥2.10.0 | GitHub App JWT generation (RS256) |
| Settings | pydantic-settings | ≥2.6.0 | Typed environment variable loading |
| Environment | python-dotenv | ≥1.0.0 | .env file loading |
| Containerization | Docker | — | Multi-stage builds (api/worker/dev) |
| Orchestration | Docker Compose | — | Local development and production deployment |
| CI/CD | GitHub Actions | — | Lint, test, security scan, Docker build |
| Linting | flake8 | — | Python static analysis |
| Security Scan | Bandit | — | Python security vulnerability scanning |
| Container Scan | Trivy | — | Docker image vulnerability scanning |
| Git Hooks | — | — | Local development quality gates |

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Platform                             │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐    │
│  │   PR     │───▶│   Webhook    │───▶│   GitHub API           │    │
│  │  Event   │    │   (POST)     │    │   (REST: Reviews)      │    │
│  └──────────┘    └──────┬───────┘    └───────────▲────────────┘    │
└─────────────────────────┼─────────────────────────┼─────────────────┘
                          │                         │
                          ▼                         │
┌─────────────────────────────────────────────────────────────────────┐
│                      AegisAI System                                 │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Webhook Receiver (app/main.py)                      │   │
│  │  • Validates X-Hub-Signature-256 (HMAC-SHA256)               │   │
│  │  • Filters: only pull_request events (opened/sync/reopen)    │   │
│  │  • Deduplicates via Redis SETNX lock                         │   │
│  │  • Enqueues review job to RQ                                 │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Redis (Queue + Dedup Locks)                                  │   │
│  │  • Job queue: "default"                                       │   │
│  │  • Dedup lock: "review_lock:{repo}:{sha}" (TTL 10min)        │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  RQ Worker (worker.py → app/workers/review_worker.py)         │   │
│  │                                                                │   │
│  │  Step 1: Get GitHub App installation token                     │   │
│  │  Step 2: Clone PR repo at head SHA (shallow clone, depth=50)  │   │
│  │  Step 3: Extract git diff between base and head SHAs          │   │
│  │  Step 4: Filter noise files (lockfiles, minified, vendor)     │   │
│  │  Step 5: Redact secrets from diff text                        │   │
│  │  Step 6: Batch files and send to LLM security agent           │   │
│  │  Step 7: Parse LLM JSON response with hallucination guard     │   │
│  │  Step 8: Post review to GitHub (inline + summary comments)    │   │
│  │  Step 9: Clean up workspace                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  LLM Gateway (app/services/llm_gateway.py)                   │   │
│  │  • Provider abstraction: Anthropic or OpenAI (swappable)      │   │
│  │  • Retry logic: 3 attempts, exponential backoff (2-30s)       │   │
│  │  • Rate limit and 5xx retry handling                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  GitHub Auth (app/services/github_auth.py)                   │   │
│  │  • JWT generation (RS256, 10min expiry)                       │   │
│  │  • Installation token exchange (1hr, cached with 2min buffer) │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Architectural Pattern**: **Event-Driven Microservices** (within a single deployment unit). The system uses a webhook-receiver + background-worker pattern separated by a Redis message queue. This is a simplified event-driven architecture where:
- The **webhook receiver** is stateless and lightweight (only validates + enqueues)
- The **worker** is the heavy lifter (clone, analyze, post)
- **Redis** provides both message queuing and deduplication locks

The pattern is justified by: the `app/main.py` webhook handler only enqueues jobs, `worker.py` consumes from the queue, and the `app/services/` folder contains independently testable service modules.

---

## 4. Complete Folder Structure Tree

```
AegisAI/
├── .dockerignore                    # Docker build context exclusions
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI pipeline
├── .gitignore                       # Git ignore rules
├── .vscode/
│   └── settings.json                # VS Code workspace settings
├── AGENTS.md                        # AI coding agent instructions
├── app/
│   ├── __init__.py                  # Package marker
│   ├── main.py                      # FastAPI application entry point
│   ├── config.py                    # pydantic-settings configuration
│   ├── agents/
│   │   ├── __init__.py              # Package marker
│   │   └── security_agent.py        # LLM-based security review agent
│   ├── services/
│   │   ├── __init__.py              # Package marker
│   │   ├── diff_extractor.py        # Git diff extraction & parsing
│   │   ├── github_auth.py           # GitHub App JWT + installation tokens
│   │   ├── github_reviewer.py       # Posts reviews to GitHub PR API
│   │   ├── llm_gateway.py           # LLM provider abstraction (Claude/GPT)
│   │   ├── queue.py                 # Redis queue + dedup locks
│   │   ├── repo_manager.py          # Repository cloning & cleanup
│   │   └── secrets_redactor.py      # Pre-LLM secret pattern redaction
│   └── workers/
│       ├── __init__.py              # Package marker
│       └── review_worker.py         # RQ job function for PR reviews
├── docker-compose.dev.yml           # Docker Compose dev overrides
├── docker-compose.prod.yml          # Docker Compose production overrides
├── docker-compose.yml               # Docker Compose base definition
├── Dockerfile                       # Multi-stage Docker build
├── docs/
│   ├── design/
│   │   ├── AppFlow.md               # Application flow documentation
│   │   └── Design.md                # System design document
│   ├── product/
│   │   └── PRD.md                   # Product requirements document
│   ├── project/
│   │   ├── ImplementationPlan.md    # Implementation roadmap
│   │   ├── RiskRegister.md          # Risk assessment
│   │   ├── Rules.md                 # Project rules/conventions
│   │   └── Tracker.md               # Progress tracker
│   ├── reference/
│   │   └── Glossary.md              # Domain terminology
│   └── technical/
│       ├── API.md                   # API documentation
│       ├── Deployment.md            # Deployment guide
│       ├── Schema.md                # Data schema documentation
│       ├── SecurityAndCompliance.md # Security & compliance notes
│       ├── TechSpec.md              # Technical specification
│       └── Testing.md               # Testing documentation
├── Makefile                         # Docker Compose convenience commands
├── PROJECT_ANALYSIS.md              # Repository audit report
├── PROJECT_OVERVIEW.md              # This file
├── pyproject.toml                   # Python tool configuration (black, isort, pytest)
├── README.md                        # Project README
├── requirements.txt                 # Python dependencies
├── scripts/
│   ├── git-safe-commit.sh           # Git commit helper script
│   └── test_llm_gateway.py          # Manual LLM gateway test script
├── worker.py                        # RQ worker process entry point
```

---

## 5. Exhaustive File-by-File & Folder-by-Folder Breakdown

### Root Files

#### `AegisAI/README.md`
- **File type**: Markdown documentation
- **Purpose**: Primary project documentation with architecture overview, local development setup instructions, testing checklist, and links to detailed docs.
- **Key content**: Architecture diagram (webhook → FastAPI → Redis → Worker → LLM → GitHub), prerequisites (Python 3.10+, Redis), setup instructions, full manual test checklist.
- **Dependencies**: None (standalone documentation)

#### `AegisAI/PROJECT_ANALYSIS.md`
- **File type**: Markdown documentation
- **Purpose**: Repository audit report from automated analysis. Documents modernization status ("Verified & Cleaned"), architecture alignment, and operations checklist.
- **Key content**: Target architecture (Clean Modular Layout), test verification result (`NO_TESTS_COLLECTED`), CI/CD verification status.
- **Dependencies**: None

#### `AegisAI/requirements.txt`
- **File type**: Text (pip requirements)
- **Purpose**: Pins all Python dependencies with minimum versions.
- **Key dependencies**: `fastapi>=0.115.0`, `uvicorn[standard]>=0.32.0`, `pydantic-settings>=2.6.0`, `python-dotenv>=1.0.0`, `PyJWT[crypto]>=2.10.0`, `httpx>=0.28.0`, `rq>=1.16.0,<2.0`, `redis>=5.2.0`, `anthropic>=0.45.0`, `openai>=1.55.0`, `tenacity>=9.0.0`
- **Note**: No test dependencies are listed here; they're installed separately in CI

#### `AegisAI/pyproject.toml`
- **File type**: TOML configuration
- **Purpose**: Configures Python tooling: Black (line-length=100, target Python 3.11), isort (black profile), pytest (minversion=7.0, testpaths=["tests"])
- **Key values**: `line-length = 100`, `target-version = ["py311"]`, `testpaths = ["tests"]`

#### `AegisAI/worker.py`
- **File type**: Python script (entry point)
- **Purpose**: Standalone entry point for the RQ background worker process. Imports `run_review_job` from `app.workers.review_worker`, creates a Redis connection, and starts the worker listening on the "default" queue.
- **Key exports**: `main()` function
- **Logic**: Creates `Worker(["default"], connection=redis.Redis.from_url(...))` and calls `worker.work()`
- **Side effects**: Connects to Redis, blocks until signal
- **Dependencies**: `redis`, `rq`, `app.config.settings`, `app.workers.review_worker`
- **Invoked by**: `python worker.py` (directly or via Docker CMD)

#### `AegisAI/Makefile`
- **File type**: Makefile
- **Purpose**: Docker Compose convenience commands for development workflow.
- **Key targets**: `up` (start dev stack), `down` (stop), `logs` (tail logs), `build` (build images), `shell`/`api-shell`/`worker-shell` (container shells), `test` (run pytest in container), `lint` (flake8 critical errors), `health` (curl health endpoint), `clean` (stop + remove volumes), `reset` (full rebuild from scratch)

#### `AegisAI/Dockerfile`
- **File type**: Dockerfile (multi-stage)
- **Purpose**: Multi-stage build with 4 targets: `base` (shared runtime with git/curl/tini), `deps` (Python dependencies), `api` (FastAPI receiver), `worker` (RQ worker), `dev` (hot reload + lint/test tools).
- **Key details**: Based on `python:3.11-slim`, creates non-root `aegisai` user (UID 10001), uses tini for PID-1 signal handling, healthcheck on `/health` endpoint.
- **Build targets**: `api` (default), `worker`, `dev`

#### `AegisAI/docker-compose.yml`
- **File type**: YAML (Docker Compose)
- **Purpose**: Base compose definition with 3 services: `redis` (Redis 7 Alpine), `api` (FastAPI webhook receiver), `worker` (RQ background processor).
- **Key details**: Services communicate via `aegisai-net` bridge network. Shared `workspace` volume for cloned repos. Environment variables passed through from host `.env`.

#### `AegisAI/docker-compose.dev.yml`
- **File type**: YAML (Docker Compose override)
- **Purpose**: Development overrides: hot reload (`uvicorn --reload`), source bind mounts (`./app:/app/app`), Redis exposed on host port 6379.

#### `AegisAI/docker-compose.prod.yml`
- **File type**: YAML (Docker Compose override)
- **Purpose**: Production hardening: explicit restart policies, memory limits (Redis: 256M, API: 512M, Worker: 1G), Docker secrets for private key injection.

#### `AegisAI/.dockerignore`
- **File type**: Text
- **Purpose**: Excludes .git, __pycache__, venvs, .env, *.pem, workspace/, IDE configs, CI/agent config from Docker build context.

#### `AegisAI/.gitignore`
- **File type**: Text
- **Purpose**: Ignores Python caches, .env, *.pem, workspace/, IDE configs, OS files, Docker secrets.

#### `AegisAI/.github/workflows/ci.yml`
- **File type**: YAML (GitHub Actions)
- **Purpose**: CI pipeline with 5 jobs: `lint` (flake8 + syntax check), `test` (pytest with coverage), `security-scan` (Bandit), `link-check` (lychee), `docker` (build + Trivy scan).
- **Triggers**: push/PR to main/master
- **Key details**: Python 3.11, sequential jobs (lint → test → docker), Trivy fails on CRITICAL/HIGH vulnerabilities.

---

### `AegisAI/app/` — Core Application Package

#### `AegisAI/app/__init__.py`
- **File type**: Python package marker
- **Purpose**: Empty file making `app` a Python package.

#### `AegisAI/app/main.py`
- **File type**: Python module (FastAPI application)
- **Purpose**: The primary FastAPI application. Handles GitHub webhook reception, signature verification, event filtering, deduplication, and job enqueuing.
- **Key exports**: `app` (FastAPI instance)
- **Key functions**:
  - `verify_github_signature(payload: bytes, signature_header: str | None) -> bool` — Verifies X-Hub-Signature-256 using HMAC-SHA256 with timing-safe comparison
  - `health_check()` — Simple GET `/health` returning `{"status": "ok"}`
  - `github_webhook(request: Request)` — POST `/webhooks/github` handler
- **Important logic**:
  1. Reads raw body for signature verification (before JSON parsing)
  2. Validates HMAC-SHA256 signature against `GITHUB_WEBHOOK_SECRET`
  3. Filters: only `pull_request` events with actions `opened`/`synchronize`/`reopened`
  4. Extracts PR metadata (repo, PR number, SHAs, clone URL, installation ID)
  5. Acquires dedup lock via Redis SETNX (10min TTL)
  6. Enqueues `run_review_job` to RQ with all PR metadata
- **Side effects**: Reads `GITHUB_WEBHOOK_SECRET` env var, connects to Redis
- **Dependencies**: `app.config.settings`, `app.services.queue`, `app.workers.review_worker`
- **Security features**: HMAC-SHA256 verification, security headers middleware (X-Content-Type-Options, X-Frame-Options, CSP, etc.)

#### `AegisAI/app/config.py`
- **File type**: Python module (configuration)
- **Purpose**: Typed settings class using pydantic-settings. All environment variables are loaded from `.env` and validated.
- **Key exports**: `settings` (singleton `Settings` instance)
- **Settings fields**:
  - `github_app_id: str` — GitHub App ID
  - `github_private_key_path: str` — Path to PEM private key (default: `./github-app-private-key.pem`)
  - `github_webhook_secret: str` — Webhook signature secret
  - `llm_provider: str` — "anthropic" or "openai" (default: "anthropic")
  - `anthropic_api_key: str` — Anthropic API key
  - `openai_api_key: str` — OpenAI API key
  - `claude_model: str` — Claude model name (default: `claude-sonnet-4-20250514`)
  - `openai_model: str` — GPT model name (default: `gpt-4o`)
  - `redis_url: str` — Redis connection URL (default: `redis://localhost:6379`)
  - `database_url: str` — PostgreSQL URL (unused in Phase 1)
  - `workspace_dir: str` — Clone workspace path (default: `./workspace`)
- **Configuration**: `frozen=True` (immutable), `env_file_encoding="utf-8"`

---

### `AegisAI/app/agents/` — AI Agent Modules

#### `AegisAI/app/agents/__init__.py`
- **File type**: Python package marker

#### `AegisAI/app/agents/security_agent.py`
- **File type**: Python module (core AI agent)
- **Purpose**: The centerpiece of AegisAI — takes parsed diffs, sends them to an LLM for security analysis, and returns structured, line-anchored findings with a hallucination guard.
- **Key exports**: `run_security_agent(pr_files: list[dict]) -> list[dict]`
- **Key functions**:
  - `run_security_agent(pr_files)` — Main entry point. Batches files, sends to LLM, verifies findings
  - `_extract_json(text: str) -> dict` — Robust JSON extraction from LLM responses (handles markdown fences, raw JSON)
  - `_verify_line_hint(line_hint: str, diff_text: str) -> bool` — Substring check to verify finding actually references real code
  - `_batch_files(files: list[dict]) -> list[list[dict]]` — Groups small files (<50 lines) into batches of up to 5, large files sent individually
- **Important logic**:
  1. Batches files: small files (<50 diff lines) grouped into batches of up to 5 or ~200 lines; large files sent individually
  2. For each batch: redacts secrets via `redact_secrets()`, builds user prompt with file statuses
  3. Calls LLM with system prompt instructing security review for 12 vulnerability categories
  4. Parses JSON response, extracts findings array
  5. **Hallucination guard**: For each finding, verifies `line_hint` actually appears in the diff text; marks non-matching findings as `low_confidence`
- **Vulnerability categories checked**: SQL injection, XSS, CSRF, hardcoded secrets, insecure deserialization, path traversal, SSRF, broken auth/authz, IDOR, unsafe eval/exec, command injection, insecure crypto
- **Finding schema**: `{file, line_hint, severity, category, description, recommendation, low_confidence}`
- **Dependencies**: `app.services.llm_gateway.call_llm`, `app.services.secrets_redactor.redact_secrets`
- **Side effects**: Makes LLM API calls (network), logs findings

---

### `AegisAI/app/services/` — Service Modules

#### `AegisAI/app/services/__init__.py`
- **File type**: Python package marker

#### `AegisAI/app/services/diff_extractor.py`
- **File type**: Python module
- **Purpose**: Runs `git diff` on cloned repos and parses output into per-file structured data with noise filtering.
- **Key exports**: `get_pr_diff(repo_path: str, base_sha: str, head_sha: str) -> list[dict]`
- **Key functions**:
  - `get_pr_diff(repo_path, base_sha, head_sha)` — Runs git diff, returns list of `{filename, status, diff_text}`
  - `_parse_diff_output(diff_text: str) -> list[dict]` — Parses unified diff format into per-file dicts
  - `_is_noise_file(filename: str) -> bool` — Checks against noise patterns
- **Noise patterns filtered**: `package-lock.json`, `yarn.lock`, `poetry.lock`, `pnpm-lock.yaml`, `*.min.js`, `*.min.css`, `node_modules/`, `vendor/`, `dist/`, `build/`, `.next/`, `__pycache__/`
- **Size limits**: Max 4000 diff lines per file (truncated with warning), warn at 50+ total files
- **Side effects**: Runs `git diff` subprocess, writes to filesystem (git operations)
- **Dependencies**: `subprocess`, `re`

#### `AegisAI/app/services/github_auth.py`
- **File type**: Python module
- **Purpose**: GitHub App authentication — generates JWTs and exchanges them for installation access tokens.
- **Key exports**: `get_installation_token(installation_id: int) -> str`
- **Key functions**:
  - `get_installation_token(installation_id)` — Returns valid token, using cache if available
  - `_generate_jwt() -> str` — Creates RS256-signed JWT (10min expiry, 60s clock drift buffer)
  - `_read_private_key() -> str` — Reads PEM file from disk
- **Important logic**:
  - In-memory token cache: `{installation_id: (token, expiry_timestamp)}`
  - 2-minute safety buffer before expiry (treats tokens as expired early)
  - JWT issued 60 seconds ago to handle clock drift
- **Side effects**: Reads private key file from filesystem, makes HTTP POST to GitHub API
- **Dependencies**: `httpx`, `jwt` (PyJWT), `app.config.settings`

#### `AegisAI/app/services/github_reviewer.py`
- **File type**: Python module
- **Purpose**: Posts AegisAI findings back to GitHub as PR reviews with inline comments and summary.
- **Key exports**: `post_review(repo_full_name, pr_number, head_sha, findings, installation_token, diff_files) -> dict`
- **Key functions**:
  - `post_review(...)` — Main entry. Builds review payload, posts to GitHub, falls back to summary-only on 422
  - `_build_review_body(findings, diff_files) -> dict` — Constructs review with severity summary + inline comments for high-confidence findings
  - `_map_hint_to_line(line_hint, filename, diff_files) -> int | None` — Maps line hints to actual line numbers using diff hunk headers
- **Important logic**:
  - Only posts inline comments for high-confidence findings (not `low_confidence`)
  - Falls back to summary-only review if GitHub returns 422 (line mapping error)
  - Severity breakdown in summary: 🔴 Critical, 🟠 High, 🟡 Medium, 🟢 Low
- **Side effects**: Makes HTTP POST to GitHub REST API
- **Dependencies**: `httpx`

#### `AegisAI/app/services/llm_gateway.py`
- **File type**: Python module
- **Purpose**: Swappable LLM provider abstraction. Routes to Anthropic Claude or OpenAI GPT based on config.
- **Key exports**: `call_llm(system_prompt: str, user_prompt: str, response_format: str = "json") -> str`
- **Key classes**:
  - `_LLMProvider(ABC)` — Abstract base class
  - `_AnthropicProvider` — Anthropic Claude implementation
  - `_OpenAIProvider` — OpenAI GPT implementation
- **Key functions**:
  - `call_llm(...)` — Public API. Retries up to 3 times with exponential backoff (2-30s)
  - `_get_provider() -> _LLMProvider` — Singleton provider factory
- **Important logic**:
  - Retry on `_RetryableError` (rate limits, 5xx) via tenacity
  - Non-retryable errors (401, 403, 400) raise immediately
  - Logs token usage (input/output tokens) for each call
  - JSON mode: Anthropic gets instruction in system prompt; OpenAI uses `response_format={"type": "json_object"}`
- **Side effects**: Makes HTTP requests to LLM APIs (network), logs token usage
- **Dependencies**: `anthropic`, `openai`, `tenacity`

#### `AegisAI/app/services/queue.py`
- **File type**: Python module
- **Purpose**: Redis queue setup and deduplication lock management.
- **Key exports**: `get_queue() -> rq.Queue`, `acquire_review_lock(repo_full_name, head_sha, ttl=600) -> bool`, `get_redis() -> redis.Redis`
- **Key functions**:
  - `get_redis()` — Lazy Redis connection singleton
  - `get_queue()` — Returns RQ queue on default connection
  - `acquire_review_lock(repo, sha, ttl)` — Redis SETNX lock with TTL (default 10min)
- **Side effects**: Connects to Redis, sets key with expiry
- **Dependencies**: `redis`, `rq`, `app.config.settings`

#### `AegisAI/app/services/repo_manager.py`
- **File type**: Python module
- **Purpose**: Repository cloning and workspace management for review.
- **Key exports**: `clone_pr_repo(clone_url, installation_token, head_sha, pr_number, repo_full_name) -> str`, `cleanup_workspace(path: str) -> None`
- **Key functions**:
  - `clone_pr_repo(...)` — Shallow clones (depth=50), checks out head SHA, returns local path
  - `cleanup_workspace(path)` — Recursive directory deletion
  - `_build_authenticated_clone_url(clone_url, token) -> str` — Injects token into URL: `https://x-access-token:{token}@github.com/...`
  - `_random_suffix(length=8) -> str` — Generates unique workspace path suffix
- **Important logic**:
  - Workspace path: `{workspace_dir}/{owner}_{repo}/pr_{number}_{random_suffix}`
  - Uses `subprocess.run` with timeout (120s clone, 30s checkout)
  - Cleans up workspace on failure (in `finally` block)
- **Side effects**: Creates directories, runs git subprocess, deletes directories
- **Dependencies**: `subprocess`, `shutil`, `app.config.settings`

#### `AegisAI/app/services/secrets_redactor.py`
- **File type**: Python module
- **Purpose**: Pre-LLM secret pattern redaction — defense-in-depth to prevent credential leakage through the LLM pipeline.
- **Key exports**: `redact_secrets(diff_text: str) -> str`
- **Key functions**:
  - `redact_secrets(diff_text)` — Replaces detected secrets with `[REDACTED_SECRET]`
- **Patterns detected** (4 regex patterns):
  1. `_RE_PRIVATE_KEY` — PEM private key blocks (`-----BEGIN ... PRIVATE KEY-----`)
  2. `_RE_AWS_KEY` — AWS access keys (`AKIA` prefix + 16 chars)
  3. `_RE_API_KEY` — Generic API key assignments (`api_key=`, `apikey=`, etc.)
  4. `_RE_SENSITIVE_ASSIGNMENT` — High-entropy strings in sensitive variable names (secret, token, password, credential, etc.)
- **Dependencies**: `re` (stdlib only)

---

### `AegisAI/app/workers/` — Background Worker Modules

#### `AegisAI/app/workers/__init__.py`
- **File type**: Python package marker

#### `AegisAI/app/workers/review_worker.py`
- **File type**: Python module
- **Purpose**: The RQ job function that orchestrates the entire review pipeline.
- **Key exports**: `run_review_job(repo_full_name, pr_number, head_sha, base_sha, clone_url, installation_id) -> None`
- **Important logic** (5-step pipeline):
  1. `get_installation_token(installation_id)` — Get GitHub token
  2. `clone_pr_repo(...)` — Clone repo at head SHA
  3. `get_pr_diff(local_path, base_sha, head_sha)` — Extract diff
  4. `run_security_agent(pr_files)` — LLM security analysis
  5. `post_review(...)` — Post results to GitHub
  - Always cleans up workspace in `finally` block
- **Side effects**: All service calls (network, filesystem, Redis, LLM)
- **Dependencies**: All `app.services.*` and `app.agents.security_agent`
- **Error handling**: Logs errors with full traceback, re-raises exceptions

---

### `AegisAI/scripts/` — Utility Scripts

#### `AegisAI/scripts/git-safe-commit.sh`
- **File type**: Shell script
- **Purpose**: Git commit helper (likely automates commit message formatting or pre-commit checks).

#### `AegisAI/scripts/test_llm_gateway.py`
- **File type**: Python script
- **Purpose**: Manual test script for the LLM gateway — validates that the configured provider (Claude or GPT) responds correctly.

---

### `AegisAI/docs/` — Documentation Directory

All files in `docs/` follow a structured documentation framework:

| Path | Purpose |
|------|---------|
| `docs/design/AppFlow.md` | Application flow diagrams and sequence charts |
| `docs/design/Design.md` | System design document |
| `docs/product/PRD.md` | Product requirements document |
| `docs/project/ImplementationPlan.md` | Development roadmap and milestones |
| `docs/project/RiskRegister.md` | Risk assessment and mitigation strategies |
| `docs/project/Rules.md` | Project conventions and coding rules |
| `docs/project/Tracker.md` | Progress tracking |
| `docs/reference/Glossary.md` | Domain terminology definitions |
| `docs/technical/API.md` | Full API route documentation |
| `docs/technical/Deployment.md` | Deployment procedures |
| `docs/technical/Schema.md` | Data schema documentation |
| `docs/technical/SecurityAndCompliance.md` | Security and compliance notes |
| `docs/technical/TechSpec.md` | Technical specification |
| `docs/technical/Testing.md` | Testing strategy documentation |

---

### `AegisAI/.vscode/` — IDE Configuration

#### `AegisAI/.vscode/settings.json`
- **File type**: JSON
- **Purpose**: VS Code workspace settings (likely Python linting/formatting configuration).

---

### `AegisAI/.github/` — GitHub Configuration

#### `AegisAI/.github/workflows/ci.yml`
- **File type**: YAML (GitHub Actions)
- **Purpose**: CI pipeline triggered on push/PR to main/master.
- **Jobs**:
  1. `lint` — flake8 (critical errors E9,F63,F7,F82 + warnings), Python syntax check via `py_compile`
  2. `test` — Install deps, check imports, run `pytest tests/ -v` with coverage
  3. `security-scan` — Bandit static security analysis
  4. `link-check` — Lychee broken link checker on docs (continue-on-error)
  5. `docker` — Validate compose files, build API + Worker images, Trivy vulnerability scan (fails on CRITICAL/HIGH)
- **Dependencies**: lint → test → docker (sequential), security-scan and link-check run in parallel

---

## 6. Data Models & Schemas

### Finding (LLM Output Schema)

The security agent produces findings with this structure:

```json
{
  "findings": [
    {
      "file": "string — exact filename as provided in diff",
      "line_hint": "string — literal line of code or closest identifiable snippet",
      "severity": "critical | high | medium | low",
      "category": "string — e.g. sql_injection, hardcoded_secret, xss, command_injection",
      "description": "string — specific to this code, not generic",
      "recommendation": "string — concrete fix suggestion"
    }
  ]
}
```

After hallucination guard processing, an additional field is added:
- `low_confidence: bool` — `True` if `line_hint` was not found in the actual diff text

### PR File (Diff Extraction Output)

```json
{
  "filename": "string — relative path of changed file",
  "status": "added | modified | deleted | renamed | binary",
  "diff_text": "string — the unified diff hunk text"
}
```

### GitHub Review Payload

```json
{
  "body": "string — Markdown summary with severity breakdown",
  "event": "COMMENT",
  "comments": [
    {
      "path": "string — file path",
      "line": "int — line number in the file",
      "body": "string — finding details with severity, category, description, recommendation"
    }
  ]
}
```

### Redis Dedup Lock

- **Key format**: `review_lock:{repo_full_name}:{head_sha}`
- **Value**: timestamp (string)
- **TTL**: 600 seconds (10 minutes)

### Token Cache (In-Memory)

- **Key**: `installation_id: int`
- **Value**: `(token: str, expiry_timestamp: float)`
- **Safety buffer**: 2 minutes before actual expiry

---

## 7. API Surface

| Method | Path | Purpose | Auth | Request | Response | File |
|--------|------|---------|------|---------|----------|------|
| `GET` | `/health` | Health check endpoint | None | — | `{"status": "ok"}` | `app/main.py` |
| `POST` | `/webhooks/github` | GitHub webhook receiver | HMAC-SHA256 signature | Raw JSON body (GitHub webhook payload) | `{"status": "received"}` or `{"status": "deduplicated"}` or `{"status": "ignored", "reason": "..."}` | `app/main.py` |

### Webhook Event Filtering

The webhook handler only processes:
- **Event type**: `pull_request`
- **Actions**: `opened`, `synchronize`, `reopened`
- All other events/actions return `{"status": "ignored"}`

### Security Headers (Middleware)

Every response includes:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-XSS-Protection: 0`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none';`

---

## 8. Configuration & Environment Variables

| Variable | Purpose | Default | Required | Consumed By | Example |
|----------|---------|---------|----------|-------------|---------|
| `GITHUB_APP_ID` | GitHub App identifier | `""` | Yes (prod) | `app/config.py` → `github_auth.py` | `"123456"` |
| `GITHUB_PRIVATE_KEY_PATH` | Path to GitHub App PEM private key | `./github-app-private-key.pem` | Yes (prod) | `app/config.py` → `github_auth.py` | `"/run/secrets/github-app-private-key.pem"` |
| `GITHUB_WEBHOOK_SECRET` | HMAC-SHA256 secret for webhook verification | `""` | Yes (prod) | `app/config.py` → `main.py` | `"my-webhook-secret"` |
| `LLM_PROVIDER` | Which AI provider to use | `"anthropic"` | No | `app/config.py` → `llm_gateway.py` | `"anthropic"` or `"openai"` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `""` | If provider=anthropic | `app/config.py` → `llm_gateway.py` | `"sk-ant-..."` |
| `OPENAI_API_KEY` | OpenAI API key | `""` | If provider=openai | `app/config.py` → `llm_gateway.py` | `"sk-..."` |
| `CLAUDE_MODEL` | Claude model name | `"claude-sonnet-4-20250514"` | No | `app/config.py` → `llm_gateway.py` | `"claude-sonnet-4-20250514"` |
| `OPENAI_MODEL` | GPT model name | `"gpt-4o"` | No | `app/config.py` → `llm_gateway.py` | `"gpt-4o"` |
| `REDIS_URL` | Redis connection string | `"redis://localhost:6379"` | No | `app/config.py` → `queue.py` | `"redis://redis:6379/0"` |
| `DATABASE_URL` | PostgreSQL connection string | `"postgresql://user:pass@localhost:5432/aegisai"` | No (Phase 1) | `app/config.py` | `"postgresql://..."` |
| `WORKSPACE_DIR` | Directory for cloned repos | `"./workspace"` | No | `app/config.py` → `repo_manager.py` | `"/app/workspace"` |

---

## 9. Build, Run & Deployment Instructions

### Prerequisites

- Python 3.11+
- Redis (for job queue)
- Docker & Docker Compose (for containerized deployment)
- GitHub App with webhook configured (for production)

### Local Development (Without Docker)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your values

# 4. Start Redis (Docker)
docker run -d -p 6379:6379 redis

# 5. Start FastAPI server (Terminal 1)
uvicorn app.main:app --reload

# 6. Start RQ worker (Terminal 2)
python worker.py
```

### Local Development (With Docker)

```bash
# Start full dev stack (Redis + API + Worker)
make up

# Or equivalently:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
make logs

# Run tests in container
make test

# Stop
make down
```

### Production Deployment

```bash
# Build and start production stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Ensure secrets are in place
# ./secrets/github-app-private-key.pem
```

### CI/CD Pipeline (GitHub Actions)

1. **Lint** → flake8 critical errors + Python syntax check
2. **Test** → pytest with coverage
3. **Security Scan** → Bandit static analysis
4. **Link Check** → Lychee broken link detection
5. **Docker** → Build images + Trivy vulnerability scan

### Make Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make up` | `docker compose up -d` | Start full dev stack |
| `make down` | `docker compose down` | Stop stack |
| `make logs` | `docker compose logs -f` | Tail logs |
| `make build` | `docker compose build` | Build images |
| `make test` | `docker compose exec api pytest` | Run tests |
| `make lint` | `docker compose exec api flake8` | Lint code |
| `make health` | `curl http://localhost:8000/health` | Check health |
| `make clean` | `docker compose down -v` | Stop + remove volumes |
| `make reset` | `clean + build --no-cache + up` | Full rebuild |

---

## 10. Data & Control Flow Walkthroughs

### Flow 1: New Pull Request Opened (Happy Path)

1. Developer opens a PR on GitHub
2. GitHub sends `POST /webhooks/github` with `X-GitHub-Event: pull_request` and action `opened`
3. `app/main.py:github_webhook()`:
   - Reads raw body for signature verification
   - Verifies HMAC-SHA256 against `GITHUB_WEBHOOK_SECRET`
   - Parses JSON payload, extracts PR metadata (repo, PR#, SHAs, clone URL, installation ID)
   - Calls `acquire_review_lock()` — Redis SETNX with 10min TTL
   - Enqueues `run_review_job` to RQ with all metadata
4. `app/workers/review_worker.py:run_review_job()`:
   - `get_installation_token(installation_id)` → JWT + GitHub API exchange
   - `clone_pr_repo(...)` → Shallow clone at head SHA
   - `get_pr_diff(...)` → `git diff base..head`, parse into per-file structs, filter noise
   - `run_security_agent(pr_files)`:
     - Batch files into groups
     - For each batch: `redact_secrets()` → build prompt → `call_llm()` → parse JSON
     - Verify each finding's `line_hint` against actual diff → mark `low_confidence`
   - `post_review(...)` → Build review payload, POST to GitHub API
   - `cleanup_workspace(...)` → Delete cloned repo
5. Developer sees AegisAI review on the PR with inline comments and summary

### Flow 2: Duplicate Webhook Event

1. GitHub sends duplicate webhook (same head SHA)
2. `app/main.py` calls `acquire_review_lock()` — returns `False` (lock already held)
3. Returns `{"status": "deduplicated"}` immediately
4. No review job is enqueued

### Flow 3: LLM Rate Limited

1. Worker calls LLM API, receives 429 (rate limit)
2. `llm_gateway.py` raises `_RetryableError`
3. Tenacity retries with exponential backoff: 2s, 4s, 8s (up to 3 attempts)
4. If all 3 attempts fail, the exception propagates to `review_worker.py`
5. Worker logs the error and re-raises (job fails in RQ)
6. Workspace is cleaned up in `finally` block

---

## 11. Dependency Graph Summary

### Internal Module Dependencies

```
app/main.py
  ├── app/config.py
  ├── app/services/queue.py
  └── app/workers/review_worker.py

app/workers/review_worker.py
  ├── app/agents/security_agent.py
  │   ├── app/services/llm_gateway.py
  │   │   └── app/config.py
  │   └── app/services/secrets_redactor.py
  ├── app/services/diff_extractor.py
  ├── app/services/github_auth.py
  │   └── app/config.py
  ├── app/services/github_reviewer.py
  ├── app/services/repo_manager.py
  │   └── app/config.py
  └── app/services/queue.py
      └── app/config.py

worker.py
  ├── app/config.py
  └── app/workers/review_worker.py
```

### External Package Purposes

| Package | Purpose | Used By |
|---------|---------|---------|
| `fastapi` | HTTP framework for webhook receiver | `app/main.py` |
| `uvicorn` | ASGI server | Entry point |
| `pydantic-settings` | Typed env var loading | `app/config.py` |
| `python-dotenv` | .env file loading | `app/config.py` |
| `PyJWT` | JWT generation for GitHub auth | `app/services/github_auth.py` |
| `httpx` | HTTP client for GitHub/LLM APIs | `github_auth.py`, `github_reviewer.py` |
| `rq` | Redis-backed task queue | `worker.py`, `app/services/queue.py` |
| `redis` | Redis client | `app/services/queue.py` |
| `anthropic` | Anthropic Claude API client | `app/services/llm_gateway.py` |
| `openai` | OpenAI GPT API client | `app/services/llm_gateway.py` |
| `tenacity` | Retry logic with backoff | `app/services/llm_gateway.py` |

---

## 12. Testing Strategy

### Test Types

- **Unit tests**: Not yet implemented (`NO_TESTS_COLLECTED` per PROJECT_ANALYSIS.md)
- **Integration tests**: Not yet implemented
- **Manual testing**: Documented in README.md with a full checklist

### Test Infrastructure

- **Framework**: pytest (configured in `pyproject.toml`)
- **Coverage**: `pytest-cov` available (installed in CI)
- **Test path**: `tests/` directory (currently empty or minimal)

### Manual Test Checklist (from README)

1. Open a PR with vulnerable code (e.g., SQL injection via f-string)
2. Within ~30-60 seconds, confirm a GitHub PR review appears from the App
3. Open a clean PR and confirm "no issues found" summary
4. Verify workspace folder is cleaned up after job completion

### LLM Gateway Test

- `scripts/test_llm_gateway.py` — Manual test script to validate LLM provider connectivity

---

## 13. Known Issues, Technical Debt & Assumptions

### Known Issues

1. **No automated tests**: The `tests/` directory exists but contains no collected tests. This is the most significant technical debt.
2. **`database_url` configured but unused**: `config.py` defines `DATABASE_URL` for PostgreSQL, but no database models or ORM exist in Phase 1. This is reserved for future use.

### Technical Debt

1. **In-memory token cache**: `_token_cache` in `github_auth.py` is a plain dict — not shared across workers. If multiple worker processes run, each maintains its own cache.
2. **In-memory dedup lock**: The dedup mechanism uses Redis (shared), which is correct for multi-worker setups.
3. **No retry for non-retryable LLM errors**: If the LLM returns a 400 (bad request), the job fails immediately without recovery.
4. **Hardcoded noise patterns**: The diff extractor's noise patterns are hardcoded regex — no configuration mechanism.
5. **No structured logging**: Uses `logging` module with basic formatter — no JSON structured logging for production observability.

### Assumptions

1. **Redis is available**: The system assumes Redis is running and accessible at `REDIS_URL`.
2. **GitHub App is pre-configured**: The system assumes a GitHub App is already created with appropriate permissions (pull requests: write, contents: read).
3. **Private key file exists**: `github_auth.py` assumes the PEM file exists at `GITHUB_PRIVATE_KEY_PATH`.
4. **LLM API keys are valid**: No startup validation of API keys.
5. **Single worker process**: The current architecture assumes a single RQ worker — no horizontal scaling documentation.

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| **AegisAI** | The project name — an AI-powered code review tool |
| **GitHub App** | A GitHub integration type that operates with its own identity, unlike OAuth apps |
| **Installation Token** | Short-lived (1hr) access token for GitHub API, obtained by exchanging a JWT with a specific installation ID |
| **JWT (JSON Web Token)** | RS256-signed token used to authenticate as a GitHub App |
| **Webhook** | HTTP callback from GitHub to AegisAI when events occur (e.g., PR opened) |
| **X-Hub-Signature-256** | HMAC-SHA256 signature header sent by GitHub to verify webhook authenticity |
| **RQ (Redis Queue)** | Python library for job queuing backed by Redis |
| **LLM (Large Language Model)** | AI model used for security analysis (Claude or GPT) |
| **Hallucination Guard** | Verification step that checks if LLM-reported line references actually exist in the diff |
| **Diff** | The output of `git diff` showing changes between two commits |
| **Noise Files** | Files excluded from review: lockfiles, minified assets, vendor directories, build output |
| **Secrets Redactor** | Pre-LLM defense layer that replaces detected secrets with placeholders |
| **Inline Comment** | A review comment attached to a specific line in a PR file |
| **Deduplication Lock** | Redis key preventing the same webhook event from being processed twice |

---

## 15. Appendix

### LICENSE

The project includes a LICENSE file (type not explicitly read, but present in file tree). The README badges suggest MIT license.

### `.vscode/settings.json`

Contains VS Code workspace settings, likely configuring Python interpreter path, linting, and formatting preferences.

### `scripts/git-safe-commit.sh`

Shell script for safe git commits — likely handles pre-commit checks or commit message formatting. Specific content not read.

### `scripts/test_llm_gateway.py`

Manual test script for validating LLM provider configuration and connectivity. Used during development/debugging.

### Documentation Files (`docs/`)

The `docs/` directory contains a comprehensive documentation framework with design, product, project, reference, and technical sections. All files follow a consistent structure across the project organization.

---

*This document was generated as part of a comprehensive project documentation effort. Last updated: August 8, 2026.*
