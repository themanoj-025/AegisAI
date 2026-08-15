# SecurityAndCompliance — AegisAI: Threat Model & Security

| Field | Value |
| --- | --- |
| Version | v0.1 |
| Last Updated | 2026-08-06 |
| Owner | Security Engineer |
| Status | In Review |

---

## 1. Threat Model (STRIDE)

| Threat | Surface | Impact | Mitigation |
| --- | --- | --- | --- |
| Spoofing | Webhook forgery | Fake reviews | HMAC-SHA256 constant-time verify |
| Tampering | Diff payload | LLM sees altered code | GitHub API re-fetch at head_sha |
| Repudiation | Reviews posted | No audit | Job logs with timestamps |
| Info disclosure | Secrets → LLM provider | Credential leak | Mandatory redaction stage + tests |
| DoS | Webhook flood | Queue exhaustion | Rate limit + queue depth alerts |
| Elevation | Malicious repo scripts | RCE on worker | Clone untrusted repos in sandboxed dir; never execute |

## 2. Auth / Authorization Model

- GitHub webhook HMAC is the only inbound auth in v1.
- GitHub App token used for API calls (least privilege: metadata read, PR read/write).
- No user accounts in v1.

## 3. Data Classification

| Data | Class | Handling |
| --- | --- | --- |
| Repo code | Confidential (customer) | Redacted before LLM; deleted after job |
| Secrets found in code | Critical | Never transmitted; reported in-review with masked value |
| Job metadata | Internal | Logged with redaction |

## 4. Encryption Standards

- In transit: TLS 1.2+ everywhere (GitHub API, LLM API).
- At rest: none stored beyond job metadata in v1; if persisted, encrypt `finding.message` at rest (AES-256-GCM).
- Keys: env vars; rotate via deployment.

## 5. Compliance Checklist

- [ ] No secrets in git history (gitleaks in CI)
- [ ] No raw diffs logged pre-redaction
- [ ] LLM provider contract reviewed for data residency
- [ ] GDPR: no PII collected in v1 (repo data is customer-controlled)

## 6. Incident Response Plan (outline)

1. Detect: alert on review failure rate spike.
2. Triage: determine scope (single repo vs worker-wide).
3. Contain: disable webhook processing (flag).
4. Remediate: fix root cause, re-run reviews.
5. Recover: re-enable with canary.
6. Postmortem: blameless writeup in repo.

## 7. Related Documents

| Document | Relationship |
| --- | --- |
| [TechSpec.md](TechSpec.md) | Security NFRs |
| [Rules.md](../project/Rules.md) | Security baseline rules |
| [API.md](API.md) | HMAC contract |
| [Schema.md](Schema.md) | Sensitive data map |
| [PRD.md](../product/PRD.md) | Security goals |
| [AppFlow.md](../design/AppFlow.md) | Flow stages |
| [Design.md](../design/Design.md) | Output format |
| [ImplementationPlan.md](../project/ImplementationPlan.md) | Security tasks |
| [Tracker.md](../project/Tracker.md) | Status |
| [Testing.md](Testing.md) | Security tests |
| [Deployment.md](Deployment.md) | Secret management |
| [Glossary.md](../reference/Glossary.md) | Vocabulary |
| [RiskRegister.md](../project/RiskRegister.md) | Risks |
