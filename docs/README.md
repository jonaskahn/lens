<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                                                      
                                                                documentation
</pre>
</div>

<p align="center">API-first service that tracks HTML changes across many website domains. For each tracked URL it periodically crawls the page, normalizes and diffs the HTML, detects whether the change is <em>meaningful</em>, stores a change history, and delivers notifications through multiple channels.</p>

This folder is the **detailed reference** for how the system is built and operated.
Each project folder (`apps/*`, `libs/*`) also has its own `README.md` with a focused,
self-contained overview; this `docs/` set is the cross-cutting, in-depth companion.

## How to read this

If you are new, read in this order:

| #  | Document                                                   | What it covers                                                                      |
|----|------------------------------------------------------------|-------------------------------------------------------------------------------------|
| 01 | [Overview](01-overview.md)                                 | What lens does, the primary use case, scope, glossary                               |
| 02 | [Architecture](02-architecture.md)                         | Clean Architecture layers, the dependency rule, the six runtime roles + web console |
| 03 | [Domain model](03-domain-model.md)                         | Entities, value objects, the URL lifecycle, config precedence                       |
| 04 | [Content-processing pipeline](04-content-pipeline.md)      | The L0–L5 change-detection pipeline and AI escalation                               |
| 05 | [Data & storage](05-data-and-storage.md)                   | PostgreSQL tables, blob storage, migrations, retention                              |
| 06 | [Messaging & scaling](06-messaging-and-scaling.md)         | RabbitMQ topology, outbox, idempotency, leases, DLQ, throttling                     |
| 07 | [API reference](07-api-reference.md)                       | REST endpoints, authentication, scopes, pagination, errors                          |
| 08 | [Message contracts](08-message-contracts.md)               | Task and event payloads, exchanges and queues                                       |
| 09 | [Configuration](09-configuration.md)                       | Environment variables per role, dynamic settings, secrets                           |
| 10 | [AI enrichment](10-ai-enrichment.md)                       | The optional AI tier: embeddings, LLM classification, auto-learning                 |
| 11 | [Deployment & operations](11-deployment-and-operations.md) | Images, compose, scaling, observability, runbook                                    |
| 12 | [Development](12-development.md)                           | Workspace layout, make targets, testing, conventions                                |
## The system in one picture

```
                 ┌─────────┐      ┌──────────────┐
   operators ──► │   API   │      │ web console  │ (operator UI, optional)
   & scripts ──► │  (CLI)  │ ◄──► │  Nuxt + BFF  │
                 └────┬────┘      └──────────────┘
                      │ writes config, publishes "check now"
                      ▼
                 ┌──────────────────────  PostgreSQL  ───────────────────────┐
                 │ domains · categories · urls · snapshots · changes · ...   │
                 └───────────────────────────────────────────────────────────┘
                      ▲                 ▲                      ▲
   schedule due URLs  │                 │ persist results      │ read history
                 ┌────┴─────┐     ┌─────┴──────┐         ┌─────┴──────┐
                 │scheduler │ ──► │  crawler   │ ──────► │ notifier   │ ──► channels
                 │ (tick)   │  ▲  │  worker    │ outbox  │ worker     │  (email/slack/…)
                 └──────────┘  │  └─────┬──────┘ events  └────────────┘
                  RabbitMQ ────┘        │ escalate (optional)
                  crawl tasks           ▼
                                  ┌────────────┐
                                  │ ai_worker  │ (optional LLM enrichment)
                                  └────────────┘
```

- **API / CLI** define *what* to monitor and read results; they never crawl.
- **Scheduler** finds due URLs and enqueues crawl tasks.
- **Crawler worker** fetches, diffs, decides significance, and persists results.
- **Notifier worker** publishes the outbox and delivers notifications.
- **AI worker** (optional) classifies escalated changes with an LLM.
- **Web console** is a pure client of the REST API via a server-side proxy.

PostgreSQL holds relational state, an object/blob store holds raw HTML and diffs,
Redis provides locks/throttle/idempotency, and RabbitMQ carries tasks and events.

## Source-of-truth note

These documents describe the system **as implemented in the code** under `libs/` and
`apps/`. Where the running stack depends on wiring choices (for example which crawler
or broker adapter is injected at startup), the docs call that out. Operational truth
(commands, environment variables, services) follows the `Makefile`,
`deploy/compose/docker-compose.yml`, and each app's `settings.py`.

## 📜 License

[AGPL-3.0-only](../LICENSE)
