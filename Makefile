# ═══════════════════════════════════════════════════════════════════════
# AegisAI — ergonomic Docker entry points
# ═══════════════════════════════════════════════════════════════════════

DOCKER_COMPOSE := docker compose

.PHONY: help up down logs ps build shell api-shell worker-shell test \
        lint health clean reset config

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Start the full dev stack (redis + api + worker)
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up -d

down: ## Stop the stack
	$(DOCKER_COMPOSE) down

logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f --tail=100

ps: ## Show running services
	$(DOCKER_COMPOSE) ps

build: ## Build images (dev target)
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml build

shell: ## Open a shell in the api container
	$(DOCKER_COMPOSE) exec api /bin/sh

api-shell: ## Alias for shell
	$(DOCKER_COMPOSE) exec api /bin/sh

worker-shell: ## Open a shell in the worker container
	$(DOCKER_COMPOSE) exec worker /bin/sh

test: ## Run the test suite inside the api image
	$(DOCKER_COMPOSE) exec api python -m pytest tests/ -v

lint: ## Lint with flake8 (critical errors)
	$(DOCKER_COMPOSE) exec api python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

health: ## Check API health endpoint
	curl -fsS http://localhost:8000/health

config: ## Validate compose files
	$(DOCKER_COMPOSE) config

clean: ## Stop and remove containers + volumes (data loss!)
	$(DOCKER_COMPOSE) down -v --remove-orphans

reset: clean ## Full rebuild from scratch
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up -d
