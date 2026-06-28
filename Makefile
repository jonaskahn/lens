# lens - Makefile
# ============================================================================
# QUICK START (first time)
#
#   1. make setup          — install deps, generate ENCRYPTION_KEY + initial API key
#   2. make infra-up-infra — start postgres / rabbitmq / redis / minio
#   3. make db-migrate     — apply database migrations
#   4. make web-dev        — start the Vue/Nuxt dev server (http://localhost:3000)
#
# Typical dev loop:
#   make format   →   make verify   →   make infra-logs
# ============================================================================

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# ---- tool knobs ------------------------------------------------------------
PYTHON         ?= python3.12
UV             ?= uv
COMPOSE        ?= docker compose
COMPOSE_FILE   ?= deploy/compose/docker-compose.yml
ALEMBIC        ?= $(UV) run alembic
BLACK          ?= $(UV) run black
RUFF           ?= $(UV) run ruff
MYPY           ?= $(UV) run mypy
PYRIGHT        ?= $(UV) run pyright
PYTEST         ?= $(UV) run pytest

# ---- workspace knobs -------------------------------------------------------
WORKSPACE_DIRS := libs apps
PYPROJECT_ROOT := pyproject.toml
WEB_DIR        := apps/web
PNPM           ?= pnpm
WEB_RUN        := cd $(WEB_DIR) && $(PNPM)

# ============================================================================
# help
# ============================================================================
.PHONY: help
help: ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
	  /^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)

# ============================================================================
##@ Quick Start
# ============================================================================

