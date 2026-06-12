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
