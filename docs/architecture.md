# Architecture — AegisAI

## System Architecture
```
GitHub (PR Webhook)
     │
     ▼
FastAPI Receiver ───→ Redis Queue ───→ RQ Worker
(app/main.py)                            (worker.py)
     │                                       │
     │                                  Clone Repo (workspace/)
     │                                       │
     │                                  Extract Diff
     │                                       │
     │                                  Secrets Redaction
     │                                       │
     │                                  LLM API (Claude/GPT)
     │                                       │
     │                                  Post Review to GitHub
     │
PostgreSQL (optional, for logging)
```

## Process Architecture
The app runs as **3 separate processes**:
1. **Redis** — Message broker for the job queue
2. **FastAPI Server** — HTTP server receiving GitHub webhooks
3. **RQ Worker** — Background worker processing review jobs

## Request Lifecycle
1. GitHub sends PR webhook → FastAPI endpoint
2. Webhook validated via signature verification
3. Job enqueued to Redis queue
4. Worker picks up job → clones repo → extracts diff
5. Secrets redacted from diff
6. LLM called with security analysis prompt
7. Review posted back to GitHub as PR review comment
8. Workspace cleaned up
