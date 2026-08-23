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

<p align="center">
  <strong>AI-powered code review agent that catches vulnerabilities in pull requests before they reach production.</strong>
  <br />
  Uses Claude/GPT to analyze diffs, detect security issues, and post actionable findings directly on your PRs.
</p>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [📋 Environment Variables](#-environment-variables)
- [🏗️ Architecture](#️-architecture)
- [🔍 What It Detects](#-what-it-detects)
- [📁 Project Structure](#-project-structure)
- [🛠️ Available Commands](#️-available-commands)
- [🧪 Testing](#-testing)
- [🔧 LLM Gateway](#-llm-gateway)
- [🐳 Docker Deployment](#-docker-deployment)
- [🛡️ Security Features](#️-security-features)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🙏 Acknowledgements](#-acknowledgements)
- [📬 Support](#-support)

---

## 📸 Screenshots

> _To add screenshots: run the app, capture your screen, save images to `docs/assets/`, and reference them below._
>
> **Suggested screenshots:**
> - PR review arriving with inline security comments (GIF)
> - Dashboard showing recent reviews and findings
> - Docker compose startup logs

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Powered Analysis** | Uses Claude or GPT-4o to detect 12+ vulnerability categories |
| 🔒 **Security-First** | Catches SQL injection, XSS, hardcoded secrets, command injection, and more |
| 📝 **Inline Comments** | Posts findings directly on the relevant lines in your PR |
| ⚡ **Real-Time** | Reviews complete within 30-60 seconds of PR creation |
| 🛡️ **Hallucination Guard** | Verifies every finding actually references real code |
| 🔄 **Deduplication** | Prevents duplicate reviews on the same PR |
| 🔐 **Secret Redaction** | Detects and redacts secrets before LLM processing |
| 🐳 **Docker Ready** | Multi-stage builds for API, Worker, and Development |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis
- Docker & Docker Compose (recommended)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/themanoj-025/AegisAI.git
cd AegisAI

# Configure environment
cp .env.example .env
# Edit .env with your GitHub App credentials and LLM API key

# Start the full stack
docker compose up -d

# View logs
docker compose logs -f
```

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start Redis
docker run -d -p 6379:6379 redis

# Start FastAPI server (Terminal 1)
uvicorn app.main:app --reload

# Start RQ worker (Terminal 2)
python worker.py
```

---

## 📋 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_APP_ID` | GitHub App identifier | — | ✅ |
| `GITHUB_PRIVATE_KEY_PATH` | Path to PEM private key | `./github-app-private-key.pem` | ✅ |
| `GITHUB_WEBHOOK_SECRET` | HMAC-SHA256 secret | — | ✅ |
| `LLM_PROVIDER` | AI provider (`anthropic` or `openai`) | `anthropic` | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — | If using Claude |
| `OPENAI_API_KEY` | OpenAI API key | — | If using GPT |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` | — |

---

## 🏗️ Architecture

```




┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Platform                             │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐    │
│  │   PR     │───▶│   Webhook    │───▶│   GitHub API           │    │
│  │  Event   │    │   (POST)     │    │   (Reviews + Comments) │    │
│  └──────────┘    └──────┬───────┘    └───────────▲────────────┘    │
└─────────────────────────┼─────────────────────────┼─────────────────┘
                          │                         │
                          ▼                         │
┌─────────────────────────────────────────────────────────────────────┐
│                      AegisAI System                                 │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Webhook Receiver                                    │   │
│  │  • Validates HMAC-SHA256 signature                           │   │
│  │  • Filters pull_request events                               │   │
│  │  • Deduplicates via Redis locks                              │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Redis Queue + Deduplication                                 │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  RQ Worker Pipeline                                          │   │
│  │  1. Get GitHub installation token                            │   │
│  │  2. Clone PR repo (shallow, depth=50)                        │   │
│  │  3. Extract git diff between base and head                   │   │
│  │  4. Filter noise files (lockfiles, vendor, minified)         │   │
│  │  5. Redact secrets from diff                                 │   │
│  │  6. Send to LLM security agent                               │   │
│  │  7. Parse JSON response with hallucination guard             │   │
│  │  8. Post review to GitHub                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  LLM Gateway (Claude / GPT-4o)                               │   │
│  │  • Swappable providers                                       │   │
│  │  • 3 retries with exponential backoff                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 What It Detects

AegisAI scans for 12+ vulnerability categories:

| Category | Examples |
|----------|----------|
| 🔴 **Critical** | SQL injection, Command injection, Hardcoded secrets |
| 🟠 **High** | XSS, SSRF, Insecure deserialization, Path traversal |
| 🟡 **Medium** | Broken auth, IDOR, Unsafe eval/exec |
| 🟢 **Low** | Insecure crypto, Missing validation |

---

## 📁 Project Structure

```
AegisAI/
├── app/
│   ├── main.py              # FastAPI webhook receiver
│   ├── config.py            # Pydantic settings
│   ├── agents/
│   │   └── security_agent.py # LLM security analysis
│   ├── services/
│   │   ├── diff_extractor.py  # Git diff parsing
│   │   ├── github_auth.py     # GitHub App JWT auth
│   │   ├── github_reviewer.py # Posts reviews to PRs
│   │   ├── llm_gateway.py     # LLM provider abstraction
│   │   ├── queue.py           # Redis queue + locks
│   │   ├── repo_manager.py    # Repo cloning & cleanup
│   │   └── secrets_redactor.py # Pre-LLM secret detection
│   └── workers/
│       └── review_worker.py   # RQ job orchestrator
├── scripts/
│   └── test_llm_gateway.py   # Manual LLM test
├── docker-compose.yml        # Service orchestration
├── Dockerfile                # Multi-stage builds
├── Makefile                  # Convenience commands
└── worker.py                 # RQ worker entry point
```

---

## 🛠️ Available Commands

| Command | Description |
|---------|-------------|
| `make up` | Start full dev stack |
| `make down` | Stop all services |
| `make logs` | Tail logs from all services |
| `make build` | Build Docker images |
| `make test` | Run pytest in container |
| `make lint` | Run flake8 linting |
| `make health` | Check API health endpoint |
| `make clean` | Stop + remove volumes |
| `make reset` | Full rebuild from scratch |

---

## 🧪 Testing

### Manual Test Checklist

1. **Test PR with vulnerabilities:**
   ```bash
   # Create a PR with SQL injection
   echo 'query = f"SELECT * FROM users WHERE id={user_id}"' > test.py
   git add test.py && git commit -m "test: vulnerable code"
   git push origin HEAD:refs/heads/test-pr
   ```

2. **Verify review appears:**
   - Wait 30-60 seconds
   - Check the PR for AegisAI review comments

3. **Test clean PR:**
   - Open a PR with no security issues
   - Verify "no issues found" summary

4. **Verify cleanup:**
   - Check `workspace/` directory is empty after job

### Automated Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 🔧 LLM Gateway

AegisAI supports multiple LLM providers:

### Anthropic Claude (Default)

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### OpenAI GPT

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Test LLM Connectivity

```bash
python scripts/test_llm_gateway.py
```

---

## 🐳 Docker Deployment

### Development

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Production

```bash
# Ensure secrets are in place
mkdir -p secrets
cp /path/to/github-app-private-key.pem secrets/

# Start production stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Available Targets

| Target | Image | Description |
|--------|-------|-------------|
| `api` | FastAPI server | Webhook receiver |
| `worker` | RQ worker | Background processor |
| `dev` | Development | Hot reload + tools |

---

## 🛡️ Security Features

- **HMAC-SHA256 Verification:** All webhooks are cryptographically verified
- **Secret Redaction:** 4 pattern types detected before LLM processing
- **Hallucination Guard:** Verifies findings reference actual code
- **Security Headers:** CSP, X-Frame-Options, X-Content-Type-Options
- **Timing-Safe Comparison:** Prevents timing attacks on signature verification

---

## 🗺️ Roadmap

- [x] Core webhook receiver
- [x] LLM security agent
- [x] GitHub review posting
- [x] Docker deployment
- [x] CI/CD pipeline
- [ ] PostgreSQL storage for audit trail
- [ ] Web dashboard for review history
- [ ] Custom security rules engine
- [ ] Slack/Teams notifications
- [ ] Multi-language support

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- [Anthropic](https://www.anthropic.com/) - Claude API
- [OpenAI](https://openai.com/) - GPT API
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [RQ](https://python-rq.org/) - Job queue
- [Redis](https://redis.io/) - Data store

---

## 📬 Support

- 🐛 [Report Bug](https://github.com/themanoj-025/AegisAI/issues)
- 💡 [Request Feature](https://github.com/themanoj-025/AegisAI/issues)
- 📧 [Email](mailto:your-email@example.com)

---

## 📬 Support

- 🐛 [Report Bug](https://github.com/themanoj-025/AegisAI/issues)
- 💡 [Request Feature](https://github.com/themanoj-025/AegisAI/issues)
- 📧 [Email](mailto:your-email@example.com)


<p align="center">
  Made with ❤️ by <a href="https://github.com/themanoj-025">themanoj-025</a>
</p>

<p align="center">
  If you find this project useful, please give it a ⭐ star!
</p>
---

## ⭐ Star History

[![Last Commit](https://img.shields.io/github/last-commit/themanoj-025/AegisAI?style=flat-square)](https://github.com/themanoj-025/AegisAI)
[![Contributors](https://img.shields.io/github/contributors/themanoj-025/AegisAI?style=flat-square)](https://github.com/themanoj-025/AegisAI/graphs/contributors)

[![Star History Chart](https://api.star-history.com/svg?repos=themanoj-025/AegisAI&type=Date)](https://star-history.com/#AegisAI&Date)
