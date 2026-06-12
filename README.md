# Rejection Feedback Engine

Open-source, self-hosted engine that turns rejections into honest,
criterion-based candidate feedback. Glass box, not black box: a
pre-declared rubric judges; your own LLM only extracts evidence and
writes the words. No candidate data leaves your infrastructure.

## How it works

1. Define (or AI-draft) a rubric for a role: criteria, must-haves, salary band.
2. Publish it — published rubrics are immutable (uniform application).
3. Evaluate candidates: the LLM extracts evidence per criterion; humans can override.
4. On rejection, feedback is composed ONLY from unmet criteria — a validator
   rejects any reason not linked to the published rubric.
5. A human approves; then it's delivered.

## Quick start (free, local LLM via Ollama)

    python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' uvicorn
    export RFE_LLM_BASE_URL=http://localhost:11434/v1
    export RFE_LLM_MODEL=llama3
    .venv/bin/uvicorn rfe.main:app

Works with any OpenAI-compatible API (OpenAI, vLLM, Ollama) — bring your own model.

## Run tests

    .venv/bin/pytest

## Status

Phase 1 (core engine). Spec: docs/specs/2026-06-12-rejection-feedback-engine-design.md
Roadmap: persistence (SQLite/Postgres), SMTP + tokenized feedback pages,
RBAC + encryption, web UI, ATS adapters (Greenhouse/Lever/Ashby).

## Deployment (Docker)

    cp .env.example .env        # fill in your values (never commit .env)
    docker compose up --build

The app listens on `:8000` (run behind a TLS-terminating reverse proxy in
production — see Security). Data (SQLite DB + audit log) persists in the
`rfe-data` volume.

## Security notes

- **No candidate data leaves your infra** — self-hosted, bring-your-own-LLM.
- **API-key auth:** every endpoint except the public feedback page (`/f/{token}`)
  requires `X-API-Key`. Set `RFE_API_KEYS` (comma-separated). Keys are
  compared in constant time.
- **Tokenized feedback page:** `/f/{token}` serves a single read-only page.
  Tokens are HMAC-signed and expire (`RFE_TOKEN_TTL_HOURS`, default 168h).
  A bad/expired/unknown token returns 404 — no enumeration.
- **Signed webhooks:** outbound webhook payloads carry an `X-RFE-Signature`
  HMAC header so receivers can verify origin.
- **Append-only audit log:** publish/approve/send/delete are recorded as
  JSONL (`RFE_AUDIT_LOG`) with action + entity id + timestamp — **no PII**.
- **No secrets in the repo:** `.env` is gitignored; CI runs `pip-audit`
  (dependency CVEs) and `gitleaks` (secret scanning) on every push/PR.
- **TLS:** terminate TLS at a reverse proxy; do not expose `:8000` directly
  to the internet.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RFE_LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible LLM endpoint |
| `RFE_LLM_MODEL` | `llama3` | Model name |
| `RFE_LLM_API_KEY` | _(empty)_ | LLM API key (if required) |
| `RFE_DB_PATH` | `./rfe.db` | SQLite database file path |
| `RFE_API_KEYS` | _(empty)_ | Comma-separated valid API keys |
| `RFE_AUDIT_LOG` | `./audit.jsonl` | Append-only audit log path |
| `RFE_TOKEN_SECRET` | _(empty)_ | HMAC secret for feedback-page tokens |
| `RFE_TOKEN_TTL_HOURS` | `168` | Feedback token lifetime (hours) |
| `RFE_SMTP_HOST` | `localhost` | SMTP server host |
| `RFE_SMTP_PORT` | `587` | SMTP server port |
| `RFE_SMTP_USER` | _(empty)_ | SMTP username (login skipped if empty) |
| `RFE_SMTP_PASS` | _(empty)_ | SMTP password |
| `RFE_SMTP_FROM` | `no-reply@localhost` | From address (use a no-reply address) |
| `RFE_WEBHOOK_URL` | _(unset)_ | Outbound webhook receiver URL |
| `RFE_WEBHOOK_SECRET` | _(empty)_ | HMAC secret for webhook signatures |
