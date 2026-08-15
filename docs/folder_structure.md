# Folder Structure — AegisAI

Canonical layout after the v5.0 modernization pass. The structure follows the
target architecture ("adapt, don't force-fit"): a small layered `app/`
package, two root entry points, Docker tooling, and a docs suite.

## 1. Current tree (canonical)

```
AegisAI/
├── app/                         # Core package
│   ├── __init__.py
│   ├── main.py                  # FastAPI webhook receiver (entry point)
│   ├── config.py                # pydantic-settings (env-backed)
│   ├── agents/
│   │   └── security_agent.py    # LLM security review + hallucination guard
│   ├── services/
│   │   ├── diff_extractor.py    # git diff parsing / noise filtering
│   │   ├── github_auth.py       # App JWT → installation tokens
│   │   ├── github_reviewer.py   # PR review posting (inline + summary)
│   │   ├── llm_gateway.py       # Anthropic/OpenAI provider abstraction
│   │   ├── queue.py             # Redis singleton, RQ queue, dedup locks
│   │   ├── repo_manager.py      # shallow clone + workspace cleanup
│   │   └── secrets_redactor.py  # pre-LLM secret redaction
│   └── workers/
│       └── review_worker.py     # RQ job pipeline orchestrator
├── worker.py                    # ENTRY POINT: RQ worker process
├── scripts/
│   ├── git-safe-commit.sh       # commit helper
│   └── test_llm_gateway.py      # manual LLM connectivity test
├── docs/                        # documentation suite (see §2)
├── .github/workflows/ci.yml     # lint → test → bandit → lychee → docker+trivy
├── Dockerfile                   # multi-stage (base/deps/api/worker/dev)
├── docker-compose.yml           # base stack (redis + api + worker)
├── docker-compose.dev.yml       # dev overrides (reload, bind mounts)
├── docker-compose.prod.yml      # prod hardening (limits, secrets)
├── Makefile                     # compose convenience targets
├── pyproject.toml               # black / isort / pytest config
├── requirements.txt             # pip dependencies
├── README.md  PROJECT_OVERVIEW.md  PROJECT_ANALYSIS.md  AGENTS.md
└── .gitignore  .dockerignore  .vscode/
```

## 2. Docs tree

```
docs/
├── architecture.md              # canonical architecture reference
├── folder_structure.md          # this file
├── module_dependency.md         # ← v6 restructure: dependency graph
├── startup_flow.md              # ← v6 restructure: boot flows
├── package_overview.md          # ← v6 restructure: module inventory
├── migration/
│   ├── migration_summary.md     # ← v5.0 modernization pass report (moved here)
│   ├── old_tree_to_new_tree.md  # ← v6 restructure
│   └── file_move_ledger.md      # ← v6 restructure
├── design/    (AppFlow.md, Design.md)
├── product/   (PRD.md)
├── project/   (ImplementationPlan.md, RiskRegister.md, Rules.md, Tracker.md,
│               analysis_report.md ← this pass)
├── reference/ (Glossary.md)
└── technical/ (API.md, Deployment.md, Schema.md, SecurityAndCompliance.md,
                TechSpec.md, Testing.md)
```

## 3. Change log (this pass)

| Old path | New path | Reason | Mechanism |
|---|---|---|---|
| `AGENTS_FIX.md` | *removed* | Leftover AI-prompt scaffolding (v7.0 fix prompt, duplicated in 16 sibling repos); not referenced by code, CI, or Docker | `git rm` (recoverable from history) |
| — | `docs/project/analysis_report.md` | Required Phase 1–2 inventory artifact | added |
| — | `docs/architecture.md` | Required Phase 9 artifact | added |
| — | `docs/folder_structure.md` | Required Phase 9 artifact | added |
| — | `docs/migration_summary.md` | Required Phase 9 artifact | added |
| `docs/migration_summary.md` | `docs/migration/migration_summary.md` | v6 restructure: consolidate migration records under `docs/migration/` | `git mv` |
| — | `docs/module_dependency.md` | v6 restructure: Phase 6 deliverable | added |
| — | `docs/startup_flow.md` | v6 restructure: Phase 6 deliverable | added |
| — | `docs/package_overview.md` | v6 restructure: Phase 6 deliverable | added |
| — | `docs/migration/old_tree_to_new_tree.md` | v6 restructure: Phase 6 deliverable | added |
| — | `docs/migration/file_move_ledger.md` | v6 restructure: Phase 6 deliverable | added |

Reference updates: `.dockerignore` (dropped the now-stale `AGENTS_FIX.md`
exclusion), `PROJECT_OVERVIEW.md` (dropped `AGENTS_FIX.md` from the tree and
file breakdown).

## 4. Root allowlist compliance

| Root entry | Status |
|---|---|
| `worker.py`, `app/main.py` | ✔ entry points |
| `Dockerfile`, `docker-compose*.yml` | ✔ container tooling |
| `Makefile`, `pyproject.toml`, `requirements.txt` | ✔ standard metadata |
| `README.md`, `PROJECT_OVERVIEW.md`, `PROJECT_ANALYSIS.md`, `AGENTS.md` | ✔ metadata / docs |
| `app/`, `docs/`, `scripts/`, `.github/`, `.vscode/` | ✔ top-level folders |
| `.gitignore`, `.dockerignore` | ✔ VCS / build metadata |

Result: **no stray files remain at root** (pre-existing `AGENTS_FIX.md`
scaffolding removed; `PROJECT_ANALYSIS.md` retained as the short-form audit,
superseded in depth by `docs/project/analysis_report.md`).

## 5. Why not more restructuring?

The app is already a minimal, clean, acyclic layered package; the target
architecture's `domain/services/repositories` subpackages would be an
over-fit for ~10 modules. Per the prompt's own rule — "don't over-engineer,
adapt to the actual stack" — no further moves were made. The single
structural defect found (a root-level prompt scaffold, `AGENTS_FIX.md`) was
removed rather than relocated.
