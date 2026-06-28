# 09 — Configuration

lens configuration comes in two tiers:

- **Bootstrap** — environment variables, read at startup. These include connection
  settings (database, broker, Redis, blob storage) and secrets. They are immutable for
  the life of the process.
- **Dynamic** — operational settings stored in the database, changeable at runtime via
  the admin API/CLI and broadcast to every instance.

## Environment variables

Each service has a typed settings class (`settings.py`) built on the shared
`lens_common.config.Settings` base. **The settings classes read variables with the
`LENS_` prefix** (e.g. `LENS_DATABASE_URL`). The repository's `.env.example` is a broad
reference of the full configuration surface; the canonical names actually read by the
code are the `LENS_`-prefixed ones below.

### Shared (all roles)

| Variable                   | Default | Meaning                                                             |
|----------------------------|---------|---------------------------------------------------------------------|
| `LENS_APP_ROLE`            | `api`   | One of `api` / `scheduler` / `crawler` / `notifier` / `ai` / `cli`. |
| `LENS_LOG_LEVEL`           | `INFO`  | Log level.                                                          |
| `LENS_LOG_FORMAT`          | `json`  | `json` or `console`.                                                |
| `LENS_GLOBAL_MIN_INTERVAL` | `300`   | Floor (seconds) for URL polling intervals.                          |
| `LENS_MAX_SNAPSHOTS`       | `25`    | Per-URL snapshot retention cap.                                     |

### Connection settings (roles that need them)

| Variable              | Used by                                        | Meaning                                            |
|-----------------------|------------------------------------------------|----------------------------------------------------|
| `LENS_DATABASE_URL`   | api, scheduler, crawler, notifier, ai, cli     | PostgreSQL DSN.                                    |
| `LENS_RABBITMQ_URL`   | scheduler, crawler, notifier, ai               | RabbitMQ URL.                                      |
| `LENS_REDIS_URL`      | scheduler (leader lock), crawler, notifier, ai | Redis URL for locks/throttle/idempotency/DLQ.      |
| `LENS_BLOB_ROOT`      | crawler, notifier                              | Local filesystem root for blob storage.            |
| `LENS_ENCRYPTION_KEY` | notifier (and anything persisting channels)    | Fernet key for encrypting channel secrets at rest. |

### API (`lens-api`)

| Variable                 | Default | Meaning                               |
|--------------------------|---------|---------------------------------------|
| `LENS_API_RATE_LIMIT`    | `100`   | Requests per window per bucket.       |
| `LENS_API_RATE_WINDOW`   | `60`    | Rate-limit window (seconds).          |
| `LENS_API_MAX_PAGE_SIZE` | `200`   | Maximum page size for list endpoints. |

### Scheduler (`lens-scheduler`)

| Variable                             | Default                 | Meaning                                          |
|--------------------------------------|-------------------------|--------------------------------------------------|
| `LENS_SCHEDULER_TICK_SECONDS`        | `10`                    | Interval between scheduling ticks.               |
| `LENS_SCHEDULER_BATCH_SIZE`          | `100`                   | Max URLs enqueued per tick.                      |
| `LENS_MAX_QUEUE_DEPTH`               | `1000`                  | Backpressure threshold.                          |
| `LENS_SHARD_ID` / `LENS_SHARD_COUNT` | `0` / `1`               | Sharding identity for multi-instance scheduling. |
| `LENS_LEADER_LOCK_KEY`               | `lens:scheduler:leader` | Redis key for optional leader election.          |

### Crawler worker (`lens-crawler`)

| Variable                            | Default | Meaning                                     |
|-------------------------------------|---------|---------------------------------------------|
| `LENS_CRAWLER_CONCURRENCY`          | `4`     | Max concurrent crawl tasks.                 |
| `LENS_CRAWLER_PREFETCH`             | `4`     | Broker QoS prefetch.                        |
| `LENS_CRAWLER_LEASE_TTL_SECONDS`    | `120`   | Per-URL lock / DB lease TTL.                |
| `LENS_CRAWL_MAX_ATTEMPTS`           | `3`     | Attempts before dead-lettering.             |
| `LENS_CRAWL_RETRY_BASE_SECONDS`     | `5`     | Exponential backoff base for retries.       |
| `LENS_POLITENESS_MIN_DELAY_SECONDS` | `5`     | Delay used when requeuing a throttled task. |
| `LENS_POLITENESS_MAX_RATE`          | `10`    | Max requests/sec per domain host.           |

### Notifier worker (`lens-notifier`)

| Variable                          | Default | Meaning                                |
|-----------------------------------|---------|----------------------------------------|
| `LENS_NOTIFIER_PREFETCH`          | `8`     | Broker QoS prefetch.                   |
| `LENS_NOTIFIER_POLL_SECONDS`      | `1`     | Outbox relay tick interval.            |
| `LENS_NOTIFIER_OUTBOX_BATCH_SIZE` | `100`   | Outbox rows per relay tick.            |
| `LENS_NOTIFY_MAX_ATTEMPTS`        | `3`     | Notification retry cap.                |
| `LENS_NOTIFY_RETRY_BASE_SECONDS`  | `5`     | Backoff base for notification retries. |
| `LENS_PER_CHANNEL_MAX_RATE`       | `10`    | Max sends/sec per channel.             |

### AI worker (`lens-ai`)

| Variable                         | Default                    | Meaning                              |
|----------------------------------|----------------------------|--------------------------------------|
| `LENS_AI_ENABLED`                | `false`                    | Master switch for the AI tier.       |
| `LENS_AI_PREFETCH`               | `2`                        | Broker QoS prefetch.                 |
| `LENS_LLM_ENDPOINT`              | `http://localhost:8000/v1` | OpenAI-compatible LLM base URL.      |
| `LENS_LLM_MODEL`                 | `Qwen2.5-7B-Instruct`      | Model id.                            |
| `LENS_LLM_TIMEOUT_SECONDS`       | `30`                       | LLM request timeout.                 |
| `LENS_ENRICH_MAX_ATTEMPTS`       | `4`                        | Enrichment retry cap.                |
| `LENS_ENRICH_RETRY_BASE_SECONDS` | `5`                        | Backoff base for enrichment retries. |

See [AI enrichment](10-ai-enrichment.md) for the full AI tuning surface.

## Secrets

- **Channel secrets** (Apprise URLs) are encrypted at rest in the database using a Fernet
  cipher; the encryption key is provided via `LENS_ENCRYPTION_KEY` (a base64 32-byte
  key). Generate one with:

  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- **API keys** are stored only as SHA-256 hashes; the raw key is shown once at creation.
- **The web console** keeps the backend API key server-side only (never in the browser)
  and seals its session cookie with a `NUXT_SESSION_PASSWORD`. See `apps/web/README.md`.

## Dynamic configuration

A subset of operational settings is stored in the database and can be changed at runtime
through the admin settings endpoints (see [API reference](07-api-reference.md)). On
change, the new value is broadcast over a `config` fanout exchange so every running
instance can apply it according to its reload policy (hot-reload, restart-required, or
ignore-by-role). Bootstrap connection settings and secrets remain environment-only.

## 📜 License

[AGPL-3.0-only](../LICENSE)
