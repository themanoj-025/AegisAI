# Design — AegisAI: Design System & UX Principles

| Field | Value |
| --- | --- |
| Version | v0.1 |
| Last Updated | 2026-08-06 |
| Owner | Design Lead |
| Status | In Review |

---

## 1. Design Principles

1. **Clarity over cleverness** — Review comments must state the issue and the fix plainly. Do: "Potential SQL injection: use parameterized queries." Don't: "This looks sus."
2. **Context first** — Every comment references file, line, and surrounding code.
3. **Severity honesty** — Never over- or under-state severity; `blocking` / `warning` / `nit`.
4. **Minimal noise** — Clean PRs get a one-line summary, not spam.
5. **Actionable output** — Each finding includes a suggested remediation.

## 2. Brand & Visual Identity

- Voice: precise, professional, security-first; no emojis in comments.
- Imagery: none (text-only output in v1).

## 3. Color System

N/A — no app UI in v1. Color tokens reserved for future operator dashboard:

| Token | Hex | Usage | Contrast (AA) |
| --- | --- | --- | --- |
| severity-blocking | `#B91C1C` | Blocking findings | 7:1 on white |
| severity-warning | `#B45309` | Warning findings | 5.4:1 |
| severity-nit | `#1D4ED8` | Nits | 6.3:1 |
| success | `#15803D` | "No issues" | 5.2:1 |

## 4. Typography Scale

| Token | Font | Size | Weight | Line-height | Usage |
| --- | --- | --- | --- | --- | --- |
| comment-body | system sans | 14px | 400 | 1.5 | Comment text |
| code-snippet | mono | 13px | 400 | 1.4 | Code blocks in comments |
| severity-label | system sans | 12px | 700 | 1.4 | Severity badges |

## 5. Spacing & Grid System

N/A — no pixel UI in v1. Comment text uses GitHub's native rendering.

## 6. Component Library

**Review Comment anatomy** (ASCII):

```
┌───────────────────────────────────────┐
│ [severity] [category]  — file:line    │
│ What: <one-line description>          │
│ Why: <security rationale>             │
│ Fix: <suggested remediation>          │
└───────────────────────────────────────┘
```

States: only "posted" and "failed-to-post" (logged).

## 7. Iconography & Imagery

None in v1 — text-only output.

## 8. Accessibility Standards

- Comments render in native GitHub UI (inherits GitHub's accessibility).
- ASCII-only comment format (no colored text reliance) so severity is never conveyed by color alone.

## 9. Responsive Behavior

N/A — GitHub UI renders comments on all breakpoints natively.

## 10. Motion & Micro-interactions

None in v1.

## 11. Dark Mode / Theming

N/A — inherits GitHub themes.

## 12. Related Documents

| Document | Relationship |
| --- | --- |
| [AppFlow.md](AppFlow.md) | Surfaces that consume these components (SCR-001/002) |
| [PRD.md](../product/PRD.md) | UX requirements |
| [TechSpec.md](../technical/TechSpec.md) | Output pipeline |
| [Schema.md](../technical/Schema.md) | Finding record fields |
| [ImplementationPlan.md](../project/ImplementationPlan.md) | Design tasks |
| [Tracker.md](../project/Tracker.md) | Status |
| [Rules.md](../project/Rules.md) | Standards |
| [API.md](../technical/API.md) | Output contract |
| [SecurityAndCompliance.md](../technical/SecurityAndCompliance.md) | Redaction of secrets in output |
| [Testing.md](../technical/Testing.md) | Comment format tests |
| [Deployment.md](../technical/Deployment.md) | Environments |
| [Glossary.md](../reference/Glossary.md) | Vocabulary |
| [RiskRegister.md](../project/RiskRegister.md) | Risks |
