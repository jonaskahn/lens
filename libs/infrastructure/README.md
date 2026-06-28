<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                infrastructure
</pre>
</div>

<p align="center"><strong>Infrastructure adapters.</strong> Implements the application ports, providing SQL persistence, RabbitMQ event consumers/publishers, Crawl4AI scraping, Apprise notifications, and Redis locks.</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

---

## Why it exists

The application layer defines *interfaces*; this layer provides the *implementations*.
Keeping them separate means the business core never depends on a specific database or
broker, and technology can be swapped (or faked in tests) behind a stable port.

## What it provides

| Concern                | Adapter(s)                                                                                               | Talks to                              |
|------------------------|----------------------------------------------------------------------------------------------------------|---------------------------------------|
| **Persistence**        | SQLAlchemy repositories + a transactional `UnitOfWork`, with entity↔row mapping                          | PostgreSQL                            |
| **Migrations**         | Alembic revision chain                                                                                   | PostgreSQL                            |
| **Task queue**         | In-memory + RabbitMQ task publisher/subscriber                                                           | RabbitMQ                              |
| **Event bus**          | In-memory + RabbitMQ event publisher/consumer; the outbox relay loop                                     | RabbitMQ                              |
| **Blob storage**       | Gzip local-filesystem blob store (sync + async)                                                          | Filesystem (object store anticipated) |
| **Crawling**           | HTTP fetcher (`HttpxCrawler`) behind `CrawlerPort`                                                       | Target websites                       |
| **Content processing** | HTML normalizer, line differ, template fingerprint, zone extractor, template classifier, semantic scorer | (pure compute)                        |
| **Notifications**      | Apprise notifier, Jinja2 template renderer, channel secret provider                                      | Email/Slack/Discord/Telegram/webhook  |
| **Coordination**       | Redis locks, throttle, idempotency store, dead-letter store                                              | Redis                                 |
| **Secrets**            | Fernet cipher for channel secrets at rest                                                                | (crypto)                              |
| **AI tier**            | OpenAI-compatible LLM classifier; local embeddings + cache; auto-learning helpers                        | LLM endpoint / local models           |
| **Ops**                | Retention adapter, infrastructure metrics, dynamic settings store                                        | PostgreSQL / Prometheus               |

Almost every adapter has an **in-memory counterpart** so the whole system can run in a
single process for tests and local development; production wires the
PostgreSQL/RabbitMQ/Redis adapters at composition time.

## Database

The schema (domains, categories, urls, snapshots, changes, channels, bindings, api_keys,
outbox, notification_log, site_profiles, url_check_states, classifications, labels,
embeddings) is defined as SQLAlchemy models and managed with Alembic. See
[`docs/05-data-and-storage.md`](../../docs/05-data-and-storage.md). Run migrations with
`make migrate` or `LENS_DATABASE_URL=... uv run lens migrate`.

## How it is used

An **import-only library**. Apps call its factory functions (engine creation, the
unit-of-work factory, adapter constructors) in their composition roots and inject them
into use cases. Connection settings come from the environment (`LENS_DATABASE_URL`,
`LENS_RABBITMQ_URL`, `LENS_REDIS_URL`, `LENS_BLOB_ROOT`, `LENS_ENCRYPTION_KEY`); see
[`docs/09-configuration.md`](../../docs/09-configuration.md).

## Conventions & notes

- Repositories accept/return **domain entities**, never exposing ORM rows upward.
- Channel secrets are **encrypted at rest** with a Fernet cipher.
- Multi-instance safety relies on `SELECT … FOR UPDATE SKIP LOCKED` for due URLs plus
  Redis locks/idempotency; see [`docs/06-messaging-and-scaling.md`](../../docs/06-messaging-and-scaling.md).
- The shipped crawler is HTTP-based and the blob store is local-filesystem; both sit
  behind ports and can be swapped for richer backends without touching the business
  layers.
