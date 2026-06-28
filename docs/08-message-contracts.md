# 08 — Message contracts

This document describes the messages that flow over RabbitMQ: the **crawl task** the
scheduler produces, and the **domain events** the outbox relay publishes. For the
topology (exchanges, queues, routing keys) and delivery guarantees, see
[Messaging & scaling](06-messaging-and-scaling.md).

## Envelope

All broker messages share a JSON envelope:

```json
{
  "message_id": "0190a0c2-...",
  "type": "UrlChangeDetected",
  "occurred_at": "2026-06-28T08:15:30Z",
  "attempt": 1,
  "data": { "...": "type-specific payload" }
}
```

- `type` selects the handler.
- `attempt` drives retry/backoff and dead-lettering.
- `data` carries the type-specific fields below.

## Crawl task

Produced by the scheduler (and by the API/CLI "check now") onto the `crawl` exchange
with routing key `crawl.task`.

| Field            | Meaning                                                              |
|------------------|----------------------------------------------------------------------|
| `url_id`         | The URL to crawl.                                                    |
| `task_id`        | Idempotency id, derived from `url_id` + scheduled slot.              |
| `scheduled_slot` | The due timestamp this task corresponds to.                          |
| `reason`         | `scheduled` (from the scheduler) or `manual` (from a trigger-check). |

The crawler worker uses `task_id` to drop duplicate deliveries and `scheduled_slot` to
reason about which polling slot the work belongs to.

## Domain events

Written to the `outbox` table by the use cases and published by the outbox relay onto
the `events` exchange (and `enrich` exchange for AI escalation). Each carries a stable
`event_id` used for deduplication.

| Event `type`                | Routing key       | Emitted when                                   | Key `data` fields                                                                         |
|-----------------------------|-------------------|------------------------------------------------|-------------------------------------------------------------------------------------------|
| `UrlChangeDetected`         | `url.changed`     | A meaningful change was recorded               | `url_id`, `change_id`, `new_snapshot_id`, `significant`, diff summary                     |
| `UrlCrawlFailed`            | `url.failed`      | A crawl attempt failed                         | `url_id`, error info, `consecutive_errors`                                                |
| `UrlBecameStale`            | `url.stale`       | A URL went too long without a successful check | `url_id`, last-checked info                                                               |
| `SiteTemplateDriftDetected` | `site.drift`      | A page's template skeleton changed materially  | `domain_id`, profile info                                                                 |
| `ChangeNeedsEnrichment`     | `change.enrich`   | A change was escalated to the AI tier          | `change_id`, `url_id`, `domain_id`, changed zones, `escalation_reasons`, `template_class` |
| `ChangeEnriched`            | `change.enriched` | The AI tier finished classifying a change      | `change_id`, classification (`change_type`, `is_meaningful`, severity, summary)           |

## How consumers use them

| Consumer            | Subscribes to                                                                                                              | Action                                                                     |
|---------------------|----------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| **notifier worker** | `change.events` queue on the `events` exchange (`url.changed`, `url.failed`, `url.stale`, `site.drift`, `change.enriched`) | Route → render → send notifications, deduped per `(event_id, channel_id)`. |
| **AI worker**       | `enrich.tasks` queue on the `enrich` exchange (`change.enrich`)                                                            | Classify the change with an LLM and write a `ChangeEnriched` outbox event. |

The notifier maps each event type to a notification **trigger**:

| Event                                                              | Trigger      |
|--------------------------------------------------------------------|--------------|
| `UrlChangeDetected`, `ChangeEnriched`, `SiteTemplateDriftDetected` | on change    |
| `UrlCrawlFailed`                                                   | on error     |
| `UrlBecameStale`                                                   | on no change |

Events whose change is classified as cosmetic/layout (or marked not meaningful by the AI
tier) are suppressed before sending.

## Dynamic configuration broadcast

A separate `config` fanout exchange broadcasts setting changes to every running instance
so they can hot-reload runtime-mutable settings. See [Configuration](09-configuration.md).

> Maintainer note: the routing of `change`-aggregate outbox rows (the AI escalation and
> enriched events) is worth verifying end-to-end against your broker bindings, since both
> the escalation request and the enriched result originate from `change`-aggregate rows.
> The intended destinations are `change.enrich` (to the AI worker) for escalation and
> `change.enriched` (to the notifier) for the enriched result.

## 📜 License

[AGPL-3.0-only](../LICENSE)
