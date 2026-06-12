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

## Phase 3: Security & Web UI

### PII encryption at rest

Set `RFE_ENCRYPTION_KEY` to a Fernet key and candidate PII (`name`, `email`,
`resume_text`, `salary_expectation`) is encrypted in the SQLite database.
Without it, PII is stored in plaintext (not recommended in production).

Generate a key:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

> **WARNING: Key loss is permanent data loss.** If you lose `RFE_ENCRYPTION_KEY`,
> all existing candidate rows become undecryptable. Store it in a secrets
> manager (AWS Secrets Manager, Vault, etc.), never in this file or the repo.

### Retention auto-purge

`RFE_RETENTION_DAYS` (default `365`) controls how long candidate records are
kept. Set to `0` to disable. Purge cascades: deletes the candidate's
evaluations and feedback too.

Trigger a purge: `POST /admin/purge` (admin role required). Candidates with no
`created_at` (rows created before Phase 3) are never purged — fail safe.

### Right-to-erasure (GDPR/DSAR)

`DELETE /candidates/{id}` (admin role required) cascade-deletes a candidate
plus their evaluations and feedback. Audit-logged by entity id only — no PII
in the audit log.

### RBAC

Three roles: `admin` (everything), `recruiter` (+write workflow), `viewer`
(GET only). Configure `RFE_API_KEYS` with `key:role` pairs:

    RFE_API_KEYS="adminkey:admin,reckey:recruiter,viewkey:viewer"

A bare key (no `:role`) defaults to `admin` — Phase 2 keys keep full access.
Keys are compared in constant time (HMAC). Unauthorized roles return 403.

### Web UI

Open `http://localhost:8000/` in your browser, paste an API key, and manage
rubrics, candidates, and feedback. No build step — pure HTML/CSS/JS, no JS
dependencies. Set `RFE_SERVE_UI=0` to disable.

## Status

Phase 3 complete: encryption at rest, retention purge, right-to-erasure, RBAC,
web UI. Spec: docs/specs/2026-06-12-rejection-feedback-engine-design.md
Roadmap: Postgres adapter, KMS key management, key rotation tooling, ATS
adapters (Greenhouse/Lever/Ashby).

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
| `RFE_API_KEYS` | _(empty)_ | Comma-separated `key:role` pairs (`admin`/`recruiter`/`viewer`); bare key = `admin` |
| `RFE_ENCRYPTION_KEY` | _(empty)_ | Fernet key for PII encryption at rest; unset = plaintext (not recommended) |
| `RFE_RETENTION_DAYS` | `365` | Auto-purge candidates older than N days; `0` = disabled |
| `RFE_SERVE_UI` | `1` | Serve web UI at `/`; set to `0` to disable |
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
