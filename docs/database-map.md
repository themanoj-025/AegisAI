# Database Map — AegisAI

## Database: PostgreSQL (optional)
The PostgreSQL database is optional — used for logging and tracking review history.

### Tables (from code reference)
| Table | Purpose | Key Fields |
|-------|---------|------------|
| `reviews` | Store review results | id, pr_number, repo, status, findings |

## Redis (Required)
Redis is used as the job queue backend (not as a database).

## Storage
| Storage | Purpose |
|---------|---------|
| `workspace/` | Temporary directory for cloned repos (cleaned after job) |
| `./github-app-private-key.pem` | GitHub App private key file |
