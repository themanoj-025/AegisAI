# Old Tree → New Tree — AegisAI

Restructure performed **2026-08-11** (v6, Principal Architect protocol). The repo
already conformed to the target architecture after the v5.0 pass (2026-08-10); this
restructure consolidates migration records and completes the Phase 6 documentation
suite. **Zero code changes, zero import changes, zero entry-point changes.**

## Before (2026-08-10, after v5.0)

```
AegisAI/
├── app/
│   ├── __init__.py · main.py · config.py
│   ├── agents/security_agent.py
│   ├── services/ (7 modules)
│   └── workers/review_worker.py
├── worker.py                        (root entry — unchanged)
├── scripts/{git-safe-commit.sh, test_llm_gateway.py}
├── docs/
│   ├── architecture.md · folder_structure.md · migration_summary.md   ← root of docs/
│   ├── design/ · product/ · project/ · reference/ · technical/
├── .github/workflows/ci.yml
├── Dockerfile · docker-compose*.yml · Makefile
├── pyproject.toml · requirements.txt
├── README.md · PROJECT_OVERVIEW.md · PROJECT_ANALYSIS.md · AGENTS.md
└── .gitignore · .dockerignore · .env.example
```

## After (2026-08-11)

```
AegisAI/
├── app/                            (unchanged)
├── worker.py                       (unchanged — entry-point contract)
├── scripts/                        (unchanged)
├── docs/
│   ├── architecture.md · folder_structure.md          (existing, kept)
│   ├── module_dependency.md                            (NEW)
│   ├── startup_flow.md                                 (NEW)
│   ├── package_overview.md                             (NEW)
│   ├── migration/
│   │   ├── migration_summary.md                        (MOVED from docs/)
│   │   ├── old_tree_to_new_tree.md                     (NEW — this file)
│   │   └── file_move_ledger.md                         (NEW)
│   ├── design/ · product/ · project/ · reference/ · technical/  (unchanged)
├── .github/workflows/ci.yml         (unchanged)
├── Dockerfile · docker-compose*.yml · Makefile         (unchanged)
├── pyproject.toml · requirements.txt                   (unchanged)
├── README.md · PROJECT_OVERVIEW.md · PROJECT_ANALYSIS.md · AGENTS.md (unchanged)
└── .gitignore · .dockerignore · .env.example           (unchanged)
```

## Summary

| Kind | Count |
| --- | --- |
| Files moved (`git mv`) | 1 (`docs/migration_summary.md` → `docs/migration/migration_summary.md`) |
| Docs added | 5 (`module_dependency.md`, `startup_flow.md`, `package_overview.md`, `migration/old_tree_to_new_tree.md`, `migration/file_move_ledger.md`) |
| Docs updated | 1 (`folder_structure.md` — docs tree + change log) |
| Code / imports / entry points / CI / Docker changed | 0 |
| Deleted | 0 |

Rationale for no further moves: the layered `app/` package already matches the
target ("adapt, don't force-fit"); `worker.py`, `scripts/`, and `Dockerfile`
locations are entry-point/infra contracts. Full rationale is documented in
`docs/folder_structure.md` §5 and the v5.0 migration summary.
