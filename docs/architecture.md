# Architecture — AegisAI

A concise, current map of how AegisAI is built. The code remains the source of
truth; this document is the canonical architecture reference produced during
the v5.0 modernization pass.

## 1. System at a glance

AegisAI is an **AI-powered security code-review GitHub App**. When a pull
request is opened/synchronized/reopened, GitHub sends a webhook; AegisAI
verifies the HMAC signature, deduplicates via a Redis lock, and enqueues a
review job. A background RQ worker authenticates as the GitHub App, clones the
PR repo (shallow), extracts the diff, redacts secrets, sends the diff to an
LLM security agent (Claude or GPT-4o), verifies each finding against the real
diff (hallucination guard), and posts a PR review with inline comments and a
severity summary.

## 2. Layered model

```
┌──────────────────────────────────────────────────────────────────────┐
│  Interface / API                                                      │
│   app/main.py  — FastAPI: GET /health · POST /webhooks/github         │
│   worker.py    — RQ worker process entry point                        │
├──────────────────────────────────────────────────────────────────────┤
│  Application orchestration                                            │
│   app/workers/review_worker.py  — 6-step job pipeline                 │
├──────────────────────────────────────────────────────────────────────┤
│  Domain                                                               │
│   app/agents/security_agent.py — LLM review, batching, JSON parsing,  │
│                                   hallucination guard                 │
├──────────────────────────────────────────────────────────────────────┤
│  Services (cross-cutting + external I/O)                              │
│   diff_extractor   — git diff parsing, noise filtering, size caps     │
│   github_auth      — App JWT → installation token (cached)            │
│   github_reviewer  — PR review posting (inline + summary, 422 fallback)│
│   llm_gateway      — Anthropic/OpenAI provider abstraction + retries  │
│   queue            — Redis singleton, RQ queue, SETNX dedup locks     │
│   repo_manager     — shallow clone + workspace cleanup                │
│   secrets_redactor — pre-LLM secret pattern redaction                 │
├──────────────────────────────────────────────────────────────────────┤
│  Configuration                                                        │
│   app/config.py    — pydantic-settings (env-backed, frozen)           │
└──────────────────────────────────────────────────────────────────────┘
```

Dependencies point strictly downward and are acyclic: `main`/`worker` →
`review_worker` → services + agent → `config`. Leaves: `config`,
`diff_extractor`, `github_reviewer`, `secrets_redactor`.

## 3. Runtime flows

### 3.1 Webhook → review (happy path)
1. GitHub POSTs `pull_request` (action `opened`/`synchronize`/`reopened`) to
   `/webhooks/github`.
2. `main.py` verifies `X-Hub-Signature-256` (HMAC-SHA256, timing-safe).
3. `acquire_review_lock(repo, head_sha)` — Redis `SETNX` with 10-min TTL;
   if already held → `{"status": "deduplicated"}`.
4. Job enqueued on the RQ `default` queue with PR metadata.
5. `run_review_job`:
   - `get_installation_token` (JWT RS256 → exchange, 2-min expiry buffer)
   - `clone_pr_repo` (shallow `--depth=50`, checkout head SHA, random-suffix workspace path)
   - `get_pr_diff` (base..head; noise files filtered; 4000-line/file cap)
   - `run_security_agent` (batch ≤5 small files / ~200 lines; redact; LLM; parse JSON; verify `line_hint` against diff → `low_confidence` flag)
   - `post_review` (inline comments for high-confidence findings; summary body; falls back to summary-only on HTTP 422)
   - `cleanup_workspace` in `finally`.

### 3.2 Failure paths
- LLM rate limit / 5xx → tenacity retry (3 attempts, exponential 2–30s);
  non-retryable (401/403/400) raises immediately.
- Review API 422 (stale diff position) → summary-only fallback.
- Any worker exception → logged with traceback, re-raised (RQ marks failed),
  workspace always cleaned up.

## 4. Configuration surface

| Setting (env) | Default | Purpose |
|---|---|---|
| `GITHUB_APP_ID` / `GITHUB_PRIVATE_KEY_PATH` / `GITHUB_WEBHOOK_SECRET` | — | GitHub App auth + webhook verification |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | LLM credentials |
| `CLAUDE_MODEL` / `OPENAI_MODEL` | `claude-sonnet-4-20250514` / `gpt-4o` | Model selection |
| `REDIS_URL` | `redis://localhost:6379` | Queue + locks |
| `DATABASE_URL` | postgres placeholder | **Unused (reserved** for audit trail) |
| `WORKSPACE_DIR` | `./workspace` | Clone scratch space |

## 5. Persistence

| Artifact | Location | Note |
|---|---|---|
| Redis | external service | queue + dedup locks (no host port in base compose) |
| Workspace clones | `workspace/` (gitignored, docker volume) | ephemeral, cleaned per job |
| Audit DB | — | roadmap (Postgres), not implemented |

## 6. Deployment

- **Docker multi-stage**: `base` (python:3.11-slim, git/curl/tini) →
  `deps` → `api` / `worker` / `dev` targets; non-root `aegisai` user; tini as
  PID 1; healthcheck on `/health`.
- **Compose**: base `docker-compose.yml` (redis + api + worker on
  `aegisai-net`), `.dev.yml` (reload + bind mounts + host Redis port), `.prod.yml`
  (restart policies, memory limits, Docker secrets for the PEM key).
- **CI** (`.github/workflows/ci.yml`): flake8 (critical + warnings),
  `py_compile` syntax check, pytest (51 tests, all passing), Bandit,
  lychee link check, Docker build + Trivy (fails on CRITICAL/HIGH).

## 7. Key design decisions

1. **Event-driven receiver/worker split** — the webhook handler is stateless
   and fast (verify + dedup + enqueue); the heavy pipeline runs in RQ.
2. **Deduplication before work** — Redis SETNX lock keyed by repo + head SHA
   prevents duplicate reviews on re-delivered webhooks.
3. **Defense-in-depth before the LLM** — secret redaction runs before any diff
   reaches the model; the hallucination guard verifies findings cite real code.
4. **Provider abstraction** — `llm_gateway` hides Anthropic/OpenAI behind one
   `call_llm()`; retries confined to retryable errors.
5. **Best-effort line mapping** — findings that cannot be anchored to a diff
   line degrade to the summary body instead of failing the review.
