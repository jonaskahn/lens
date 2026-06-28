# 11 — Deployment & operations

lens is a **multi-image** system: each role builds from the shared codebase and runs as
its own process/container. They share PostgreSQL, RabbitMQ, Redis, and a blob store, but
do not call each other directly.

## Backing services

| Service              | Role                              | Local default (compose)                           |
|----------------------|-----------------------------------|---------------------------------------------------|
| PostgreSQL           | Relational state                  | `postgres:16` on `5432`                           |
| RabbitMQ             | Task queue + event bus            | `rabbitmq:3.13-management` on `5672` (UI `15672`) |
| Redis                | Locks, throttle, idempotency, DLQ | `redis:7` on `6379`                               |
| MinIO (object store) | Blob storage (optional)           | `minio` on `9000` (console `9001`)                |

## Images

Container builds live under `deploy/`:

- `deploy/docker/base.Dockerfile` — the shared Python base image all roles run from. The
  per-role container simply runs that role's console script (`lens-api`,
  `lens-scheduler`, `lens-crawler`, `lens-notifier`, `lens-ai`).
- `deploy/docker/web.Dockerfile` — the Nuxt web console (Node 24 + pnpm).
- `deploy/compose/docker-compose.yml` — the local stack (infra + roles).
- `deploy/k8s/` — Kubernetes manifest notes.

## Local stack with docker compose

```bash
# infrastructure only (postgres, rabbitmq, redis, minio)
make up-infra

# full stack (infra + all roles) — uses the "full" compose profile
make up

# include the web console
docker compose -f deploy/compose/docker-compose.yml --profile web up -d

# tail logs / list / tear down
make logs
make ps
make down
```

The compose file reads a root `.env` file. Copy `.env.example` to `.env` first and fill
in secrets (notably `ENCRYPTION_KEY`, and `NUXT_API_KEY` / `NUXT_SESSION_PASSWORD` for the
web console).

> Wiring note: the role containers run the console scripts directly. Each role's
> entrypoint must be wired with its production adapters (PostgreSQL unit-of-work factory,
> broker publisher/consumer, Redis clients, blob storage) for the container to serve
> traffic — see each app's `README.md` and `production.py` where present. Treat the
> compose file as the deployment topology; confirm production wiring before relying on a
> role in a real environment.

## First-run checklist

1. **Bring up infra:** `make up-infra`.
2. **Run migrations:** `make migrate` (or `LENS_DATABASE_URL=... uv run lens migrate`).
3. **Create an admin API key** (via the bootstrap key mechanism / admin endpoint) so you
   can call the API.
4. **Import a setup** describing the domains/categories/URLs to monitor:
   `uv run lens import examples/your-setup.json`.
5. **Start the roles** (`make up`) and watch the scheduler enqueue, the crawler process,
   and the notifier deliver.

## Scaling guidance

| Role      | Scale                                | Notes                                                                               |
|-----------|--------------------------------------|-------------------------------------------------------------------------------------|
| api       | Many replicas behind a load balancer | Stateless. Use the Redis-backed rate limiter so limits are shared.                  |
| scheduler | One or a few replicas                | Uses `SKIP LOCKED` + URL leases; optional leader election via Redis.                |
| crawler   | The main horizontal lever            | Scale replicas and `LENS_CRAWLER_CONCURRENCY`; per-host politeness keeps it polite. |
| notifier  | A few replicas                       | Outbox relay + `notification_log` dedup keep delivery exactly-once.                 |
| ai        | Optional, scale to LLM capacity      | Only runs when `LENS_AI_ENABLED=true`.                                              |

When running multiple crawler/notifier replicas, ensure the blob store is shared (a
shared volume or an object-store adapter), since snapshots/diffs written by one worker
are read by the API and other workers.

## Observability

- **Metrics** — each role exposes Prometheus metrics; the API serves them at
  `/api/v1/metrics`. Notable series include task throughput, crawl duration, diff
  outcomes, notification results, lease contention, throttle waits, queue depth, DLQ
  size, and (AI) enrichment duration / token usage.
- **Logs** — structured (JSON by default) with a **correlation id** threaded through each
  request/task so a single operation can be traced across services.
- **Health/readiness** — `GET /api/v1/health` (liveness) and `GET /api/v1/ready`
  (readiness; flips to 503 when a registered dependency check fails).

## Runbook (common operations)

| Situation                           | Action                                                                                                                     |
|-------------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| A page's crawls keep failing        | Check `GET /urls/{id}` for status/backoff; inspect recent `UrlCrawlFailed` notifications; verify the URL and crawl config. |
| Messages piling up / poison tasks   | Inspect the DLQ: `GET /api/v1/admin/dlq`; replay or discard after fixing the cause.                                        |
| Storage growing                     | Run retention: `POST /api/v1/admin/retention/run` and `.../sweep-orphans`; tune `LENS_MAX_SNAPSHOTS`.                      |
| Too many/few notifications          | Adjust channel **bindings** and **triggers**, and the diff/significance config; tune per-channel rate.                     |
| Change a runtime setting fleet-wide | Use the admin settings endpoints; the change is broadcast to all instances.                                                |
| Rotate a channel secret             | Update the channel; it is re-encrypted at rest with the configured Fernet key.                                             |

## Development vs. production wiring

Every external dependency has an **in-memory adapter** used by tests and single-process
local runs, and a **production adapter** (PostgreSQL/RabbitMQ/Redis) wired at composition
time. This is why the test suite runs without any infrastructure, and why bringing up a
real deployment is primarily a matter of providing connection settings and confirming the
production composition for each role. See [Development](12-development.md).

## 📜 License

[AGPL-3.0-only](../LICENSE)
