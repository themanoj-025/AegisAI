# AegisAI

<p align="center">
  <img src="https://img.shields.io/badge/AegisAI-AI%20Code%20Review-blue?style=for-the-badge" alt="AegisAI header banner: AI Code Review">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python version requirement: 3.11 or newer">
  <img src="https://img.shields.io/badge/FastAPI-0.143%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI version: 0.143 or newer">
  <img src="https://img.shields.io/badge/Redis-8.1%2B-DC382D?logo=redis&logoColor=white" alt="Redis version: 8.1 or newer">
  <img src="https://img.shields.io/badge/RQ-2.12%2B-blue?logo=python&logoColor=white" alt="Redis Queue version: 2.12 or newer">
  <img src="https://img.shields.io/badge/Tests-195%20passing-brightgreen" alt="Automated test suite: 195 tests collected">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

> An automated, security-focused code review agent for GitHub Pull Requests. It analyzes PR diffs in repository context, redacts sensitive tokens, classifies vulnerabilities through a hybrid deterministic and LLM reasoning pipeline (Claude / GPT), and posts line-anchored review comments prior to merge.

**Status:** Prototype portfolio project. Built to demonstrate asynchronous webhook ingestion, resilient task queues (RQ with Dead Letter Queue), secret redaction, and multi-provider LLM orchestration. Not an officially accredited static analysis tool.

<!-- TODO[L2-01]: Capture an end-to-end pull request review comment screenshot; save to docs/assets/pr-review.png (owner: Maintainer) -->

<p align="center">
  <a href="#what-it-does">What It Does</a> •
  <a href="#quick-facts">Quick Facts</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#engineering-highlights">Engineering Highlights</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#testing">Testing</a> •
  <a href="./LICENSE">License</a>
</p>

---

## What It Does

AegisAI automates security code reviews for pull requests on GitHub:

1. **HMAC Webhook Ingestion:** Receives GitHub `pull_request` webhook payloads, validates HMAC-SHA256 signatures in constant time, and acknowledges requests with HTTP `202 Accepted` within milliseconds to prevent webhook timeouts.
2. **Resilient Background Execution:** Enqueues review jobs onto Redis RQ with exponential retry backoff and a Dead Letter Queue (DLQ) to handle transient rate limits and provider outages.
3. **Workspace Isolation & Diff Parsing:** Clones the PR branch using temporary authenticated GitHub App tokens into isolated workspace directories, parses git diffs, and strips out noise files (lockfiles, vendor directories, minified bundles).
4. **Secret Redaction:** Redacts API tokens, private keys, passwords, and bearer tokens before sending code context to external LLM providers.
5. **Hybrid Review Engine:** Combines deterministic regex rules with semantic LLM evaluation (Anthropic Claude Sonnet or OpenAI GPT-4o) to eliminate false positives and score findings by severity (`blocking`, `warning`, `nit`).
6. **Line-Anchored Comments:** Formats and posts findings directly onto the offending lines in the GitHub PR review thread, with a summary report.

---

## Quick Facts

| Dimension | Specification | Evidence Source |
|:---|:---|:---|
| Project Type | Asynchronous GitHub App / Security Review Agent | `pyproject.toml`, `app/main.py` |
| Primary Language | Python (>= 3.11) | `pyproject.toml:8`, `Dockerfile` |
| Primary Framework | FastAPI (>= 0.143.0), Redis Queue (RQ >= 2.12.0) | `requirements.txt:1,13` |
| Supported LLM Gateways | Anthropic Claude (`claude-sonnet-4-20250514`), OpenAI (`gpt-4o`) | `app/config.py:27-28` |
| Queue & Broker | Redis (>= 8.1.0) with RQ and Dead Letter Queue | `requirements.txt:14`, `app/services/webhook_retry.py` |
| Test Suite | 195 collected tests across unit, integration, and security suites | `tests/` directory (`pytest`) |
| License | MIT License | `LICENSE` file |

---

## Architecture

```mermaid
flowchart TB
    subgraph GitHub["GitHub Ecosystem"]
        PR["Pull Request Event"]
        BOT["AegisAI PR Review Comments"]
    end

    subgraph API["FastAPI Webhook Service (app/main.py)"]
        HMAC["HMAC-SHA256 Signature Validator"]
        RATE["SlowAPI Rate Limiter"]
        ROUTER["Webhook Router (/api/v1/webhooks/github)"]
    end

    subgraph Broker["Task Queue & Reliability (Redis)"]
        QUEUE["Default Review Queue"]
        RETRY["Webhook Retry Queue"]
        DLQ["Dead Letter Queue (DLQ)"]
        SLACK["Slack Ops Alerts"]
    end

    subgraph Worker["Background Worker (worker.py)"]
        CLONE["Repo Manager (Isolated Temp Clone)"]
        DIFF["Diff Parser & Noise Filter"]
        REDACT["Secrets Redactor"]
        HYBRID["Hybrid Security Agent"]
        RULES["Deterministic Static Rules"]
        LLM["LLM Gateway (Claude / GPT-4o)"]
    end

    PR -->|Webhook POST| HMAC --> RATE --> ROUTER
    ROUTER -->|Enqueue 202| QUEUE
    ROUTER -.->|Failure Fallback| RETRY -->|Max Retries Exceeded| DLQ --> SLACK

    QUEUE --> Worker
    CLONE --> DIFF --> REDACT --> HYBRID
    HYBRID --> RULES
    HYBRID --> LLM
    HYBRID -->|Post Review API| BOT
```

