# Contributing to AegisAI

Thanks for your interest in AegisAI! Contributions — bug reports, documentation, and pull requests — are welcome.

## Getting started

1. Fork the repository and clone your fork.
2. Create a feature branch: `git checkout -b feature/amazing`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and add your GitHub App credentials and LLM API key.

## Development workflow

- Add or update tests for every change.
- Run the test suite: `pytest tests/ -v`.
- Run the linter: `make lint` (flake8).
- Verify the app boots: `docker compose up -d` or `uvicorn app.main:app --reload`.

## Commit conventions

Keep commits small and focused. Prefix messages with a type, e.g. `feat:`, `fix:`, `docs:`, `test:`.

## Opening a pull request

1. Push your branch and open a PR against `main`.
2. Describe what you changed and why.
3. Link any related issue.

By contributing, you agree that your contributions are licensed under the MIT License.
