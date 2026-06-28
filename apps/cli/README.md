<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                cli
</pre>
</div>

<p align="center"><strong>💻 Rich terminal output &middot; 📥 Import/export setups &middot; 🗄️ Database migrations (Alembic) &middot; ⚡ On-demand crawl trigger &middot; 🧪 Test notifications &middot; 🐘 PostgreSQL &middot; 🐇 RabbitMQ</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>Operator command-line tool.</strong> Provides administrative command utilities for local runs, manual configuration imports/exports, dead-letter queue inspection, and database migrations.</p>

---

## 💻 Responsibilities

- Bulk **import/export** of setup files (JSON/YAML/CSV).
- **Database migrations** (Alembic).
- Manage **domains**, **categories**, **URLs**, **channels**, and **bindings**.
- **Trigger crawls** ("check now") and inspect **change history**, **diffs**, and
  **snapshots**.
- Send **test notifications** to a channel.
- Optional **auto-learning / ops** commands (zone learning, template clustering,
  evaluation, labeling) when wired.

## 🏃 Running

```bash
uv run lens --help              # list commands
uv run lens import setup.json   # import a setup bundle
uv run lens migrate             # apply database migrations
uv run lens domain list         # browse entities (most lists support --format json)
uv run lens check now --url <id>   # enqueue a crawl (needs a task publisher wired)
uv run lens notify test --channel <id>
```

Output is rendered with Rich; most list commands support `--format table|json` for
scripting.

## ⚙️ Configuration

Reads `LENS_`-prefixed environment variables; notably **`LENS_DATABASE_URL`** is required
for entity commands and `migrate`. See [`docs/09-configuration.md`](../../docs/09-configuration.md).

## 🧩 Depends on

- **PostgreSQL** for all entity commands, import/export, and migrations.
- **RabbitMQ** for `check now` (when a task publisher is wired).
- **Apprise-compatible targets** for `notify test` (sends a real notification).

## 📝 Notes

- The CLI is **local-only** (not part of the docker-compose role set).
- `make migrate` runs Alembic directly; `uv run lens migrate` does the same via the CLI
  using `LENS_DATABASE_URL`.

## 🔗 See also

- The use cases it drives: [`libs/application/README.md`](../../libs/application/README.md).
- Architecture & roles: [`docs/02-architecture.md`](../../docs/02-architecture.md).
