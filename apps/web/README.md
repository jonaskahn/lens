<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                web
</pre>
</div>

<p align="center"><strong>🖥️ Admin dashboard &middot; 🔐 BFF proxy (API key never reaches browser) &middot; 📋 CRUD for all entities &middot; 🔍 Change &amp; diff inspection &middot; ⚙️ Admin: DLQ, retention, API keys &middot; 🌐 Lens REST API</strong></p>

<p align="center">
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/node-%3E%3D_20.0.0-339933?style=flat-square&logo=node.js&logoColor=white" alt="Node >= 20.0.0" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>Nuxt-based web console.</strong> An admin dashboard and operator UI client for managing tracked domains, categories, logs, and notification channels.</p>

---

## 🖥️ What it does

A browser UI over the same capabilities as the API:

- A **dashboard** of domain/URL health and status.
- CRUD for **domains**, **categories**, and **URLs** (interval, crawl/diff config, "check
  now").
- Inspect **changes**, **diffs**, **snapshots**, and AI **classifications**.
- Manage notification **channels** and **bindings**; send test notifications.
- **Import/export** setups.
- **Admin**: dynamic settings, dead-letter queue, retention, and API keys.

## 🔗 How it talks to the backend

All backend access goes through a server-side **backend-for-frontend (BFF)** so the Lens
API key **never reaches the browser bundle**:

```
browser → /api/* (Nuxt server proxy) → Lens REST API
```

The BFF injects the API key server-side, enforces the operator's session scope per
request, and applies CSRF protection on mutating requests. Login validates the operator's
own API key to derive their session **scopes** (`read` / `write` / `admin`), which gate
UI and BFF access. Data is fetched on demand (no polling or websockets).

## 🏃 Running

```bash
cd apps/web
pnpm install
pnpm dev            # dev server on http://localhost:3000
pnpm build && pnpm preview   # production build
```

From the repo root you can also use `make web-dev`, `make web-build`, `make web-test`.
Generate typed API bindings from a running backend with `pnpm gen:api`.

## ⚙️ Configuration

Server-only runtime config (mapped from `NUXT_`-prefixed env vars):

| Variable | Purpose |
| --- | --- |
| `NUXT_API_BASE_URL` | Base URL of the Lens REST API (e.g. `http://api:8000/api/v1`). |
| `NUXT_API_KEY` | The backend API key — **server-side only**, injected by the BFF. |
| `NUXT_SESSION_PASSWORD` | Secret (≥32 chars) used to seal the session cookie. |

The API key and session secret are never exposed to the client. Protect `NUXT_API_KEY`:
it carries the console's effective backend permissions.

## 🧩 Depends on

- A reachable **Lens REST API** (the only backend dependency).
- **Node 24 + pnpm** at build/runtime.

In docker-compose the console runs as the `web` service (profiles `web`/`full`) on port
`3000` and points at the `api` service.

## 🔗 See also

- API surface it consumes: [`docs/07-api-reference.md`](../../docs/07-api-reference.md).
- Architecture & roles: [`docs/02-architecture.md`](../../docs/02-architecture.md).
