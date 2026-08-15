# File Move Ledger — AegisAI

Restructure date: **2026-08-11** (v6) · Method: `git mv` · Branch: `main`
(local commits, no push).

## Moved Files

| # | Old Path | New Path | Category | Reason | Risk | Verified? |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `docs/migration_summary.md` | `docs/migration/migration_summary.md` | Meta → Docs | Consolidate migration records under `docs/migration/` (protocol Phase 6) | Low (0 references; verified by grep) | ✅ |

## Files Added

| Path | Reason |
| --- | --- |
| `docs/module_dependency.md` | Phase 6 deliverable — dependency graph (acyclic, verified from source imports). |
| `docs/startup_flow.md` | Phase 6 deliverable — API/worker boot + webhook→review flow. |
| `docs/package_overview.md` | Phase 6 deliverable — module inventory. |
| `docs/migration/old_tree_to_new_tree.md` | Phase 6 deliverable. |
| `docs/migration/file_move_ledger.md` | Phase 6 deliverable (this file). |

## Files Updated

| Path | Reason |
| --- | --- |
| `docs/folder_structure.md` | Docs-tree section now lists `migration/`; change-log table extended with v6 entries. |

## Files Deliberately NOT Moved (contract analysis)

| Path | Why it stays | Risk if moved |
| --- | --- | --- |
| `worker.py` | Root entry point — CI imports `from worker import app`; Dockerfile `COPY worker.py` + worker CMD; compose dev bind-mounts it | High — 4+ infra touchpoints, zero benefit |
| `app/main.py` | Canonical API entry (`uvicorn app.main:app`) — already in `app/` | — |
| `scripts/` (flat) | 2 developer/ops scripts; `scripts/{admin,backfills,seed}` split would be over-engineering for 2 files | Low |
| `app/` layout | Already conforms to target (layered package); no `db/models/repositories` exist to relocate | — |
| `tests/` (absent) | No test suite exists; CI tolerates absence (`|| echo "No tests found"`); creating an empty dir adds nothing (git doesn't track empty dirs) | — |

## Flagged (needs human review / follow-up backlog)

| Item | Flag |
| --- | --- |
| **Zero automated tests** | Pre-existing; CI's test job collects nothing. Recommended unit suite for `llm_gateway`, `secrets_redactor`, `diff_extractor`, `queue` + `TestClient` health/signature tests (already in v5.0 summary §6). |
| `scripts/git-safe-commit.sh` | Not referenced by Makefile/CI — verify intent before wiring/removing (pre-existing flag). |
| `DATABASE_URL` setting | Reserved for the Postgres audit-trail roadmap, currently unused (pre-existing flag). |
| In-memory installation-token cache | Per-process; fine at single-worker scale; consider shared Redis cache when scaling (pre-existing flag). |

## Deletions

None in this restructure.
