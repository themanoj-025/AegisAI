# MEMORY.md — AegisAI

## Project Overview
**AegisAI** is an automated, security-focused code review system for GitHub pull requests. It listens for GitHub webhook events, queues review jobs via Redis/RQ, clones the PR branch, extracts the diff, redacts secrets, and sends the diff to an LLM (Claude/GPT-4) for security analysis. The AI review is posted back as a GitHub PR review comment.

## Business Purpose
Automate security code review for GitHub repositories. Catches vulnerabilities (SQL injection, XSS, hardcoded secrets, etc.) before they reach production, reducing manual review burden on security teams.

## Tech Stack
| Category | Technology |
|-----------|-----------|
| **Runtime** | Python 3.10+ |
| **Web Framework** | FastAPI |
| **Queue** | Redis + RQ (Redis Queue) |
| **LLM Providers** | Anthropic Claude, OpenAI GPT-4 |
| **Auth** | PyJWT (GitHub App JWT) |
| **HTTP Client** | httpx |

## Architecture
```
GitHub PR Webhook → FastAPI Receiver → Redis Queue → RQ Worker
→ Clone Repo → Diff Extraction → Secrets Redaction
→ LLM Security Agent → Post Review to GitHub
```

## Key Processes
1. **Webhook Receiver** (FastAPI) — Validates webhook secret, enqueues review job
2. **Worker** (RQ) — Processes queue: clone repo, extract diff, redact secrets, call LLM, post review
3. **LLM Agent** — Sends diff to Claude/GPT-4 with security-focused prompt, parses response

## Data Flow
1. Developer opens/closes a GitHub PR
2. GitHub sends webhook to FastAPI server
3. Server validates webhook signature, enqueues job to Redis
4. RQ Worker picks up job, clones repo to workspace
5. Worker extracts git diff, redacts potential secrets
6. Worker calls LLM API with security analysis prompt
7. LLM response is posted as a GitHub PR review
8. Workspace is cleaned up after job completion

## Environment Variables
| Variable | Purpose |
|-----------|---------|
| GITHUB_APP_ID | GitHub App ID for authentication |
| GITHUB_PRIVATE_KEY_PATH | Path to GitHub App private key |
| GITHUB_WEBHOOK_SECRET | Webhook secret for request validation |
| LLM_PROVIDER | Choose between "anthropic" or "openai" |
| ANTHROPIC_API_KEY | Claude API key |
| OPENAI_API_KEY | OpenAI API key |
| REDIS_URL | Redis connection string |
| DATABASE_URL | PostgreSQL connection string |
| WORKSPACE_DIR | Directory for cloned repos |

## Key Files
| File | Purpose |
|------|---------|
| `worker.py` | RQ worker entry point |
| `requirements.txt` | Python dependencies |
| `app/main.py` | FastAPI application |
| `app/config.py` | Settings via pydantic-settings |
| `app/workers/review_worker.py` | Review job processing logic |

## Deployment
- Three processes needed: Redis, FastAPI server, RQ Worker
- Webhook forwarding via ngrok or smee.io for local development
