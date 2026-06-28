<div align="center"><pre>
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓███████▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        
░▒▓█▓▒░      ░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ 
░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  
                                        ai
</pre>
</div>

<p align="center"><strong>🤖 LLM classification (OpenAI-compatible) &middot; 🔍 Meaningful-change detection &middot; 🏷️ Weak label learning &middot; 🔄 Idempotent enrichment &middot; 🐘 PostgreSQL &middot; 🐇 RabbitMQ &middot; 🗄️ Redis</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-f97316?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0.html"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square" alt="License: AGPL-3.0" /></a>
</p>

<p align="center"><strong>LLM-driven change enrichment.</strong> An optional worker that classifies page changes escalated by the crawler, using embeddings and LLMs to detect and learn significant updates.</p>

---

## 🤖 What it does

For each **enrichment task** (`ChangeNeedsEnrichment`) it:

1. Builds a classification request from the changed zone texts.
2. Calls an **OpenAI-compatible LLM** (e.g. a self-hosted vLLM/Ollama endpoint) for a
   structured result: change type, whether it is meaningful, severity, and a summary.
3. Persists the classification (one per change) plus a weak `llm` label for future
   learning/evaluation.
4. Updates the change's enrichment status and writes a **`ChangeEnriched`** event to the
   outbox so the notifier can deliver an enriched follow-up.

Enrichment is **idempotent** — a change that already has a classification is skipped.

## 🏃 Running

```bash
uv run lens-ai
```

The entrypoint creates the database engine, the LLM classifier, and a RabbitMQ consumer
(plus optional Redis idempotency/DLQ), then consumes the `enrich.tasks` queue until
shutdown. In docker-compose it runs as the `ai` role (enabled via the `ai`/`full`
profiles).

## ⚙️ Configuration

`LENS_`-prefixed environment variables, including:

- `LENS_AI_ENABLED` — master switch for the AI tier.
- `LENS_LLM_ENDPOINT` / `LENS_LLM_MODEL` / `LENS_LLM_TIMEOUT_SECONDS` — the LLM backend.
- `LENS_ENRICH_MAX_ATTEMPTS` / `LENS_ENRICH_RETRY_BASE_SECONDS` — retry/backoff.
- `LENS_DATABASE_URL`, `LENS_RABBITMQ_URL`, `LENS_REDIS_URL`.

See [`docs/09-configuration.md`](../../docs/09-configuration.md) and the AI tier overview
in [`docs/10-ai-enrichment.md`](../../docs/10-ai-enrichment.md).

## 🧩 Depends on

- **PostgreSQL** (classifications, labels, change status, outbox).
- **RabbitMQ** (consume enrichment tasks).
- **Redis** (optional idempotency and dead-letter queue).
- **An OpenAI-compatible LLM endpoint** (self-hosted or otherwise).

## 📝 Notes

- This worker classifies; **embeddings** for L4 semantic scoring are produced by the
  crawler when the AI tier is enabled.
- The base L0–L5 pipeline and all notifications work with this service disabled.

## 🔗 See also

- The escalation gate and learning jobs: [`docs/10-ai-enrichment.md`](../../docs/10-ai-enrichment.md).
- Event payloads: [`docs/08-message-contracts.md`](../../docs/08-message-contracts.md).