*Data flow summary: Incoming GitHub webhook requests pass HMAC signature verification and rate limiting. Valid events are enqueued on Redis RQ. The decoupled background worker clones the PR branch into a secure temporary workspace, filters noise files, redacts secrets, runs deterministic rules and LLM evaluation, and posts line-anchored comments back to GitHub.*

---

## Tech Stack

### Backend & Orchestration
- **Runtime:** Python 3.11+
- **Web Framework:** FastAPI (v0.143+) with Uvicorn
- **Task Queue:** RQ (Redis Queue v2.12+) backed by Redis 8.1+
- **Configuration Management:** Pydantic Settings (`pydantic-settings>=2.6.0`)
- **HTTP Client:** HTTPX (`httpx>=0.28.1`) for asynchronous GitHub REST API communication
- **Authentication & Cryptography:** PyJWT (`>=2.15.1`) with cryptographic token signing

### AI & Security Pipeline
- **Anthropic SDK:** `anthropic>=1.13.0` (`claude-sonnet-4-20250514` model gateway)
- **OpenAI SDK:** `openai>=3.28.0` (`gpt-4o` model gateway)
- **Retry & Resilience:** `tenacity>=9.2.1` with custom circuit breaker (`app/circuit_breaker.py`)
- **Rate Limiting:** `slowapi>=0.1.10`
- **Secrets Redaction:** Custom token entropy and prefix scanner (`app/services/secrets_redactor.py`)

### Observability & Infrastructure
- **Metrics:** Prometheus Client (`prometheus-client>=0.26.0`) exposing queue latency, review duration, and DLQ counters
- **Tracing:** OpenTelemetry SDK (`opentelemetry-api`, `opentelemetry-sdk`)
- **Containerization:** Multi-stage `Dockerfile`, Docker Compose (`docker-compose.yml`, `docker-compose.dev.yml`)

---

## Engineering Highlights

### Line-Anchored Severity Model
Findings are evaluated and categorized into actionable review levels:
- `blocking`: Exploitable vulnerabilities (e.g., SQL injection, remote code execution, unauthenticated endpoints) that halt PR merges.
- `warning`: Architectural antipatterns or missing security defenses (e.g., lack of rate limits, missing CSRF protection).
- `nit`: Cosmetic maintainability recommendations or style discrepancies.

### Secrets Redaction Pipeline
Before diff snippets are transmitted to external AI APIs, `app/services/secrets_redactor.py` executes a high-speed regex and entropy scan to scrub sensitive data:
- Private key blocks (`-----BEGIN RSA PRIVATE KEY-----`)
- AWS access keys (`AKIA...`)
- Generic API keys, passwords, and authorization bearer tokens
- Matched tokens are replaced with typed redaction markers (`[REDACTED_API_KEY]`), preventing credential leakage into prompt logs.

### Dead Letter Queue (DLQ) & Ops Alerting
Webhook delivery spikes or LLM provider outages do not cause dropped events:
- Ingestion failures trigger immediate fallback to `webhook-retry` queues with exponential backoff (`60, 300, 900, 1800` seconds).
- Events exhausting max retry attempts are safely moved to the Dead Letter Queue.
- The DLQ emits Prometheus gauge metrics and can trigger automated Slack webhook notifications (`ALERT_WEBHOOK_URL`).

---

## Prerequisites

Before running AegisAI, ensure you have installed:
- **Python:** Version 3.11 or newer (`python --version`)
- **Redis:** Version 7 or newer (or run via Docker)
- **Git:** Installed and available on your system path
- **GitHub App:** App ID, Webhook Secret, and Private Key (PEM) configured on GitHub

---

## Quick Start

### Option A — Local Development

#### 1. Clone the repository
```bash
git clone https://github.com/themanoj-025/AegisAI.git
cd AegisAI
```

#### 2. Set up virtual environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

