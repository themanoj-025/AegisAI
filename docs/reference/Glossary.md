# Glossary — AegisAI: Shared Vocabulary

| Field | Value |
| --- | --- |
| Version | v0.1 |
| Last Updated | 2026-08-06 |
| Owner | Tech Writer |
| Status | In Review |

---

| Term | Definition |
| --- | --- |
| Webhook | GitHub event delivery to our `/webhook` endpoint |
| Diff | Set of line changes in a PR |
| Redaction | Masking secrets before LLM context |
| RQ | Redis Queue — job queue library |
| Worker | Process consuming jobs and running the pipeline |
| head_sha | PR branch's latest commit SHA |
| Idempotency | Guaranteeing no duplicate review for same head_sha |
| Severity | blocking / warning / nit classification |
| Finding | One detected security issue |
| Clean PR | PR with no detected issues |
| ngrok/smee | Local tunnel tools for receiving GitHub webhooks |
| LLM security agent | The LLM prompt+call that performs analysis |

## Related Documents

| Document | Relationship |
| --- | --- |
| [PRD.md](../product/PRD.md) | Terms used there |
| [TechSpec.md](../technical/TechSpec.md) | Terms used there |
| [AppFlow.md](../design/AppFlow.md) | Terms used there |
| [Design.md](../design/Design.md) | Terms used there |
| [Schema.md](../technical/Schema.md) | Terms used there |
| [ImplementationPlan.md](../project/ImplementationPlan.md) | Terms used there |
| [Tracker.md](../project/Tracker.md) | Terms used there |
| [Rules.md](../project/Rules.md) | Terms used there |
| [API.md](../technical/API.md) | Terms used there |
| [SecurityAndCompliance.md](../technical/SecurityAndCompliance.md) | Terms used there |
| [Testing.md](../technical/Testing.md) | Terms used there |
| [Deployment.md](../technical/Deployment.md) | Terms used there |
| [RiskRegister.md](../project/RiskRegister.md) | Terms used there |
