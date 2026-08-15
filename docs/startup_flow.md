# Startup Flow — AegisAI

Two independent processes serve the system: the **API** (FastAPI webhook receiver)
and the **worker** (RQ background processor), connected by Redis.

## 1. API Boot (uvicorn)

```
uvicorn app.main:app --host 0.0.0.0 --port 8000      # Docker: CMD in api target
│
├─ 1. app.config settings load (pydantic-settings ← .env)
├─ 2. FastAPI app constructed
├─ 3. CORS middleware added
├─ 4. HTTP middleware registered (request logging / guards)
├─ 5. Routes registered:
│      GET  /health          → {"status": "ok"}
│      POST /webhooks/github → verify HMAC → dedup lock → enqueue RQ job
└─ 6. Server ready on :8000 (healthcheck: curl /health)
```

## 2. Worker Boot (RQ)

```
python worker.py                                   # Docker: worker target
│
├─ 1. logging configured (stream handler, "aegisai" logger)
├─ 2. app.config settings load
├─ 3. Redis connection established
├─ 4. RQ Worker started on the default queue
│      (job functions registered from app.workers.review_worker)
└─ 5. Listening for jobs; runs run_review_job() per dequeued job
```

## 3. Webhook → Review Flow (end-to-end)

1. GitHub sends `pull_request` webhook (`opened`/`synchronize`/`reopened`) to
   `/webhooks/github` on the API.
2. `main.py` verifies `X-Hub-Signature-256` (HMAC-SHA256, timing-safe) using
   `GITHUB_WEBHOOK_SECRET`.
3. `acquire_review_lock(repo, head_sha)` — Redis `SETNX`, 10-min TTL; already held
   → `{"status": "deduplicated"}`.
4. Job enqueued with PR metadata on the RQ default queue → API responds 202.
5. Worker dequeues and runs `run_review_job`:
   - `get_installation_token` (GitHub App JWT → installation token, cached)
   - `clone_pr_repo` (shallow `--depth=50`, checkout head SHA, random-suffix workspace)
   - `get_pr_diff` (base..head; noise files filtered; 4000-line/file cap)
   - `run_security_agent` (batch ≤5 small files; **redact secrets** → LLM → parse JSON
     → hallucination guard: verify `line_hint` against the real diff → `low_confidence`)
   - `post_review` (inline comments for high-confidence findings + summary body;
     HTTP 422 → summary-only fallback)
   - `cleanup_workspace` in `finally`.

Failure paths: LLM retryable errors → tenacity 3 attempts (2–30s exponential backoff);
non-retryable (401/403/400) raise immediately; review 422 → degrade; worker exception
→ logged + re-raised (RQ marks failed), workspace always cleaned.

## 4. Docker Boot

- **api target**: `CMD ["uvicorn", "app.main:app", ...]` as non-root `aegisai` user;
  tini as PID 1; healthcheck `curl /health`.
- **worker target**: `CMD ["python", "worker.py"]`.
- **dev target**: uvicorn `--reload` + bind mounts (`docker-compose.dev.yml`).
- **compose**: base stack = redis + api + worker on `aegisai-net`; `.prod.yml` adds
  restart policies, memory limits, and Docker secrets for the GitHub App PEM key.

## 5. Configuration Surface

Loaded by `app/config.py` from `.env` (gitignored; `.env.example` is the template):

| Env var | Default | Purpose |
| --- | --- | --- |
| `GITHUB_APP_ID` / `GITHUB_PRIVATE_KEY_PATH` / `GITHUB_WEBHOOK_SECRET` | — | GitHub App auth + webhook verification |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | LLM credentials |
| `CLAUDE_MODEL` / `OPENAI_MODEL` | sonnet-4 / gpt-4o | Model selection |
| `REDIS_URL` | `redis://localhost:6379` | Queue + locks |
| `WORKSPACE_DIR` | `./workspace` | Clone scratch space (ephemeral, gitignored) |

## 6. Failure Modes

| Failure | Behavior |
| --- | --- |
| Redis down | API enqueue/lock calls fail loudly (no queueing) |
| Invalid webhook signature | 401, request dropped |
| LLM outage | Retried ×3 with backoff; then job fails (visible in RQ) |
| Stale diff position (422) | Summary-only review fallback |
| Workspace leak | Always cleaned in `finally`; volume is ephemeral |

See `docs/architecture.md` §3 for the canonical flow reference.
