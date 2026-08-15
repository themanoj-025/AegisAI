# AegisAI — Documentation Index

Single home for all AegisAI documentation. AegisAI is an AI-powered security
code-review GitHub App: it verifies webhook signatures, deduplicates via Redis,
and runs a background review pipeline (diff extraction → secret redaction →
LLM security review → hallucination-guarded findings → PR review).

**Start here:** [architecture.md](architecture.md) (system map) →
[folder_structure.md](folder_structure.md) (repo tree) →
[technical/TechSpec.md](technical/TechSpec.md) (build details).

## Structure

```
docs/
├── README.md                      ← this index
├── architecture.md                canonical architecture reference
├── folder_structure.md            repository + docs tree
├── module_dependency.md           dependency graph (acyclic)
├── package_overview.md            module inventory
├── startup_flow.md                boot + webhook→review flow
├── design/
│   ├── AppFlow.md                 app screens / states / flows
│   └── Design.md                  design decisions
├── product/
│   └── PRD.md                     product requirements
├── project/
│   ├── analysis_report.md         repo inventory & classification (2026-08-10)
│   ├── ImplementationPlan.md      implementation plan
│   ├── RiskRegister.md            risks & mitigations
│   ├── Rules.md                   engineering rules
│   └── Tracker.md                 status tracker
├── reference/
│   └── Glossary.md                terminology
├── technical/
│   ├── API.md                     endpoint reference
│   ├── Deployment.md              deployment guide
│   ├── Schema.md                  data model
│   ├── SecurityAndCompliance.md   security baseline
│   ├── TechSpec.md                technical spec
│   └── Testing.md                 test strategy
├── migration/
│   ├── migration_summary.md       v5.0 modernization record
│   ├── old_tree_to_new_tree.md    restructure before/after
│   └── file_move_ledger.md        file-move ledger
└── audit/
    ├── cleanup-audit-2026-08-13.md  previous cleanup audit
    └── cleanup-audit-2026-08-15.md  docs de-LLM-ification audit
```

## Guidance

| You want... | Read |
|---|---|
| How the system works end-to-end | [architecture.md](architecture.md) |
| Where everything lives | [folder_structure.md](folder_structure.md) |
| Module-by-module inventory | [package_overview.md](package_overview.md) |
| How the app boots / reviews a PR | [startup_flow.md](startup_flow.md) |
| API surface | [technical/API.md](technical/API.md) |
| Data model | [technical/Schema.md](technical/Schema.md) |
| Deployment / Docker / CI | [technical/Deployment.md](technical/Deployment.md) |
| Security posture | [technical/SecurityAndCompliance.md](technical/SecurityAndCompliance.md) |
| What's shipped / next | [project/Tracker.md](project/Tracker.md) |
| Risks & follow-ups | [project/RiskRegister.md](project/RiskRegister.md) |
