# Routes — AegisAI

## API Routes (FastAPI)
| Method | Route | Purpose | Auth Required |
|--------|-------|---------|---------------|
| POST | `/webhook` | Receive GitHub PR webhooks | Yes (webhook secret) |
| GET | `/health` | Health check | No |

## Webhook Events Handled
| GitHub Event | Action | Processing |
|-------------|--------|------------|
| `pull_request` | `opened` | Enqueue review job |
| `pull_request` | `synchronize` | Enqueue review job (re-review) |
| `pull_request` | `closed` | Cleanup (optional) |
