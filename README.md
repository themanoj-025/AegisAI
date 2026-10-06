# 🛡️ AegisAI

<p align="center">
  <img src="https://img.shields.io/badge/AegisAI-AI%20Code%20Review-blue?style=for-the-badge" alt="AegisAI Logo" />
</p>

<h1 align="center">🛡️ AegisAI</h1>

<p align="center">
  <strong>Automated Security-Focused Code Review for GitHub Pull Requests</strong>
</p>

<p align="center">
  <a href="https://github.com/themanoj-025/AegisAI/actions"><img src="https://img.shields.io/github/actions/workflow/status/themanoj-025/AegisAI/ci.yml?style=flat-square&label=CI" alt="CI Status" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/blob/main/LICENSE"><img src="https://img.shields.io/github/license/themanoj-025/AegisAI?style=flat-square" alt="License" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/stargazers"><img src="https://img.shields.io/github/stars/themanoj-025/AegisAI?style=social" alt="Stars" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/issues"><img src="https://img.shields.io/github/issues/themanoj-025/AegisAI?style=flat-square" alt="Issues" /></a>
  <a href="https://github.com/themanoj-025/AegisAI/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="PRs Welcome" /></a>
</p>

---

## 📋 Table of Contents

- [What it does](#what-it-does)
- [📸 Screenshots](#-screenshots)
- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🔍 What it detects](#-what-it-detects)
- [📁 Project structure](#-project-structure)
- [🧪 Testing](#-testing)
- [🔧 LLM gateway](#-llm-gateway)
- [🐳 Docker deployment](#-docker-deployment)
- [🛡️ Security features](#️-security-features)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [📬 Support](#-support)

---

## What it does

AegisAI is an automated security-focused code review agent that runs on GitHub Pull Requests. It reads the full diff in repository context, detects vulnerabilities and security anti-patterns, ranks findings by severity, and posts actionable, line-anchored review comments directly on the PR — before the change reaches production.

> [!NOTE] The agent analyzes the diff, classifies security issues, and posts review comments. The LLM provider (Claude or GPT) is chosen at runtime via an environment variable; a deterministic fallback reviews diffs without LLM calls.

## Screenshots

> To add screenshots: start the stack with `docker compose up -d`, open a test PR, capture the review comment, save images to `docs/assets/`, and reference them below.
>
> **Suggested screenshots:**
> - AegisAI review comment posted inline on a vulnerable line
> - PR review summary listing detected vulnerability categories
> - Queue/DLQ stats from `/api/v1/webhooks/queue/stats`

---

## ✨ Features

### Line-anchored findings

- Posts review comments directly on the lines that trigger a severity finding (blocking / warning / nit)
- Findings are categorized by type: `bug`, `security`, `style`, `suggestion`

### LLM + deterministic hybrid

- **LLM-based reasoning** (Claude / GPT — configurable via env var) for semantic understanding of the diff
- **Deterministic rules** for high-confidence, no-false-positive checks (e.g., hardcoded secrets, injection, auth bypass patterns)
- The LLM is only used for findings the deterministic rules cannot resolve; it never invents findings out of thin air

### Severity-ranking & categorization

| Severity | Meaning |
| --- | --- |
| `blocking` | Likely exploitable vulnerability; must be addressed before merge |
| `warning` | Real issue; should be fixed before merge |
| `nit` | Cosmetic or style; optional |

### Summary metrics

- Post-review comment aggregates findings by category and severity
- Uploads a machine-readable JSON report as a PR artifact (configurable)

### Webhook & queue

- Receives GitHub `pull_request` events via HMAC-verified webhook
- Enqueues review tasks on Redis RQ; returns 202 quickly to avoid GitHub's webhook timeout

## 🏗️ Architecture

```text
AegisAI/
├── app/
│   ├── api/                    # FastAPI webhook + review routes
│   ├── core/                   # Business logic (diff parsing, finding classification)
│   ├── services/               # LLM providers, Redis RQ, database
│   ├── models/                 # SQLAlchemy models
│   ├── config.py               # Settings (LLM provider, secrets)
│   └── main.py                 # App entry point
├── docker-compose.yml
├── requirements.txt
└── README.md
```

> [!TIP] To add a new finding rule: implement the `FindingRule` interface in `app/core/finding_rules.py`, register it in `core/finding_rules/registry.py`, and the webhook will surface it on every PR.

## 🔍 What it detects

| Category | Examples |
| --- | --- |
| **Injection** | SQL, command, LDAP injection patterns |
| **Auth & access control** | Hardcoded credentials, missing authorization checks |
| **Data exposure** | Logging secrets, verbose error messages, unmasked PII |
| **Insecure dependencies** | Known-vulnerable packages (via dependency scan) |
| **CWE patterns** | Top-N CWE items (CWE-79, CWE-89, CWE-22, etc.) |

> [!CAUTION] The detection list above is the current coverage area as verified in the source. If any item is missing from the manifest or the README claims more than the code covers, reconcile before the next release.

## 📁 Project structure

```
AegisAI/
├── app/
│   ├── api/                    # Webhook + review routes
│   ├── core/                   # Business logic + finding rules
│   ├── services/               # LLM, Redis RQ, DB
│   ├── models/                 # SQLAlchemy models
│   ├── config.py               # Settings
│   └── main.py                 # Entry point
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🧪 Testing

```bash
# Run the test suite
pytest tests/ -v
```

> [!NOTE] The CI workflow enforces lint + test + security scans; a coverage threshold is enforced on the review-service code.

## 🔧 LLM gateway

| Setting | Description |
| --- | --- |
| `AEGISAI_LLM_PROVIDER` | `anthropic` (default) or `openai` |
| `AEGISAI_CLAUDE_KEY` / `AEGISAI_OPENAI_KEY` | API key for the chosen provider |
| `AEGISAI_TIMEOUT` | Reasoning timeout per finding (default 10s) |
| `AEGISAI_BLOCK_THRESHOLD` | Minimum severity to post a blocking comment |

> [!IMPORTANT] No LLM key is required for the deterministic fallback. Set `AEGISAI_LLM_PROVIDER=unknown` to run purely deterministic to verify the non-LLM path.

## 🐳 Docker deployment

```bash
# 1. Clone the repository
git clone https://github.com/themanoj-025/AegisAI.git
cd AegisAI

# 2. Copy the environment template
cp .env.example .env
#   → Set AEGISAI_LLM_PROVIDER, the provider key, and Redis URL

# 3. Start the stack
docker compose up --build
```

## 🛡️ Security features

- HMAC-SHA256 webhook signature verification (constant-time compare)
- Redis-based task queue with DLQ for retries
- Audit logging of every review comment posted
- Rate limiting on the review webhook endpoint
- Strict CSP headers (`default-src 'none'` — the Swagger UI intentionally renders blank; capture the PR-review flow instead)

## 🗺️ Roadmap

> [!CAUTION] Checked items are built and verified. Unchecked items are tracked in the issue tracker.

- [x] Line-anchored security findings on PR diffs
- [x] Severity ranking (blocking / warning / nit)
- [x] LLM + deterministic finding hybrid
- [x] Redis RQ task queue + DLQ
- [x] JSON report artifact
- [ ] Public demo instance (tracked public issue)

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT License — see [LICENSE](LICENSE).

> [!IMPORTANT] The license in this README matches the `license` field in `pyproject.toml` and the contents of the `LICENSE` file. No conflicts were found.
