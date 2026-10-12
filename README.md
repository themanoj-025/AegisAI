<p align="center">
  <img src="https://img.shields.io/badge/AegisAI-AI%20Code%20Review-blue?style=for-the-badge" alt="AegisAI Logo" />
</p>

<h1 align="center">AegisAI</h1>

<p align="center">
  <strong>Automated security-focused code review agent for GitHub Pull Requests.</strong>
</p>

<p align="center">
  <a href="https://github.com/themanoj-025/AegisAI/actions"><img src="https://img.shields.io/github/actions/workflow/status/themanoj-025/AegisAI/ci.yml?style=flat-square&label=CI" alt="CI Status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License MIT" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/stargazers"><img src="https://img.shields.io/github/stars/themanoj-025/AegisAI?style=social" alt="GitHub Stars" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/issues"><img src="https://img.shields.io/github/issues/themanoj-025/AegisAI?style=flat-square" alt="GitHub Issues" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="PRs Welcome" /></a>
</p>

---

## Overview

AegisAI inspects pull request diffs directly within repository context, spots security anti-patterns and vulnerabilities, ranks findings by severity, and posts line-anchored comments before vulnerable code reaches production.

It pairs deterministic static detection rules (for zero false positives on secrets, injection, and auth bugs) with semantic LLM reasoning (Claude or GPT) to understand complex control flow and business logic.

> [!NOTE]
> AegisAI operates fully even without an external LLM key. Setting `LLM_PROVIDER=unknown` enables the deterministic engine to flag vulnerabilities offline with zero API calls.

---

## Table of Contents

