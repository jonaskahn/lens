<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                api
</pre>
</div>

<p align="center"><strong>🌐 REST + OpenAPI (FastAPI) &middot; 🔐 API key auth with flat scopes &middot; 📥 Import/export (JSON/YAML/CSV) &middot; ⚡ On-demand crawl trigger &middot; 📊 Change history &amp; diffs &middot; 🐘 PostgreSQL &middot; 🐇 RabbitMQ &middot; 🗄️ Redis &middot; 📦 Blob storage</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>HTTP control plane.</strong> A FastAPI adapter over the shared application use cases, letting operators and scripts manage configurations, trigger on-demand crawls, and read change history.</p>

---

## 🌐 Responsibilities

- Manage **domains**, **categories**, and **URLs** (what to crawl and how often).
- Manage **notification channels** and **bindings** (where alerts go).
- **Import/export** setup bundles (JSON/YAML/CSV).
- **Trigger on-demand crawls** ("check now").
- Read **change history**, **diffs**, **snapshots**, and AI **classifications**.
- **Admin/ops**: dead-letter queue inspect/replay/discard, retention sweeps, dynamic
  settings, and API-key lifecycle.

All business logic lives in `lens_application`; this app is routing, authentication,
request/response schemas, middleware, and composition wiring.

## 🏃 Running

```bash
uv run lens-api      # starts uvicorn on 0.0.0.0:8000
```

- API base path: `/api/v1`. OpenAPI at `/openapi.json`, Swagger UI at `/docs`.
- In a real deployment the service is wired with a PostgreSQL unit-of-work factory, an
  API-key lookup, and (for full functionality) a task publisher, blob storage, and the
  admin ports. The production wiring helper is `src/lens_api/production.py`. Capabilities
  that are not wired return `503` rather than failing silently.

## 🔐 Authentication

Bearer **API keys** (`Authorization: Bearer <key>`) with **flat scopes** `read`,
`write`, `admin` (none implies another — grant explicitly). The keys are stored as
SHA-256 hashes. `/health`, `/ready`, and `/metrics` need no auth.

## ⚙️ Configuration

Reads `LENS_`-prefixed environment variables (rate-limit window/size, page size, plus the
shared connection settings supplied at composition time). See
[`docs/09-configuration.md`](../../docs/09-configuration.md).

## 🧩 Depends on

- **PostgreSQL** for all CRUD and API-key lookup.
- **RabbitMQ** for "check now", async import, and DLQ admin.
- **Redis** for shared (multi-replica) rate limiting and readiness checks.
- **Blob storage** for serving diffs and snapshot content.

It is **stateless** and scales to many replicas behind a load balancer.

## ⚡ Cross-cutting behavior

- **Correlation IDs** threaded through logs (`X-Correlation-Id`).
- **Rate limiting** (`429` + `Retry-After`); use the Redis-backed limiter for shared
  limits across replicas.
- **Cursor pagination** on list endpoints.
- Structured **error mapping** to HTTP status codes.

## 🔗 See also

- Full endpoint reference: [`docs/07-api-reference.md`](../../docs/07-api-reference.md).
- Architecture & roles: [`docs/02-architecture.md`](../../docs/02-architecture.md).
