<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
              application
</pre>
</div>

<p align="center"><strong>Application use cases, ports, and orchestration logic.</strong> Coordinates use cases to carry out system workflows and defines the interfaces (ports) implemented by the infrastructure layer.</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

---

## Why it exists

This layer is the seam between *what the system does* (use cases) and *how the outside
world is reached* (ports/adapters). Because it depends only on `domain` and `common`, the
entire application behavior is unit-testable with in-memory fakes, and any external
technology can be swapped without touching business logic.

## What it contains

### Use cases

One class per operation, each with a single `async execute(...)` that runs inside one
unit-of-work transaction. Grouped by area:

- **Configuration CRUD** — domains, categories, URLs, channels, bindings.
- **Import / export** — bulk setup bundles with conflict policies.
- **Crawl & change detection** — enqueue due URLs, trigger checks, and the central
  `ProcessCrawlTaskUseCase` that runs the L0–L5 pipeline and persists results.
- **Notifications** — drain the outbox and route/render/send change, error, and stale
  events; send test notifications.
- **AI enrichment** — classify escalated changes (the AI tier).
- **Auto-learning** — zone learning, template clustering, evaluation, labeling.
- **Operations / scaling** — dead-letter inspect/replay/discard, retention, dynamic
  settings.
- **API keys** — mint, list, revoke (hash-only storage).

### Ports

The interfaces adapters must implement — for example `UnitOfWork` and the repositories,
`CrawlerPort`, `HtmlNormalizerPort`, `DifferPort`, `BlobStoragePort`,
`TaskPublisherPort` / `TaskSubscriberPort`, `EventPublisherPort` / `EventConsumerPort`,
`NotifierPort`, `LockPort`, `ThrottlePort`, `IdempotencyPort`, and the AI ports
(`ChangeClassifierPort`, `EmbeddingPort`).

### DTOs & the pipeline

Immutable input/output data-transfer objects (decoupled from HTTP and ORM shapes), and
the content-processing pipeline contracts and orchestration that drive change detection.

## How it is used

An **import-only library** with no entrypoint. Each app's composition root builds a
unit-of-work factory and the required adapters, then constructs use cases and calls
`execute(...)`. The typical path is: *driver (HTTP / CLI / queue handler)* →
`use_case.execute(dto)` → *infrastructure adapters perform the I/O*.

## Conventions

- **One use case = one class** with a single `async execute`, committing on success.
- Depends only on `domain` and `common` — never on `infrastructure` or I/O libraries.
- Uses domain entities and services for all business rules; it orchestrates, it does not
  re-implement them.

## See also

- The pipeline: [`docs/04-content-pipeline.md`](../../docs/04-content-pipeline.md).
- The messaging/outbox model: [`docs/06-messaging-and-scaling.md`](../../docs/06-messaging-and-scaling.md).