.PHONY: setup
setup: install web-install hooks ## Bootstrap the project for first-time development.
	@if [ ! -f .env ]; then \
	  cp .env.example .env; \
	  echo ""; \
	  echo "\033[33m[setup]\033[0m .env created from .env.example."; \
	else \
	  echo "\033[32m[setup]\033[0m .env already exists."; \
	fi
	@# Auto-fill ENCRYPTION_KEY if blank
	@if grep -qE '^ENCRYPTION_KEY=\s*$$' .env; then \
	  ENC_KEY=$$($(UV) run python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
	  $(UV) run python3 -c "import sys, re; p = '.env'; c = open(p).read(); c = re.sub(r'^ENCRYPTION_KEY=.*', 'ENCRYPTION_KEY=' + sys.argv[1], c, flags=re.M); open(p, 'w').write(c)" "$$ENC_KEY"; \
	  echo "\033[32m[setup]\033[0m ENCRYPTION_KEY generated and written to .env."; \
	fi
	@# Auto-fill API_KEYS_BOOTSTRAP if blank
	@if grep -qE '^API_KEYS_BOOTSTRAP=\s*$$' .env; then \
	  RAW_KEY=$$($(UV) run python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
	  $(UV) run python3 -c "import sys, re; p = '.env'; c = open(p).read(); c = re.sub(r'^API_KEYS_BOOTSTRAP=.*', 'API_KEYS_BOOTSTRAP=admin-001:' + sys.argv[1] + ':read,write,admin', c, flags=re.M); open(p, 'w').write(c)" "$$RAW_KEY"; \
	  echo ""; \
	  echo "\033[1;32m[setup]\033[0m Initial admin API key generated:"; \
	  echo ""; \
	  echo "  \033[1;36m$$RAW_KEY\033[0m"; \
	  echo ""; \
	  echo "\033[33m  Use this key to log in at the Nuxt web UI (/login).\033[0m"; \
	  echo "\033[33m  It has been written to API_KEYS_BOOTSTRAP in .env.\033[0m"; \
	else \
	  echo "\033[32m[setup]\033[0m API_KEYS_BOOTSTRAP already set, skipping key generation."; \
	fi
	@# Create apps/web/.env from apps/web/.env.example
	@if [ ! -f $(WEB_DIR)/.env ]; then \
	  cp $(WEB_DIR)/.env.example $(WEB_DIR)/.env; \
	  echo "\033[33m[setup]\033[0m $(WEB_DIR)/.env created from .env.example."; \
	else \
	  echo "\033[32m[setup]\033[0m $(WEB_DIR)/.env already exists."; \
	fi
	@# Sync NUXT_API_KEY from API_KEYS_BOOTSTRAP
	@if grep -qE '^NUXT_API_KEY=\s*$$' $(WEB_DIR)/.env; then \
	  RAW_KEY=$$(grep -E '^API_KEYS_BOOTSTRAP=' .env | cut -d: -f2); \
	  $(UV) run python3 -c "import sys, re; p = '$(WEB_DIR)/.env'; c = open(p).read(); c = re.sub(r'^NUXT_API_KEY=.*', 'NUXT_API_KEY=' + sys.argv[1], c, flags=re.M); open(p, 'w').write(c)" "$$RAW_KEY"; \
	  echo "\033[32m[setup]\033[0m NUXT_API_KEY synced from API_KEYS_BOOTSTRAP."; \
	fi
	@# Generate NUXT_SESSION_PASSWORD if blank
	@if grep -qE '^NUXT_SESSION_PASSWORD=\s*$$' $(WEB_DIR)/.env; then \
	  SESSION_PWD=$$($(UV) run python3 -c "import secrets; print(secrets.token_hex(32))"); \
	  $(UV) run python3 -c "import sys, re; p = '$(WEB_DIR)/.env'; c = open(p).read(); c = re.sub(r'^NUXT_SESSION_PASSWORD=.*', 'NUXT_SESSION_PASSWORD=' + sys.argv[1], c, flags=re.M); open(p, 'w').write(c)" "$$SESSION_PWD"; \
	  echo "\033[32m[setup]\033[0m NUXT_SESSION_PASSWORD generated."; \
	fi
	@echo ""
	@echo "\033[1mNext steps:\033[0m"
	@echo "  1. make infra-up-infra"
	@echo "  2. make db-migrate"
	@echo "  3. make web-dev        (frontend)"
	@echo "  4. uv run lens ...     (backend CLI)"

# ============================================================================
##@ Install / Dependencies
# ============================================================================

.PHONY: install
install: ## Install all Python workspace packages + dev deps (uv sync).
	$(UV) sync --all-packages --all-groups

.PHONY: web-install
web-install: ## Install web app JS dependencies (pnpm install).
	cd $(WEB_DIR) && $(PNPM) install --no-frozen-lockfile

.PHONY: lock
lock: ## Refresh the uv lockfile.
	$(UV) lock

# ============================================================================
##@ Code Quality
# ============================================================================

.PHONY: lint
lint: ## ruff check + black --check + ruff format --check (no changes applied).
	$(RUFF) check $(WORKSPACE_DIRS)
	$(BLACK) --check $(WORKSPACE_DIRS)
	$(RUFF) format --check $(WORKSPACE_DIRS)

.PHONY: format
format: ## Auto-fix lint issues, apply black + ruff formatting.
	$(RUFF) check --fix $(WORKSPACE_DIRS)
	$(BLACK) $(WORKSPACE_DIRS)
	$(RUFF) format $(WORKSPACE_DIRS)

.PHONY: type
type: mypy pyright ## Run all type-checkers (mypy + pyright).

.PHONY: mypy
mypy: ## mypy --strict over the full workspace.
	$(MYPY) --strict

.PHONY: pyright
pyright: ## pyright type-check over the full workspace.
	$(PYRIGHT)

.PHONY: verify
verify: lint type test ## Full local verification gate: lint + type-check + unit tests.

# ============================================================================
##@ Testing
# ============================================================================

.PHONY: test
test: ## Unit tests only (excludes integration).
	$(PYTEST) -m "not integration"

.PHONY: test-int
test-int: ## Integration tests — spins testcontainers, requires Docker.
	$(PYTEST) -m integration

.PHONY: test-all
test-all: test test-int ## Run all tests (unit + integration).

.PHONY: cov
cov: ## Generate HTML coverage report → htmlcov/index.html.
	$(PYTEST) --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ============================================================================
##@ Infrastructure (Docker Compose)
# ============================================================================

.PHONY: infra-up
infra-up: ## Bring up the full local stack (infra + all app roles).
	$(COMPOSE) -f $(COMPOSE_FILE) up -d
	@echo "Stack is up. Tail logs: make infra-logs"

.PHONY: infra-up-infra
infra-up-infra: ## Bring up infrastructure services only (postgres, rabbitmq, redis, minio).
	$(COMPOSE) -f $(COMPOSE_FILE) up -d postgres rabbitmq redis minio

.PHONY: infra-down
infra-down: ## Stop and remove the local stack.
	$(COMPOSE) -f $(COMPOSE_FILE) down

.PHONY: infra-logs
infra-logs: ## Tail logs from the local stack (last 200 lines).
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=200

.PHONY: infra-ps
infra-ps: ## Show running compose services.
	$(COMPOSE) -f $(COMPOSE_FILE) ps

# ============================================================================
##@ Database
# ============================================================================

.PHONY: db-migrate
db-migrate: ## Apply all pending migrations (alembic upgrade head).
	$(ALEMBIC) -c libs/infrastructure/migrations/alembic.ini upgrade head

.PHONY: db-rollback
db-rollback: ## Roll back the last applied migration (alembic downgrade -1).
	$(ALEMBIC) -c libs/infrastructure/migrations/alembic.ini downgrade -1

.PHONY: db-seed
db-seed: ## Import the sample dataset (dev convenience).
	@echo "No sample-setup.json is shipped; drop one in examples/ and run:"
	@echo "  uv run lens import examples/sample-setup.json"

# ============================================================================
##@ Build / Images
# ============================================================================

.PHONY: build
build: ## Build all container images via docker compose.
	$(COMPOSE) -f $(COMPOSE_FILE) build

.PHONY: build-base
build-base: ## Build the shared Python base image only.
	docker build -f deploy/docker/base.Dockerfile -t lens-base:latest .

.PHONY: web-build
web-build: ## Build the web app for production (nuxt build).
	$(WEB_RUN) build

# ============================================================================
##@ Run (local dev)
# ============================================================================

.PHONY: run-api
run-api: ## Start the API server (uvicorn, hot-reload).
	$(UV) run lens-api

.PHONY: run-scheduler
run-scheduler: ## Start the scheduler worker.
	$(UV) run lens-scheduler

.PHONY: run-crawler
run-crawler: ## Start the crawler worker.
	$(UV) run lens-crawler

.PHONY: run-notifier
run-notifier: ## Start the notifier worker.
	$(UV) run lens-notifier

.PHONY: run-ai
run-ai: ## Start the AI worker.
	$(UV) run lens-ai

.PHONY: run-cli
run-cli: ## Run the lens CLI (pass ARGS="..." to forward arguments).
	$(UV) run lens $(ARGS)

# ============================================================================
##@ Web UI
# ============================================================================

.PHONY: web-dev
web-dev: ## Start the Nuxt dev server at http://localhost:3000.
	$(WEB_RUN) dev

.PHONY: web-lint
web-lint: ## Lint the web app (eslint, check only).
	$(WEB_RUN) lint

.PHONY: web-lint-fix
web-lint-fix: ## Lint and auto-fix the web app.
	$(WEB_RUN) lint:fix

.PHONY: web-typecheck
web-typecheck: ## Type-check the web app (vue-tsc).
	$(WEB_RUN) typecheck

.PHONY: web-test
web-test: ## Run web unit tests (vitest).
	$(WEB_RUN) test

.PHONY: web-test-e2e
web-test-e2e: ## Run web E2E tests (playwright).
	$(WEB_RUN) test:e2e

.PHONY: web-gen-api
web-gen-api: ## Generate TypeScript API types from the running backend.
	$(WEB_RUN) gen:api

# ============================================================================
##@ Hooks / CI
# ============================================================================

.PHONY: hooks
hooks: ## Install pre-commit hooks.
	.venv/bin/pre-commit install

.PHONY: hooks-run
hooks-run: ## Run pre-commit hooks against all files.
	.venv/bin/pre-commit run --all-files

# ============================================================================
##@ Cleanup
# ============================================================================

.PHONY: clean
clean: ## Remove build artefacts, caches, and coverage outputs.
	rm -rf .pytest_cache .mypy_cache .ruff_cache .pyright .coverage htmlcov build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +

.PHONY: clean-venv
clean-venv: ## Remove the Python virtual environment (.venv).
	rm -rf .venv
