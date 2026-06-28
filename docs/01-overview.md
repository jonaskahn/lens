# 01 — Overview

## What lens is

**lens** is a focused, API-first HTML change-tracking service. It monitors web pages
across a large number of website domains, detects *meaningful* changes (filtering out
noise such as rotating ads, timestamps, or layout churn), keeps a history of changes,
and notifies interested parties through multiple channels.

It is built to run as a set of independently scalable services rather than a single
monolith, so each part of the workload (serving the API, scheduling, crawling,
notifying, AI enrichment) can be scaled to fit demand.

## The problem it solves

Watching websites for changes is easy to do badly. Naive "diff the HTML" approaches
drown users in false positives because most of a page changes on every load. lens
exists to answer a sharper question: *did something a human would care about actually
change on this page?* — and to do so reliably across thousands of pages.

## Primary use case

1. An **operator** imports a *setup* for a domain: a list of URL **categories**, the
   URLs in each category, and per-URL crawl / diff / notify configuration.
2. The system **schedules** each URL according to its polling interval.
3. **Crawler workers** fetch each due URL, normalize the HTML, and diff it against the
   last stored snapshot.
4. When a **meaningful change** (or an error) is detected, a **notification** is
   dispatched to the channels bound to that URL/category/domain.
5. The operator queries **change history**, **diffs**, and **snapshots** via the API,
   CLI, or web console.

## Scale assumptions

The design targets a large fleet:

- Thousands to tens of thousands of domains.
- One to hundreds of URLs per domain (millions of URLs at the top end).
- Every role scales horizontally with **no double-processing** and **no duplicated
  data**, using distributed locks, a transactional outbox, and idempotency keys.
- **Per-domain politeness**: bounded concurrency and a minimum delay between requests
  to the same host.

## In scope

- Bulk import/export of `domain → category → URL` setups (JSON / YAML / CSV).
- HTTP-based fetching with per-URL fetch configuration.
- HTML normalization, hashing, text diffing, ignore rules, and change deduplication.
- A template-aware, multi-level change-detection pipeline (see
  [Content pipeline](04-content-pipeline.md)).
- Snapshot and change history with retention.
- Per-URL scheduling, a distributed task queue, and per-domain throttling.
- Multi-channel notifications (email, Slack, Discord, Telegram, webhook) with routing
  precedence and templated bodies.
- A REST API and a CLI over a shared application core.
- An optional **operator web console** (a separate Nuxt front end, pure API client).
- Horizontal scalability primitives: a message broker, idempotency, distributed
  locking, a transactional outbox, and dead-letter queues.
- **Dynamic configuration**: operational settings that can be changed at runtime.
- An optional **AI enrichment layer** (off by default) that classifies and summarizes
  the small fraction of escalated changes.

## Out of scope

- Image / pixel / screenshot-based visual diffing.
- Real-time browser push (the web console polls the API; there is no server push).
- Alternative fetch backends beyond the configured crawler adapter.

## Glossary

| Term              | Meaning                                                                                              |
|-------------------|------------------------------------------------------------------------------------------------------|
| **Domain**        | A website host being monitored (e.g. `example.com`); holds default config.                           |
| **Category**      | A named grouping of URLs within a domain (e.g. `products`).                                          |
| **URL**           | A single tracked page; the unit of crawling and diffing (the `Url` entity).                          |
| **Snapshot**      | One normalized HTML capture of a URL at a point in time, with a content hash.                        |
| **Change**        | A detected diff between two consecutive snapshots.                                                   |
| **Channel**       | A notification destination (an Apprise URL) bound at global/domain/category/url level.               |
| **Binding**       | A link from a channel to a scope, with trigger flags (on change / error / no change).                |
| **Setup**         | An importable bundle: a domain plus its categories, URLs, and config.                                |
| **Role**          | The runtime function of a deployed process (`api`, `scheduler`, `crawler`, `notifier`, `ai`, `cli`). |
| **Lease / Claim** | A time-bounded lock so only one worker processes a URL at a time.                                    |
| **Outbox**        | A database table that buffers events to be published exactly once to the broker.                     |
| **Site Profile**  | Per-domain rules (zone selectors, significance rules) used by the deeper pipeline levels.            |

## Where to go next

- To understand how the code is organized, read [Architecture](02-architecture.md).
- To understand the core algorithm, read [Content pipeline](04-content-pipeline.md).
- To run it, read [Deployment & operations](11-deployment-and-operations.md).

## 📜 License

[AGPL-3.0-only](../LICENSE)
