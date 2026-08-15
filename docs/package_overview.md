# Package Overview — AegisAI

Inventory of every module (post-restructure). AegisAI is a small, layered FastAPI
application; the `app/` package is the entire runtime.

## 1. Application package (`app/`)

| Module | Responsibility | Entry point |
| --- | --- | --- |
| `app/main.py` | FastAPI webhook receiver: `GET /health`, `POST /webhooks/github`; HMAC verification, Redis dedup lock, RQ enqueue. | `uvicorn app.main:app` |
| `app/config.py` | pydantic-settings configuration (env-backed, frozen). | — |
| `app/agents/security_agent.py` | LLM security review: diff batching, secret redaction call, JSON parsing, hallucination guard (`low_confidence`). | — |
| `app/services/diff_extractor.py` | git diff parsing, noise filtering, size caps (4000 lines/file). | — |
| `app/services/github_auth.py` | GitHub App JWT → installation token, cached. | — |
| `app/services/github_reviewer.py` | PR review posting (inline + summary, 422 fallback). | — |
| `app/services/llm_gateway.py` | Anthropic/OpenAI provider abstraction + tenacity retries. | — |
| `app/services/queue.py` | Redis singleton, RQ queue, SETNX dedup locks. | — |
| `app/services/repo_manager.py` | Shallow clone + workspace cleanup. | — |
| `app/services/secrets_redactor.py` | Pre-LLM secret-pattern redaction. | — |
| `app/workers/review_worker.py` | RQ job pipeline orchestrator (`run_review_job`). | registered to RQ worker |

## 2. Root Entry Point

| Module | Responsibility | Entry point |
| --- | --- | --- |
| `worker.py` | RQ worker process bootstrap (logging + `Worker(default queue)`). | `python worker.py` (Docker worker target; CI `from worker import app`) |

## 3. Scripts (`scripts/`)

| Module | Responsibility | Entry point |
| --- | --- | --- |
| `scripts/git-safe-commit.sh` | Developer commit helper (not wired into Makefile/CI — flagged). | `bash scripts/git-safe-commit.sh` |
| `scripts/test_llm_gateway.py` | Manual LLM connectivity/provider sanity test. | `python scripts/test_llm_gateway.py` |

## 4. Tests

**51 tests, all passing** (`pytest tests/`). `pyproject.toml` declares
`testpaths = ["tests"]`; CI runs `python -m pytest tests/` (the `|| echo "No
tests found"` fallback is vestigial — the suite exists and passes). Coverage:

| File | Tests | Covers |
| --- | --- | --- |
| `tests/test_config.py` | 4 | env-backed settings / config |
| `tests/test_diff_extractor.py` | 19 | git diff parsing, noise filtering, size caps |
| `tests/test_main.py` | 12 | `/health`, webhook signature verification, dedup |
| `tests/test_queue.py` | 5 | Redis queue + SETNX dedup lock behavior |
| `tests/test_secrets_redactor.py` | 11 | pre-LLM secret-pattern redaction |

Still no direct coverage of the LLM agent path (requires mocked provider
calls); see `docs/project/RiskRegister.md` / follow-up backlog.

## 5. Infrastructure

| File | Responsibility |
| --- | --- |
| `Dockerfile` | Multi-stage: base → deps → api / worker / dev targets. |
| `docker-compose.yml` | Base stack: redis + api + worker on `aegisai-net`. |
| `docker-compose.dev.yml` | Dev overrides (reload, bind mounts, host Redis port). |
| `docker-compose.prod.yml` | Prod hardening (restart policies, memory limits, secrets). |
| `Makefile` | Convenience targets (`up`, `test`, `lint`, `build`, `health`, ...). |
| `.github/workflows/ci.yml` | flake8 → py_compile → import check → pytest → Bandit → lychee → Docker build + Trivy. |
| `.env.example` | Environment template (`app/config.py` reads `.env`). |

## 6. Documentation (`docs/`)

Root suite: `architecture.md`, `folder_structure.md`, `module_dependency.md`,
`startup_flow.md`, `package_overview.md`. Migration records: `migration/`
(`migration_summary.md` ← v5.0, `old_tree_to_new_tree.md`, `file_move_ledger.md`).
Categorized docs: `design/`, `product/`, `project/`, `reference/`, `technical/`.

## 7. Test Coverage

51 automated tests, all passing (verified 2026-08-15). CI runs
lint/syntax/import/pytest/security/build gates on every push.
