<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                notifier
</pre>
</div>

<p align="center"><strong>📬 Outbox relay to RabbitMQ &middot; 📨 Multi-channel delivery (Apprise) &middot; 🔒 Exactly-once deduplication &middot; 📝 Templated messages with diffs &middot; 🐘 PostgreSQL &middot; 🐇 RabbitMQ &middot; 🗄️ Redis &middot; 📦 Blob storage</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>Notification dispatcher.</strong> An outbox relay and multi-channel delivery worker that publishes events and dispatches notifications through email, Slack, and other Apprise-supported backends.</p>

---

## 📬 What it does

- **Outbox relay** — polls unsent rows in the `outbox` table and publishes them to
  RabbitMQ, marking each sent. This is what makes event publication exactly-once despite
  crashes (the crawler writes the event in the same transaction as the change).
- **Event consumer** — consumes the `change.events` queue and, for each event:
  routes it to the right channels (via the domain `NotificationRouter`), renders the
  message from a template, applies suppression/throttling, and sends it — deduplicating
  per `(event_id, channel_id)` so nothing is sent twice.

Handled events: URL changed, crawl failed, URL stale, template drift, and AI-enriched
changes (mapped to on-change / on-error / on-no-change triggers).

## 🏃 Running

```bash
uv run lens-notifier
```

The entrypoint is wired with a PostgreSQL unit-of-work factory, a broker consumer and an
event publisher (for the relay and retries), the notifier/renderer adapters, blob storage,
and optional Redis throttle/idempotency/DLQ. The production wiring helper is
`src/lens_notifier/production.py`. In docker-compose it runs as the `notifier` role.

## ⚙️ Configuration

`LENS_`-prefixed environment variables, including:

- `LENS_NOTIFIER_POLL_SECONDS` / `LENS_NOTIFIER_OUTBOX_BATCH_SIZE` — outbox relay cadence.
- `LENS_NOTIFY_MAX_ATTEMPTS` / `LENS_NOTIFY_RETRY_BASE_SECONDS` — retry/backoff.
- `LENS_PER_CHANNEL_MAX_RATE` — per-channel send rate.
- `LENS_DATABASE_URL`, `LENS_RABBITMQ_URL`, `LENS_REDIS_URL`, `LENS_BLOB_ROOT`,
  `LENS_ENCRYPTION_KEY`.

See [`docs/09-configuration.md`](../../docs/09-configuration.md).

## 🧩 Depends on

- **PostgreSQL** (outbox, notification log, entity lookups).
- **RabbitMQ** (publish the outbox; consume change events).
- **Redis** (per-channel throttle, idempotency, dead-letter queue).
- **Blob storage** (diff snippets for templated messages).
- **Apprise-compatible targets** (email/Slack/Discord/Telegram/webhook).

## 🛡️ Delivery guarantees

The outbox + `notification_log` dedup combination gives effectively exactly-once delivery
per channel across multiple replicas. Failed sends are retried with backoff and ultimately
dead-lettered. See [`docs/06-messaging-and-scaling.md`](../../docs/06-messaging-and-scaling.md).

## 🔗 See also

- Event payloads: [`docs/08-message-contracts.md`](../../docs/08-message-contracts.md).
- Routing rules: [`docs/03-domain-model.md`](../../docs/03-domain-model.md).