- [Key Features](#key-features)
- [Detection Coverage](#detection-coverage)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Quick Start](#installation--quick-start)
- [Configuration](#configuration)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)
- [Support](#support)

---

## Key Features

- **Line-Anchored Inline Feedback**: Delivers actionable review comments directly to the precise diff line containing a flaw.
- **Deterministic + LLM Hybrid**: Combines high-speed pattern checkers with LLM contextual reasoning to maximize signal-to-noise ratio.
- **Structured Severity Levels**: Categorizes findings as `blocking` (critical security risks), `warning` (high priority), or `nit` (code hygiene).
- **Asynchronous Webhook Queue**: Rapidly returns `202 Accepted` to GitHub while delegating processing to an RQ-based worker pool with Dead Letter Queue (DLQ) support.
- **Defensive Production Headers**: Enforces strict CSP (`default-src 'none'`), frame isolation, and cryptographic HMAC-SHA256 webhook validation.

---

## Detection Coverage

| Category | Real-World Targets Checked |
| :--- | :--- |
| **Injection Flaws** | SQL injection, raw shell command execution, unsanitized LDAP queries |
| **Authentication & AuthZ** | Hardcoded API tokens, broken access control checks, privilege escalation bugs |
| **Data Exposure** | Secret leakage in application logs, verbose exception traces, unmasked PII |
| **Insecure Dependencies** | Known vulnerable components and insecure dependency declarations |
| **CWE Common Weaknesses** | Frequent CWE patterns including CWE-22 (path traversal), CWE-79 (XSS), CWE-89 (SQLi) |

---

## Architecture

```text
GitHub Webhook (PR Event)
       │
       ▼ [HMAC-SHA256 Verification]
FastAPI Ingestion Service (/webhooks/github)
       │
       ▼ [Enqueue Task]
Redis Task Queue (RQ + DLQ)
       │
       ▼ [Worker Execution]
AegisAI Analyzer Engine (worker.py)
   ├── 1. Deterministic Rule Matching (Zero-false-positive checks)
   └── 2. Semantic LLM Gateway (Claude Sonnet / GPT-4o analysis)
       │
       ▼ [Post Line-Anchored Comments]
GitHub Pull Request Review API
```

---

## Project Structure

```text
AegisAI/
├── app/
│   ├── agents/                 # LLM agent definitions & prompt pipelines
│   ├── api/                    # Health & internal management routes
│   ├── logging/                # Structured JSON logging & correlation IDs
│   ├── services/               # Redis queue, webhook retries & DB connectors
│   ├── workers/                # Review task worker orchestration
│   ├── circuit_breaker.py      # Circuit breakers for external LLM calls
│   ├── config.py               # Pydantic v2 application settings
│   ├── health.py               # Liveness & readiness probes
│   └── main.py                 # FastAPI application & webhook entry point
├── tests/                      # Pytest unit & integration test suites
├── docker-compose.yml          # Core Redis + API + Worker stack
├── docker-compose.dev.yml      # Local development overrides
├── docker-compose.prod.yml     # Production deployment topology
├── Dockerfile                  # Container build instructions
├── Makefile                    # Ergonomic developer commands
├── pyproject.toml              # Build backend, Ruff & Pytest configuration
├── requirements.txt            # Python dependencies
├── worker.py                   # RQ worker entry point
└── README.md                   # Project documentation
```

---

## Prerequisites

- **Python**: `>= 3.11` (Python 3.12 recommended)
- **Redis**: `>= 6.0` (required for RQ job queues)
- **Docker & Docker Compose**: Optional, for containerized execution
- **GitHub App Credentials**: `GITHUB_APP_ID`, `GITHUB_WEBHOOK_SECRET`, and a private key (`.pem`)

---

## Installation & Quick Start

### Option A: Local Python Environment

```bash
# 1. Clone repository
git clone https://github.com/themanoj-025/AegisAI.git
cd AegisAI

# 2. Create virtual environment
python -m venv .venv
# On Linux/macOS: source .venv/bin/activate
# On Windows: .venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Start the web server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a separate terminal, launch the worker:

```bash
python worker.py
```

### Option B: Docker Compose

```bash
# Start Redis, API server, and background worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

# Tail logs
docker compose logs -f
```

---

## Configuration

All configuration is driven via environment variables and loaded by `app/config.py`.

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `GITHUB_APP_ID` | `""` | GitHub App ID for authentication |
| `GITHUB_PRIVATE_KEY_PATH` | `./github-app-private-key.pem` | Path to GitHub App private key PEM file |
| `GITHUB_WEBHOOK_SECRET` | `""` | Secret token used to verify HMAC-SHA256 webhook signatures |
| `LLM_PROVIDER` | `anthropic` | LLM backend: `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | `""` | API key when `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | `""` | API key when `LLM_PROVIDER=openai` |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Anthropic model identifier |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model identifier |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection URL |
| `AEGIS_API_KEY` | `""` | Optional API key for internal `/api/v1` routes |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins |

---

## Testing

AegisAI uses `pytest` with code coverage verification configured in `pyproject.toml`.

```bash
# Run unit and integration tests
pytest tests/ -v

# Run with test coverage report
pytest --cov=app tests/

# Execute tests via Makefile in Docker
make test
```

---

## Roadmap

- [x] Inline line-anchored security comments for GitHub PRs
- [x] Multi-tier severity ranking (`blocking`, `warning`, `nit`)
- [x] Deterministic security scanner fallback (zero-LLM operation)
- [x] Redis RQ job queue with retry backoff and Dead Letter Queue (DLQ)
- [x] Structured JSON artifact report generation
- [ ] Public demonstration instance <!-- TODO: Track in GitHub issue -->

---

## Contributing

Contributions are welcomed! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for code conventions, linting rules (`ruff`), and testing guidelines before submitting a pull request.

---

## Security

Please report vulnerabilities confidentially following the instructions in [SECURITY.md](SECURITY.md). Do not disclose security issues through public issue trackers.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Support

- 🐛 **Issue Tracker**: Report bugs and request features at [GitHub Issues](https://github.com/themanoj-025/AegisAI/issues).
- 💬 **Discussions & Feedback**: Submit ideas or reach out through [Pull Requests](https://github.com/themanoj-025/AegisAI/pulls).
