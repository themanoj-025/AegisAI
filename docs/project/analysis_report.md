# Analysis Report — Repository Inventory & Classification

Date: 2026-08-10 · Scope: entire AegisAI repository · Method: file-by-file
read + import-graph scan + content-hash duplicate scan + reference scan.

This report is the written inventory required by Phase 1–2 of the repository
modernization pass (v5.0). It lists every top-level entry, its purpose, its
classification, and its intra-package dependencies. Nothing here changes
behavior — it is the evidence base for the restructuring documented in
[`docs/migration_summary.md`](../migration/migration_summary.md).

---

## 1. Stack overview

| Dimension | Value |
|---|---|
| Language / runtime | Python ≥ 3.11 (CI: 3.11, image 3.11-slim) |
| Package manager | `requirements.txt` (pip) + `pyproject.toml` (tool config only) |
| Application | FastAPI webhook receiver (`app/main.py`) + RQ background worker (`worker.py`) |
| Task queue | RQ + Redis (`redis:7-alpine`) with SETNX dedup locks |
| LLM layer | Swappable provider gateway — Anthropic Claude (default) / OpenAI GPT-4o |
| Lint / test | flake8 · pytest (configured; **no test files exist yet**) |
| CI | GitHub Actions `ci.yml`: lint → test → security-scan → link-check → docker+Trivy |
| Deploy | Docker multi-stage (api/worker/dev targets) + compose dev/prod overrides |

## 2. Top-level inventory (root)

| Path | Purpose | Classification |
|---|---|---|
| `app/` | Core package — FastAPI app, config, agents, services, workers | Application |
| `worker.py` | RQ worker process entry point (`python worker.py`) | Entry point |
| `app/main.py` | FastAPI app + webhook routes (imported by uvicorn/Docker) | Entry point |
| `app/config.py` | pydantic-settings typed configuration (env-backed) | Configuration |
| `docs/` | Documentation suite (design/product/project/reference/technical) | Docs |
| `scripts/` | `git-safe-commit.sh`, `test_llm_gateway.py` | Infrastructure / Tools |
| `.github/workflows/ci.yml` | CI pipeline (lint, test, bandit, lychee, docker+trivy) | Infrastructure |
| `Dockerfile`, `docker-compose*.yml` | Multi-stage images + dev/prod compose stacks | Infrastructure |
| `Makefile` | Docker-compose convenience targets | Infrastructure |
| `pyproject.toml`, `requirements.txt` | Tool config (black/isort/pytest) + pip deps | Configuration |
| `README.md`, `PROJECT_OVERVIEW.md`, `PROJECT_ANALYSIS.md` | Project metadata / docs | Docs |
| `AGENTS.md` | AI-agent instruction file (project convention) | Docs |
| `AGENTS_FIX.md` | **Leftover AI-prompt scaffolding (v7.0 fix prompt)** — removed this pass | Unclassified → removed |
| `.gitignore`, `.dockerignore`, `.vscode/` | VCS / build / IDE metadata | Configuration |

## 3. App package (domain & application)

| Module | Purpose | Depends on (intra-package) | Classification |
|---|---|---|---|
| `config.py` | Typed settings: GitHub App creds, LLM provider, Redis, workspace | — (leaf) | Configuration |
| `main.py` | FastAPI app: HMAC webhook verification, event filtering, dedup lock, enqueue | `config`, `services.queue`, `workers.review_worker` | API/interface |
| `agents/security_agent.py` | LLM security review: file batching, JSON extraction, hallucination guard | `services.llm_gateway`, `services.secrets_redactor` | Domain / Application |
| `services/diff_extractor.py` | `git diff` parsing into per-file structs; noise filtering + size caps | — (leaf, subprocess) | Data access (external) |
| `services/github_auth.py` | GitHub App JWT generation + installation-token exchange (cached) | `config` | Cross-cutting (auth) |
| `services/github_reviewer.py` | Post findings as PR review: inline comments + summary; 422 fallback | — (leaf, httpx) | API/interface |
| `services/llm_gateway.py` | Provider abstraction (Anthropic/OpenAI) with tenacity retries | `config` | Cross-cutting |
| `services/queue.py` | Redis connection singleton, RQ queue, SETNX dedup locks | `config` | Infrastructure |
| `services/repo_manager.py` | Shallow clone + workspace cleanup | `config` | Data access (external) |
| `services/secrets_redactor.py` | Pre-LLM secret pattern redaction (4 regex families) | — (leaf) | Cross-cutting (security) |
| `workers/review_worker.py` | RQ job orchestrator: token → clone → diff → agent → post → cleanup | all services + agent | Application |

Dependency graph is **acyclic**: `main` / `worker` → `review_worker` → services
+ agent → `config`. Leaf modules: `config`, `diff_extractor`,
`github_reviewer`, `secrets_redactor`.

## 4. Documentation suite

| Path | Purpose |
|---|---|
| `docs/design/` | AppFlow.md, Design.md |
| `docs/product/` | PRD.md |
| `docs/project/` | ImplementationPlan, RiskRegister, Rules, Tracker (+ this report) |
| `docs/reference/` | Glossary.md |
| `docs/technical/` | API, Deployment, Schema, SecurityAndCompliance, TechSpec, Testing |
| `README.md` / `PROJECT_OVERVIEW.md` | Quick start + exhaustive overview (tree, flows, API surface, env vars) |

## 5. Findings summary (evidence for Phase 3)

| Scan | Method | Result |
|---|---|---|
| Duplicate files | SHA-256 content hash over tracked files | **0 duplicate-content groups** |
| Empty files | size == 0 walk | none |
| Unused deps | import scan vs `requirements.txt` | all 11 pinned deps imported; `database_url` setting unused but harmless (reserved, documented) |
| Hardcoded secrets | regex scan | none — env-backed only |
| AI scaffolding | `AGENTS_FIX.md` (identical v7.0 prompt file in 16 sibling repos) | **removed** — not referenced by code/CI/Docker (only `.dockerignore` exclusion + a doc tree line) |
| Stray artifacts | root scan | none tracked; untracked `__pycache__`/caches gitignored |
| Tests | `pytest --collect-only` | **0 tests collected** — no `tests/` directory exists (`testpaths=["tests"]` points at nothing) |

## 6. Needs Human Review

1. **No automated tests** — the CI `test` job installs deps and runs
   `pytest tests/ -v`, which currently collects zero tests. The repo is
   verified only by flake8 + `py_compile` in CI and manual PR checklists.
   Adding a unit suite for `llm_gateway`, `secrets_redactor`, and
   `diff_extractor` (all stdlib/mockable) is the highest-value next step.
2. **`database_url` setting** (`config.py`) is unused — reserved for the
   PostgreSQL audit-trail roadmap; kept deliberately.
3. **In-memory token cache** (`github_auth._token_cache`) is per-process, not
   shared across worker processes — acceptable at single-worker scale.
