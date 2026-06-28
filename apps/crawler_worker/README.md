<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                        crawler
</pre>
</div>

<p align="center"><strong>🕷️ Concurrent scraping &middot; 🔒 Per-URL distributed lock &middot; ⏱️ Per-domain politeness throttle &middot; 🌀 L0&ndash;L5 change detection &middot; 🐘 PostgreSQL &middot; 🐇 RabbitMQ &middot; 🗄️ Redis &middot; 📦 Blob storage</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>Scraping and change detection.</strong> A background worker that consumes check tasks, fetches page contents via Crawl4AI, processes them through the L0&ndash;L5 change detection pipeline, and persists snapshots.</p>

---

## 🕷️ What it does

For each **crawl task** it:

1. Drops duplicate deliveries via an **idempotency key**.
2. Applies **per-domain throttling** (politeness).
3. Takes a **per-URL distributed lock** so no other worker processes the same URL.
4. Runs `ProcessCrawlTaskUseCase`: fetch HTML → normalize → run the **L0–L5 pipeline** →
   diff → persist snapshot/change/diff → write any domain event to the **outbox** —
   all in one database transaction.
5. Acknowledges, requeues (if throttled), or retries (on error); poison tasks go to the
   dead-letter queue.

See [`docs/04-content-pipeline.md`](../../docs/04-content-pipeline.md) for the levels.

## 🏃 Running

```bash
uv run lens-crawler
```

The entrypoint must be wired at composition time with: a PostgreSQL unit-of-work factory,
the crawl/normalize/diff adapters, blob storage, a per-URL lock, and a broker subscriber
(plus optional Redis throttle/idempotency/DLQ and a publisher for requeues). It then
consumes the `crawl.tasks` queue until shutdown. In docker-compose it runs as the
`crawler` role and is the main horizontal scaling lever.

## ⚙️ Configuration

`LENS_`-prefixed environment variables, including:

- `LENS_CRAWLER_CONCURRENCY` / `LENS_CRAWLER_PREFETCH` — throughput knobs.
- `LENS_CRAWLER_LEASE_TTL_SECONDS` — per-URL lock/lease TTL.
- `LENS_CRAWL_MAX_ATTEMPTS` / `LENS_CRAWL_RETRY_BASE_SECONDS` — retry/backoff.
- `LENS_POLITENESS_MIN_DELAY_SECONDS` / `LENS_POLITENESS_MAX_RATE` — per-host politeness.
- `LENS_DATABASE_URL`, `LENS_RABBITMQ_URL`, `LENS_REDIS_URL`, `LENS_BLOB_ROOT`.

See [`docs/09-configuration.md`](../../docs/09-configuration.md).

## 🧩 Depends on

- **PostgreSQL** (URLs, snapshots, changes, check-state, outbox).
- **RabbitMQ** (consume crawl tasks; requeue throttled/failed tasks).
- **Redis** (per-URL locks, throttle, idempotency, DLQ).
- **Blob storage** (raw HTML snapshots and unified diffs).

## 🔐 Scaling & safety

Run many replicas and tune concurrency. Double-processing is prevented by the
idempotency key + Redis lock + database lease combination; see
[`docs/06-messaging-and-scaling.md`](../../docs/06-messaging-and-scaling.md). When running
multiple replicas, the blob store must be shared.

## 🔗 See also

- The producer: [`apps/scheduler/README.md`](../scheduler/README.md).
- The outbox/events that result: [`docs/08-message-contracts.md`](../../docs/08-message-contracts.md).
