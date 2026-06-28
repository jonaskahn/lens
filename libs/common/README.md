<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                common
</pre>
</div>

<p align="center"><strong>Shared kernel: config, logging, errors, ports, DI, types.</strong> Contains the cross-cutting utilities that every service needs to start up, log, observe itself, and wire dependencies. It holds no business rules and has no internal dependencies.</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

---

## Why it exists

Every role (API, scheduler, crawler, notifier, AI worker, CLI) needs the same
foundational concerns: typed configuration, structured logging, a consistent error
model, metrics, health checks, and graceful shutdown. Centralizing them here keeps the
business layers (`domain`, `application`) free of framework and operational concerns, and
keeps every service behaving consistently.

## What it provides

| Area                     | Purpose                                                                                                                          |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------|
| **Config**               | A typed settings base (env-driven, `LENS_` prefix) that each service extends; a loader that fails fast on bad config.            |
| **Logging**              | Structured logging (JSON or console) with automatic **correlation IDs** carried through each request/task.                       |
| **Errors**               | A layered exception hierarchy (domain / application / infrastructure) with stable error codes and an HTTP-mapping payload.       |
| **Dependency injection** | A small container used only by composition roots to register and resolve dependencies; business code uses constructor injection. |
| **Metrics**              | Prometheus metric definitions and factory, each with a private registry to avoid duplicate-timeseries clashes.                   |
| **Health**               | An async liveness/readiness aggregator that services register dependency checks on.                                              |
| **Lifecycle**            | Graceful shutdown on SIGTERM/SIGINT with ordered hooks.                                                                          |
| **Retry**                | Exponential backoff with jitter for transient failures.                                                                          |
| **Tracing**              | Optional OpenTelemetry export (a no-op if not installed/configured).                                                             |
| **Ports & types**        | A clock and a UUIDv7 id-generator interface (with defaults), plus shared id and cursor-pagination types.                         |

## How it is used

This is an **import-only library** — it has no entrypoint of its own. A typical service
startup uses it to load settings, configure logging, set up metrics, and register
shutdown hooks. Configuration is read from the environment with the `LENS_` prefix; see
[`docs/09-configuration.md`](../../docs/09-configuration.md).

## Conventions

- All timestamps are timezone-aware **UTC**; all ids are **UUIDv7**.
- Logging is idempotent to configure and never leaks internal error detail in payloads.
- The DI container is for composition roots only — never as a service locator inside
  business logic.

## Position in the architecture

It sits at the **bottom** of the dependency stack: every other layer may use it, and it
uses none of them. See [`docs/02-architecture.md`](../../docs/02-architecture.md).
