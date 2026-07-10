# Dependency Graph — AegisAI

## File Dependencies
```
worker.py
  └── app.config (settings)
  └── app.workers.review_worker (job function)
  └── redis (connection)
  └── rq (Worker, Connection)

app/
├── main.py
│   └── fastapi, uvicorn
│   └── app.config
│   └── app.workers.review_worker
├── config.py
│   └── pydantic-settings
│   └── python-dotenv
└── workers/
    └── review_worker.py
        └── httpx (HTTP client)
        └── PyJWT (GitHub auth)

requirements.txt (all external deps)
.env.example (configuration template)
```

## Critical Files
| File | Impact |
|------|--------|
| `app/config.py` | All settings — must be configured correctly |
| `app/workers/review_worker.py` | Core review logic — most complex module |
| `worker.py` | Worker entry point — must match server config |
