# 07 — API reference

The REST API (`apps/api`, the `lens-api` service) is the HTTP control plane. It is a
thin adapter over the application use cases: routing, authentication, request/response
schemas, and error mapping. It never crawls or notifies itself — it writes configuration,
publishes "check now" tasks, and reads results.

- **Base path:** all routes are mounted under `/api/v1`.
- **Interactive docs:** OpenAPI at `/openapi.json`, Swagger UI at `/docs`.
- **Default port:** `8000`.

## Authentication & scopes

Authentication is via **bearer API keys**:

```
Authorization: Bearer <raw-key>
```

The raw key is SHA-256 hashed and looked up in the `api_keys` table. Each key carries a
set of **scopes**, which are **flat (non-hierarchical)** — `admin` does *not* imply
`read` or `write`; grant each explicitly.

| Scope   | Grants                                            |
|---------|---------------------------------------------------|
| `read`  | All `GET` endpoints.                              |
| `write` | Create/update/delete and trigger-check endpoints. |
| `admin` | Administrative endpoints (`/admin/*`).            |

The operational endpoints `/health`, `/ready`, and `/metrics` require **no** auth.

## Endpoint groups

### Operational

| Method | Path              | Purpose                                                        |
|--------|-------------------|----------------------------------------------------------------|
| GET    | `/api/v1/health`  | Liveness.                                                      |
| GET    | `/api/v1/ready`   | Readiness; returns 503 if a registered dependency check fails. |
| GET    | `/api/v1/metrics` | Prometheus metrics (text exposition).                          |

### Domains & categories

| Method                     | Path                              | Purpose                                               |
|----------------------------|-----------------------------------|-------------------------------------------------------|
| POST / GET                 | `/api/v1/domains`                 | Create / list domains (filters: `enabled`, `search`). |
| GET / PUT / PATCH / DELETE | `/api/v1/domains/{id}`            | Read / update / delete a domain.                      |
| POST / GET                 | `/api/v1/domains/{id}/categories` | Create / list categories under a domain.              |
| POST                       | `/api/v1/domains/{id}/check`      | Trigger a crawl for all URLs in the domain.           |
| GET / PATCH / DELETE       | `/api/v1/categories/{id}`         | Read / update / delete a category.                    |
| POST                       | `/api/v1/categories/{id}/check`   | Trigger a crawl for the category's URLs.              |

### URLs, changes & snapshots

| Method               | Path                                  | Purpose                                                                        |
|----------------------|---------------------------------------|--------------------------------------------------------------------------------|
| POST / GET           | `/api/v1/urls`                        | Create / list URLs (filters: `domain_id`, `category_id`, `enabled`, `search`). |
| GET / PATCH / DELETE | `/api/v1/urls/{id}`                   | Read / update / delete a URL.                                                  |
| POST                 | `/api/v1/urls/{id}/check`             | Trigger a crawl for a single URL.                                              |
| GET                  | `/api/v1/urls/{id}/changes`           | List changes (`since`, `limit`).                                               |
| GET                  | `/api/v1/urls/{id}/snapshots`         | List snapshots.                                                                |
| GET                  | `/api/v1/urls/{id}/snapshots/latest`  | Latest snapshot metadata.                                                      |
| GET                  | `/api/v1/changes/{id}`                | Change summary.                                                                |
| GET                  | `/api/v1/changes/{id}/diff`           | Unified diff text (streamed from the blob store).                              |
| GET                  | `/api/v1/changes/{id}/classification` | AI classification for the change (AI tier).                                    |
| GET                  | `/api/v1/snapshots/{id}`              | Snapshot metadata.                                                             |
| GET                  | `/api/v1/snapshots/{id}/content`      | Raw HTML content (from the blob store).                                        |

### Channels & bindings

| Method               | Path                    | Purpose                                            |
|----------------------|-------------------------|----------------------------------------------------|
| POST / GET           | `/api/v1/channels`      | Create / list notification channels.               |
| GET / PATCH / DELETE | `/api/v1/channels/{id}` | Manage a channel.                                  |
| POST / GET           | `/api/v1/bindings`      | Create / list channel bindings (scope + triggers). |
| GET / PATCH / DELETE | `/api/v1/bindings/{id}` | Manage a binding.                                  |

### Import / export

| Method | Path              | Purpose                                                                    |
|--------|-------------------|----------------------------------------------------------------------------|
| POST   | `/api/v1/imports` | Import a setup bundle (JSON/YAML/CSV; `on_conflict` = skip/merge/replace). |
| GET    | `/api/v1/exports` | Export a setup bundle as JSON (channel secrets are stripped).              |

### Admin

| Method              | Path                                                                         | Purpose                                           |
|---------------------|------------------------------------------------------------------------------|---------------------------------------------------|
| GET / POST          | `/api/v1/admin/dlq`, `/api/v1/admin/dlq/replay`, `/api/v1/admin/dlq/discard` | Inspect, replay, or discard dead-letter messages. |
| POST                | `/api/v1/admin/retention/run`                                                | Enforce snapshot retention (+ blob cleanup).      |
| POST                | `/api/v1/admin/retention/sweep-orphans`                                      | Delete unreferenced blobs.                        |
| GET / PUT / DELETE  | `/api/v1/admin/settings[...]`                                                | Read/update/delete dynamic settings.              |
| POST                | `/api/v1/admin/settings/reload`                                              | Re-broadcast settings to all instances.           |
| POST / GET / DELETE | `/api/v1/admin/api-keys[...]`                                                | Mint, list, and revoke API keys.                  |

## Cross-cutting behavior

- **Correlation IDs** — every request reads or generates an `X-Correlation-Id`, binds it
  to the structured log context, and echoes it back. Use it to trace a request across
  services.
- **Rate limiting** — a sliding-window limiter returns `429` with a `Retry-After`
  header. For multi-replica deployments use the Redis-backed limiter so the limit is
  shared across instances.
- **Pagination** — list endpoints return a cursor-paginated page; pass the returned
  cursor to fetch the next page.
- **Errors** — application errors are mapped to structured JSON with an error code;
  validation failures return `422`; unexpected errors return `500`. The payload never
  leaks internal detail.

## Composition note

The API delegates everything to application use cases wired in its composition root. In
a real deployment the API must be wired with a PostgreSQL unit-of-work factory, an API
key lookup, and (for full functionality) a task publisher, blob storage, and the admin
ports. The production wiring helper lives in `apps/api/src/lens_api/production.py`;
optional capabilities that are not wired return `503` rather than failing silently. See
`apps/api/README.md` and [Deployment & operations](11-deployment-and-operations.md).

## 📜 License

[AGPL-3.0-only](../LICENSE)
