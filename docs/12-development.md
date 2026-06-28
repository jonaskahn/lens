# 12 — Development

## Prerequisites

- **Python 3.12+** (the workspace targets 3.12/3.13).
- **[uv](https://docs.astral.sh/uv/)** for Python dependency and workspace management.
- **Docker** (for the local infra stack and integration tests).
- **Node 24 + pnpm** (only for the `apps/web` console).

## Workspace layout

The repository is a **uv workspace**. The root `pyproject.toml` is a virtual meta-package;
the real packages live under `libs/*` and `apps/*`:

```
libs/
  common/           # shared kernel: config, logging, DI, errors, ids, clock, metrics
  domain/           # pure business model (mypy --strict)
  application/      # use cases + ports + DTOs (mypy --strict)
  infrastructure/   # adapters: db, broker, crawler, notifier, storage, locks, AI
apps/
  api/              # FastAPI HTTP service
  scheduler/        # tick-loop enqueuer
  crawler_worker/   # crawl-task consumer
  notifier_worker/  # outbox relay + event consumer
  ai_worker/        # optional LLM enrichment consumer
  cli/              # operator CLI
  web/              # Nuxt operator console (separate TS app, not in the uv workspace)
deploy/             # Dockerfiles, docker-compose, k8s
docs/               # this documentation set
```

Each package has its own `README.md`.

## Common tasks (Makefile)

| Command                                             | What it does                                                |
|-----------------------------------------------------|-------------------------------------------------------------|
| `make install`                                      | `uv sync --all-packages --all-groups` — install everything. |
| `make lint`                                         | `ruff check` + `ruff format --check`.                       |
| `make format`                                       | `ruff check --fix` + `ruff format`.                         |
| `make type`                                         | `mypy --strict` over the configured scope.                  |
| `make test`                                         | Unit tests (excludes integration).                          |
| `make test-int`                                     | Integration tests (spins up testcontainers; needs Docker).  |
| `make cov`                                          | HTML coverage report under `htmlcov/`.                      |
| `make verify`                                       | `lint` + `type` + `test` (the pre-push gate).               |
| `make up-infra` / `make up` / `make down`           | Manage the local stack.                                     |
| `make migrate`                                      | Apply database migrations.                                  |
| `make hooks`                                        | Install pre-commit hooks.                                   |
| `make web-dev` / `make web-build` / `make web-test` | Web console workflows.                                      |

## Testing strategy

- **Unit/fast tests run with no infrastructure.** Almost every port has an in-memory
  adapter (in-memory unit-of-work, broker, locks, blob store, throttle, idempotency), so
  the full crawl → detect → notify flow can be exercised in-process.
- **Integration tests** (marked `integration`) use testcontainers to run against real
  PostgreSQL/RabbitMQ/Redis; run them with `make test-int`.
- **Test naming convention:** `test_given_{state}_when_{action}_then_{outcome}`.
- Tests live in each package's `tests/` directory; the web app uses Vitest under
  `apps/web`.

## Code conventions

These are enforced by tooling (ruff, mypy) and review; the full rationale is in the
repository's `CONVENTIONS.md`.

- **Constructor injection only** — no global singletons or service locators in business
  code; apps wire dependencies in their composition root.
- **The dependency rule** — `domain` and `application` must not import infrastructure or
  third-party I/O libraries (only Pydantic). `mypy --strict` guards these layers.
- **Value objects are frozen and self-validating**; entities expose behavior, not setters.
- **One use case = one class** with a single `async execute(...)`, running inside one
  unit-of-work transaction.
- **Repositories return/accept domain entities**, never ORM rows.
- **All datetimes are timezone-aware UTC; all ids are UUIDv7.**
- **Line length 100**, double quotes, isort-ordered imports (ruff config in the root
  `pyproject.toml`).

## Adding a new capability (typical path)

1. Model it in `domain` (entities/value objects/services) if it introduces business rules.
2. Define the **port** (interface) and a **use case** in `application`, plus any DTOs.
3. Implement the **adapter** in `infrastructure` (and an in-memory variant for tests).
4. Wire it into the relevant app's composition root and expose it (an HTTP route, a CLI
   command, or a worker handler).
5. Add unit tests (in-memory) and, where it touches real I/O, an integration test.

## Type-checking and linting scope

`mypy --strict` is configured over `libs/*` and `apps/*` source. The domain and
application layers are the strictest boundary and should always be green. ruff handles
linting and formatting across `libs` and `apps`.

## 📜 License

[AGPL-3.0-only](../LICENSE)
