# Module Dependency — AegisAI

The dependency graph is **strictly acyclic and points downward**: entry points →
orchestration → domain agent + services → configuration. No circular imports.

## 1. Dependency Graph

```
  ENTRY POINTS
  ┌────────────────────────┐      ┌────────────────────────┐
  │ app/main.py            │      │ worker.py (root)       │
  │ FastAPI webhook receiver│     │ RQ worker process       │
  └───────────┬────────────┘      └───────────┬────────────┘
              │ imports                       │ imports
              ▼                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │ app/workers/review_worker.py   (job pipeline orchestrator)│
  └───────┬───────────────┬────────────────┬────────────────┘
          │               │                │
          ▼               ▼                ▼
  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐
  │ agents/      │  │ services/   │  │ services/            │
  │ security_    │  │ diff_       │  │ queue.py             │
  │ agent.py     │  │ extractor   │  │ (Redis RQ + locks)   │
  └──────┬───────┘  ├─ github_auth│  └──────────┬───────────┘
         │          ├─ github_reviewer         │
         │          ├─ repo_manager            │
         │          └─ secrets_redactor        │
         ▼                      │              │
  ┌─────────────────────────────▼──────────────┘
  │ app/services/llm_gateway.py  (provider abstraction)
  └──────────────────┬───────────────────────┘
                     ▼
  ┌───────────────────────────────────────────────┐
  │ app/config.py   (pydantic-settings, env-backed)│
  └───────────────────────────────────────────────┘
```

## 2. Module Dependency Matrix

| Module | Imports | Depends on | Consumed by |
| --- | --- | --- | --- |
| `app/main.py` | `app.config`, `app.services.queue`, `app.workers.review_worker` | FastAPI, Redis | uvicorn (`app.main:app`), Docker api target |
| `worker.py` | `app.config` | redis, rq | `python worker.py`, Docker worker target, CI import check |
| `app/workers/review_worker.py` | `app.agents.security_agent`, `app.services.*` (diff_extractor, github_auth, github_reviewer, repo_manager) | — | RQ worker (`run_review_job`) |
| `app/agents/security_agent.py` | `app.services.llm_gateway`, `app.services.secrets_redactor` | — | `review_worker` |
| `app/services/llm_gateway.py` | `app.config` | anthropic/openai, tenacity | `security_agent` |
| `app/services/secrets_redactor.py` | — (leaf) | stdlib | `security_agent` |
| `app/services/diff_extractor.py` | — (leaf) | git/stdlib | `review_worker` |
| `app/services/github_reviewer.py` | `app.config` | httpx, PyJWT | `review_worker` |
| `app/services/github_auth.py` | `app.config` | PyJWT, httpx | `review_worker` |
| `app/services/queue.py` | `app.config` | redis, rq | `main` (enqueue + lock) |
| `app/services/repo_manager.py` | `app.config` | subprocess/git | `review_worker` |
| `app/config.py` | — | pydantic-settings | everything (leaf) |

## 3. Why This Shape

- **Leaves are I/O + config bound**: `config.py` is the only module with zero
  internal imports; services depend only on config, keeping the graph shallow.
- **No import cycles**: `review_worker` orchestrates; no service imports a worker or
  the agent back up the stack.
- **`worker.py` at root** is a deliberate entry-point contract (CI imports
  `from worker import app`, Docker copies and runs it) — see the move ledger.

## 4. Change Warnings

- **Adding a service** should import only `app.config` (and leaf libs) to preserve acyclicity.
- **Moving `worker.py`** requires coordinated updates to `Dockerfile` (COPY + CMD),
  `docker-compose.dev.yml` (bind mounts + worker command), and CI's `from worker import app`.
- **Renaming env settings** in `app/config.py` breaks every service that reads them —
  keep the env surface frozen (protocol constraint).
