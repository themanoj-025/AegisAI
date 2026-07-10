# AegisAI — AI-Powered Code Review

Automated security-focused code review for GitHub pull requests.

## Architecture (Phase 1)

```
GitHub Webhook → FastAPI Receiver → Redis Queue → RQ Worker → Clone Repo
    → Diff Extraction → Secrets Redaction → LLM Security Agent → Post Review
```

## Local Development

### Prerequisites

- Python 3.10+
- Redis (for the job queue)

### Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and fill in your values
cp .env.example .env
```

### Running (three processes needed)

**1. Redis** (using Docker for quick local setup):
```bash
docker run -d -p 6379:6379 redis
```

**2. FastAPI server**:
```bash
uvicorn app.main:app --reload
```

**3. RQ Worker** (run this in a separate terminal):
```bash
python worker.py
```

### Testing the Webhook Locally

GitHub cannot reach `localhost` directly. You'll need a webhook forwarding service:

- **ngrok**: `ngrok http 8000` — gives you a public URL like `https://abc123.ngrok.io`
- **smee.io**: `npx smee --url https://smee.io/your-channel --port 8000`

Set your GitHub App's webhook URL to the forwarding URL.

### Full Manual Test Checklist

1. Open a PR with vulnerable code (e.g., SQL injection via f-string)
2. Within ~30-60 seconds, confirm a GitHub PR review appears from your App
3. Open a clean PR and confirm "no issues found" summary
4. Verify workspace folder is cleaned up after job completion

---

## 📖 Documentation

For comprehensive codebase intelligence and architecture documentation, see the [`docs/`](docs/) folder:

| File | Description |
|------|-------------|
| [`memory.md`](memory.md) | Complete project brain — purpose, tech stack, features, data flow |
| [`docs/architecture.md`](docs/architecture.md) | System architecture diagram + layered breakdown |
| [`docs/routes.md`](docs/routes.md) | Full route table |
| [`docs/api-map.md`](docs/api-map.md) | Complete API inventory with endpoints, inputs, outputs |
| [`docs/database-map.md`](docs/database-map.md) | Database schema, entities, fields, relationships |
| [`docs/dependency-graph.md`](docs/dependency-graph.md) | Module dependency map + critical files |
