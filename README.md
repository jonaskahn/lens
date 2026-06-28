<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░
                                        Track HTML changes at scale
</pre>
</div>

<p align="center"><strong>🎯 Zero false positives &middot; ⚡ L0&rarr;L5 noise filter pipeline &middot; 🤖 Optional AI enrichment (any OpenAI-compatible endpoint) &middot; 📢 Multi-channel: Email, Slack, Discord, Telegram, Webhook &middot; 🚀 Horizontally scalable &middot; 🧪 Test without Docker</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
    </p>

---

## What this is (and isn't)

Inspired by [changedetection.io](https://changedetection.io) — this is a **personal project** built to learn and to own. I wanted something I fully control, that I can hack on, and that scales the way I need it to. Not trying to replace anything; just building the thing I wished I had.

If it's useful to you too, great. If not, that's fine too.

---

## The problem

Naive "diff the HTML" drowns you in false positives — rotating ads, timestamps, layout churn — on *every* page load. **lens** answers the real question: _did something a human would actually care about change on this page?_

## Features

### 🔬 Six-level noise filter
Cheap checks kill noise early; expensive ones run only on survivors.

| L  | Check                                                                           | 💰 Cost |
|----|---------------------------------------------------------------------------------|---------|
| L0 | HTTP 304 → skip, zero diff work                                                 | Free    |
| L1 | Raw byte hash + config hash → unchanged? done                                   | Free    |
| L2 | DOM skeleton fingerprint → detect template drift, select zones                  | Tiny    |
| L3 | Zone hashing (header / price / legal / …) → noise-only? skip                    | Low     |
| L4 | Weighted lexical + embedding semantic score → below threshold? skip             | Medium  |
| L5 | Significance rules (ignore / trigger / must-not-be-present) → record or discard | Medium  |

### 📦 Bulk monitoring at scale
Import a domain setup (JSON / YAML / CSV) — categories, URLs, per-URL config — and lens takes over. Thousands of domains, millions of URLs, no double-processing.

### 🤖 AI enrichment _(optional)_
When changes are ambiguous, lens escalates to an LLM worker. Classification of type, severity, and meaningfulness via **any OpenAI-compatible endpoint** (self-hosted vLLM / Ollama, or cloud API). Fast first alert → richer follow-up once AI weighs in.

### 📢 Multi-channel notifications
Email, Slack, Discord, Telegram, webhook — routed at global, domain, category, or URL level. Trigger on **change**, on **error**, or on **silence** (no-change). Per-channel rate limiting.

### 🎩 Polite by design
Per-domain concurrency caps + minimum delay between requests to the same host. Throttled tasks are **requeued**, never dropped.

### 📜 Change history & diffs
Every meaningful change stored — unified diff, raw HTML snapshot, semantic score, AI classification — via cursor-paginated REST API, CLI, or web console.

### ⚡ Dynamic config hot-reload
Batch sizes, intervals, rate limits — pushed fleet-wide via broadcast channel, **no restart needed**.

## ⚙️ How it runs

Six independently scalable roles, sharing PostgreSQL + RabbitMQ, never calling each other directly:

```
  API / CLI ──► PostgreSQL ◄───────────────────────────────────────┐
                   ▲                                               │
  Scheduler ───────┤  enqueue due URLs (SKIP LOCKED + lease)       │
                   │                                               │
  Crawler ─────────┤  fetch → L0–L5 pipeline → snapshot + change   │
           outbox ─┤  (one transaction: snapshot + diff + event)   │
                   │                                               │
  Notifier ────────┘  drain outbox → route → render → send         │
                                                                   │
  AI worker  (optional) ◄── escalated changes ─────────────────────┘

  Web console  Nuxt 4 + BFF, pure REST API client
```

> 🔒 **No double-processing.** `SKIP LOCKED` scheduling + Redis locks + transactional outbox + idempotency keys — every hop guaranteed.

## Why lens

| 🏷️                           |                                                                                             |
|-------------------------------|---------------------------------------------------------------------------------------------|
| 🎯 **Zero false positives**   | Six pipeline levels filter ads, timestamps, layout churn before recording anything          |
| 📈 **Horizontally scalable**  | Every role runs N replicas; safety baked into protocol, not coordination                    |
| ✅ **Exactly-once delivery**   | Transactional outbox + dedup log — each event reaches each channel once                     |
| 🏠 **Self-hostable AI**       | Any OpenAI-compatible endpoint; no cloud provider required                                  |
| 🧠 **Site-profile learning**  | CLI jobs mine change history → auto-learn noise vs signal zones                             |
| 📋 **Full audit trail**       | Snapshots, diffs, classifications, notification logs — all retained, all queryable          |
| 🧪 **Zero-infra testing**     | Every adapter has an in-memory variant; full crawl→detect→notify runs in-process, no Docker |

## Repo layout

```
libs/
  common/           # 🧱 shared kernel: config, logging, DI, errors, ids, metrics
  domain/           # 🧬 pure business model (mypy --strict)
  application/      # ⚡ use cases + ports + DTOs (mypy --strict)
  infrastructure/   # 🔌 adapters: db, broker, crawler, notifier, storage, locks, AI
apps/
  api/              # 🌐 FastAPI REST API
  scheduler/        # ⏱️ tick-loop enqueuer
  crawler_worker/   # 🕷️ crawl-task consumer (crawl4ai)
  notifier_worker/  # 📬 outbox relay + event consumer (apprise)
  ai_worker/        # 🤖 optional LLM enrichment consumer
  cli/              # ⌨️ operator CLI
  web/              # 🖥️ Nuxt 4 operator console (separate TS app)
deploy/
  docker/           # 🐳 one Dockerfile per role + shared base
  compose/          # 🎼 local + integration docker-compose
  k8s/              # ☸️ Kubernetes manifests (optional)
docs/               # 📖 detailed reference (architecture, pipeline, API, ops)
```

## Quick start

```bash
make setup                        # install deps, generate .env, ENCRYPTION_KEY, and initial API key
make infra-up-infra               # postgres / rabbitmq / redis / minio
make db-migrate                   # apply migrations
make web-dev                      # frontend at http://localhost:3000
```

## Development

```bash
make format   # auto-fix lint + formatting
make verify   # lint + type-check + tests
make help     # full target reference
```

📖 Full reference: [`docs/`](docs/) — architecture, domain model, pipeline internals, API, messaging, deployment, AI enrichment.

## License

[AGPL-3.0-only](LICENSE)
