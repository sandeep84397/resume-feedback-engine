# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x (latest) | Yes |
| Older 0.x | No |

Only the latest release on the `main` branch receives security fixes.
Self-hosted deployments should stay current.

## Responsible Disclosure

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately via [GitHub Security Advisories](https://github.com/sandeepdhami/rejection-feedback-engine/security/advisories/new):

1. Click "Report a vulnerability" on the Security tab.
2. Describe the issue: component, reproduction steps, impact.
3. We aim to acknowledge reports within **3 business days** and resolve
   or provide a remediation plan within **14 days**.

We will credit reporters in the release notes unless you request otherwise.

## Scope

### In scope

- **Auth bypass** — accessing protected endpoints without a valid API key or
  with a key that grants higher privileges than assigned.
- **Token forgery** — crafting a valid feedback-page token without the secret.
- **PII leak** — reading another candidate's data, exposing PII in responses,
  logs, or errors.
- **Prompt injection** — a hostile resume causing the engine to produce
  feedback that references criteria not in the rubric, or to exfiltrate data.
- **SQL / path injection** — any injection leading to unintended data access
  or file disclosure.

### Out of scope

- Misconfiguration of self-hosted deployments (e.g., binding to 0.0.0.0
  without a firewall, not setting `RFE_API_KEYS`).
- Vulnerabilities in third-party LLM providers or SMTP infrastructure.
- Denial-of-service via resource exhaustion (no rate limiting in v0).
- Social-engineering attacks against deployment operators.

## Security Model Summary

**Rubric judges; AI scribes; humans approve.**

The engine processes candidate PII and produces legally sensitive output.
Key controls:

- **Encryption at rest** — candidate PII (`name`, `email`, `resume_text`,
  `salary_expectation`) is encrypted with a Fernet key (`RFE_ENCRYPTION_KEY`)
  before storage. Key never stored in DB or repo.
- **RBAC** — three roles (`admin`, `recruiter`, `viewer`) enforced by
  `RoleResolverMiddleware` on every non-public request; keys compared in
  constant time to prevent timing attacks.
- **Signed tokens** — feedback-page tokens are HMAC-signed with a server
  secret, scoped to one candidate, and carry a configurable TTL. Comparison
  uses `hmac.compare_digest`.
- **Audit log** — append-only log of every publish, approval, send, override,
  and deletion. Logged by entity ID only — no PII in audit records.
- **Prompt injection mitigations** — resume content is delimited and tagged as
  untrusted data in LLM prompts; all LLM output is schema-validated; feedback
  bullets referencing unknown criterion IDs are discarded before the approval
  queue.
- **No PII in logs** — the console deliverer and audit log emit entity IDs
  only; resume text and contact details are never logged.
- **TLS by default** — the reference `docker compose` deployment terminates
  TLS via a Caddy reverse proxy; the app container is not exposed directly.