**On Linux / macOS (Bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

#### 3. Configure environment variables
```bash
cp .env.example .env
```
*(On Windows cmd: `copy .env.example .env`). Populate your GitHub App credentials, Redis URL, and LLM API keys.*

#### 4. Start Redis
```bash
# If running Redis via Docker
docker run -d --name aegis-redis -p 6379:6379 redis:7-alpine
```

#### 5. Start the FastAPI Webhook Service
```bash
uvicorn app.main:app --reload --port 8000
```
Expected output:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

#### 6. Start the Background Worker (Separate terminal)
```bash
python worker.py
```
Expected output:
```text
[INFO] Starting AegisAI worker...
[INFO] Redis URL: redis://localhost:6379
[INFO] Listening on queues: default, webhook-retry
[INFO] Worker listening on default, webhook-retry...
```

---

### Option B — Containerized Setup (Docker Compose)

Launch the API server, background RQ worker, and Redis broker in containerized isolation:

```bash
# 1. Prepare environment
cp .env.example .env

# 2. Build and start services
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

# 3. Follow logs
docker compose logs -f
```

To stop all containers and tear down the network:
```bash
docker compose down
```

---

## Configuration

Settings are parsed in [`app/config.py`](app/config.py) via Pydantic Settings from your local `.env` file:

| Variable | Required | Default | Description | Secret |
|:---|:---:|:---|:---|:---:|
| `GITHUB_APP_ID` | **Yes** | `""` | The unique GitHub App numeric identifier | No |
| `GITHUB_PRIVATE_KEY_PATH` | **Yes** | `./github-app-private-key.pem` | Path to the downloaded GitHub App private key PEM file | **Yes** |
| `GITHUB_WEBHOOK_SECRET` | **Yes** | `""` | Secret configured on GitHub for webhook HMAC signature checks | **Yes** |
| `LLM_PROVIDER` | No | `anthropic` | AI provider gateway: `anthropic` or `openai` | No |
| `ANTHROPIC_API_KEY` | No (if using OpenAI) | `""` | API key for Anthropic Claude (`claude-sonnet-4-20250514`) | **Yes** |
| `OPENAI_API_KEY` | No (if using Anthropic) | `""` | API key for OpenAI (`gpt-4o`) | **Yes** |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection URL for task broker and DLQ | **Yes** |
| `DATABASE_URL` | No | `postgresql://user:pass@localhost:5432/aegisai` | PostgreSQL database connection URL for audit logs | **Yes** |
| `WORKSPACE_DIR` | No | `./workspace` | Directory for temporary git checkouts during diff analysis | No |
| `AEGIS_API_KEY` | No | `""` | Optional API key to restrict administrative API routes | **Yes** |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated list of allowed browser origins | No |
| `ALERT_WEBHOOK_URL` | No | `""` | Incoming Slack webhook URL for Dead Letter Queue alerts | **Yes** |

---

## Project Structure

```text
AegisAI/
├── app/
│   ├── agents/                    # AI security review agents (Claude / GPT orchestration)
│   ├── logging/                   # Structured JSON logging and context formatting
│   ├── services/                  # Business services:
│   │   ├── diff_service.py        # Unified diff parsing and noise file exclusion
│   │   ├── queue.py               # Redis and RQ task connection management
│   │   ├── repo_manager.py        # Secure git clone and workspace directory manager
│   │   ├── secrets_redactor.py    # Pre-submission token and key redaction engine
│   │   └── webhook_retry.py       # DLQ retry queue, backoff, and Slack alerting
│   ├── workers/                   # Asynchronous background job implementations
│   ├── circuit_breaker.py         # Failure circuit breaker for external calls
│   ├── config.py                  # Pydantic Settings schema and environment loading
│   ├── health.py                  # Health check and diagnostic API endpoints
│   ├── main.py                    # FastAPI application, HMAC auth, and webhook router
│   └── tracing.py                 # OpenTelemetry tracer configuration
├── tests/                         # Automated test suite (195 test cases)
├── .env.example                   # Annotated environment variable configuration template
├── docker-compose.yml             # Primary Docker Compose configuration
├── docker-compose.dev.yml         # Development compose overrides
├── Dockerfile                     # Multi-stage production container build
├── Makefile                       # Ergonomic development commands
├── pyproject.toml                 # Package metadata and tool configurations
├── requirements.txt               # Pinned Python package dependencies
└── worker.py                      # Dedicated entrypoint for background RQ worker process
```

---

## Testing

The test suite validates webhook security, signature validation, secret redaction, diff parsing, and retry mechanics:

```bash
# Run the complete test suite
pytest tests/ -v

# Run unit tests only
pytest tests/ -m "unit" -v

# Run with test coverage report
pytest tests/ --cov=app --cov-report=term-missing

# Run documentation anchor, link, and fence validation
python .github/scripts/lint_readme.py
```

---

## Limitations and Threat Model

- **Heuristic Assistance:** AegisAI is designed as an automated code reviewer to assist engineering teams. It does not replace comprehensive manual penetration testing or formal security verification.
- **Context Window Boundaries:** Very large PRs (exceeding multi-file token limits) are batched. Cross-file architectural logic spanning files outside the pull request diff may not be visible to the LLM agent without whole-repository indexing.
- **Provider Outages:** When third-party AI APIs experience downtime, the system falls back to deterministic rule analysis and logs DLQ events for later reprocessing.

---

## Contributing

Contributions, feedback, and security improvements are welcome! Please review [CONTRIBUTING.md](./CONTRIBUTING.md) before submitting pull requests.

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/enhanced-cwe-check`).
3. Commit your changes following Conventional Commits (`git commit -m 'feat: add detection for prototype pollution'`).
4. Ensure all tests and linters pass (`pytest tests/` and `python .github/scripts/lint_readme.py`).
5. Submit a Pull Request.

---

## Security

Please report vulnerabilities confidentially according to our security policy in [SECURITY.md](./SECURITY.md). Do not file public issues for active security exploits.

---

## License

This project is licensed under the terms of the MIT License. See [LICENSE](./LICENSE) for details.
