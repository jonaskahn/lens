<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                domain
</pre>
</div>

<p align="center"><strong>Pure business model: entities, value objects, domain services, events.</strong> Enforces the URL lifecycle and validation logic without any I/O libraries or third-party framework details.</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

---

## Why it exists

This is the innermost layer of the Clean Architecture. Keeping it pure means the core
rules of the system can be reasoned about and tested in isolation, and they never change
just because a database or message broker changes. Everything else depends on this layer;
it depends on nothing but the shared error base.

## What it contains

- **Entities** — `Domain`, `Category`, `Url` (the central entity), `Snapshot`, `Change`,
  `Channel`, `ChannelBinding`, `SiteProfile`. Entities own their behavior: state
  transitions, validation, and event emission.
- **Value objects** — immutable, self-validating types such as `Hostname`, `Address`,
  `ContentHash`, `CrawlConfig`, `DiffConfig`, `Politeness`, `Interval`,
  `NotificationRouting`, `SignificanceRule`, and the zone/AI value objects.
- **Enums** — the controlled vocabularies (URL status, binding scope, channel kind,
  trigger type, change type, escalation reason, etc.).
- **Domain services** — pure algorithms: `EffectiveConfigResolver` (config precedence),
  `ChangeSignificanceEvaluator` (the L5 significance rules), and `NotificationRouter`
  (which channels receive an event).
- **Domain events** — the facts that drive notifications and enrichment
  (`UrlChangeDetected`, `UrlCrawlFailed`, `ChangeNeedsEnrichment`, `ChangeEnriched`, …).
- **Errors** — typed validation failures (`InvalidHostname`, `HostMismatch`,
  `InvalidStateTransition`, …), all descending from the shared `DomainError`.

## Key business rules captured here

- The **URL lifecycle** state machine (idle → enqueued → crawling → back to idle, with
  error backoff and disable). Only valid transitions are allowed.
- **Configuration precedence**: `URL ► Category ► Domain ► Global`, merged field-by-field.
- **Significance evaluation**: ignore → trigger → exclusion → minimum-length rules.
- **Notification routing**: most-specific binding wins per channel and trigger.

For the full narrative, see [`docs/03-domain-model.md`](../../docs/03-domain-model.md).

## How it is used

An **import-only library** with no I/O and no entrypoint. The application layer drives it;
ids and timestamps are passed in by callers (the domain never reaches for a clock or a
database). It is type-checked under `mypy --strict`.

## Conventions

- Value objects are **frozen** and validate on construction (raising `DomainError`).
- Entities are identified by id; they expose behavior, not raw setters.
- All ids are **UUIDv7**; all datetimes are timezone-aware **UTC**.
