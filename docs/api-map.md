# API Map — AegisAI

## Internal API (FastAPI)
| Method | Endpoint | Input | Output | Purpose |
|--------|----------|-------|--------|---------|
| POST | `/webhook` | GitHub webhook JSON | `{"status": "queued"}` | Receive PR events |
| GET | `/health` | None | `{"status": "ok"}` | Health check |

## External API Integrations
| Service | Purpose | Auth Method |
|---------|---------|-------------|
| **GitHub API** | Post PR reviews, clone repos | GitHub App JWT |
| **Anthropic Claude** | LLM security analysis | API Key |
| **OpenAI GPT-4** | LLM security analysis (alternative) | API Key |

## Internal Queue
| Queue | Technology | Purpose |
|-------|------------|---------|
| Review Job Queue | Redis + RQ | Queue PR review jobs for async processing |
