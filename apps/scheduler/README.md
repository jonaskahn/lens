<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                            scheduler
</pre>
</div>

<p align="center"><strong>🎯 SKIP LOCKED concurrency &middot; 🔒 Per-URL lease &middot; ♻️ Auto backoff &middot; 🐘 PostgreSQL &middot; 🐇 RabbitMQ &middot; 🚀 Zero-coordination horizontal scale</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>Tick-based enqueuer</strong> &mdash; finds due URLs, claims leases, and fires crawl tasks into RabbitMQ. Built for <em>exactly-once</em> scheduling at scale.</p>

---

## 🔁 What it does

Every tick:

1. 🔍 **Finds** enabled, idle, due URLs in PostgreSQL (`SELECT … FOR UPDATE SKIP LOCKED`)
2. 📤 **Publishes** one crawl task per URL → RabbitMQ (`crawl` exchange → `crawl.tasks` queue)
3. 🔐 **Claims** each URL (sets lease) so no re-enqueue before the crawler finishes

> 💡 On-demand crawls bypass the scheduler — the API/CLI "check now" publishes directly.

## 🏃 Running

```bash
uv run lens-scheduler
```

Wire a PostgreSQL UoW factory + RabbitMQ publisher (+ optional Redis lock for leader election). Runs a tick loop until shutdown. In docker-compose → `scheduler` role.

## ⚙️ Configuration

`LENS_`-prefixed env vars:

| 🎛️ Knob | What |
|---|---|
| `LENS_SCHEDULER_TICK_SECONDS` | Tick interval (default `10`) |
| `LENS_SCHEDULER_BATCH_SIZE` | Max URLs enqueued per tick |
| `LENS_DATABASE_URL` | PostgreSQL connection |
| `LENS_RABBITMQ_URL` | RabbitMQ connection |
| `LENS_REDIS_URL` | Redis (optional, leader election) |
| `LENS_SHARD_ID` / `LENS_SHARD_COUNT` | Horizontal sharding for massive URL pools |
| `LENS_MAX_QUEUE_DEPTH` | Backpressure — pause when queue is full |
| `LENS_LEADER_LOCK_KEY` | Redis leader election key |

📖 See [`docs/09-configuration.md`](../../docs/09-configuration.md).

## 🧩 Depends on

| Service | Why |
|---|---|
| 🐘 **PostgreSQL** | Read due URLs, claim leases |
| 🐇 **RabbitMQ** | Publish crawl tasks |
| 🗄️ **Redis** | Leader election (optional) |

## 🔐 Scaling & safety

Multiple schedulers run safely via `SELECT … FOR UPDATE SKIP LOCKED` + per-URL lease → **no double-enqueue**. Tune `SHARD_ID`/`SHARD_COUNT` to partition work across replicas.

📖 See [`docs/06-messaging-and-scaling.md`](../../docs/06-messaging-and-scaling.md).

## 🔗 See also

- 📋 Crawl task contract: [`docs/08-message-contracts.md`](../../docs/08-message-contracts.md)
- 📥 Downstream consumer: [`apps/crawler_worker/README.md`](../crawler_worker/README.md)
