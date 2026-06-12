import os

import httpx

from rfe.adapters.delivery.console import ConsoleDeliverer
from rfe.adapters.delivery.smtp import SmtpConfig, SmtpDeliverer
from rfe.adapters.delivery.webhook import WebhookDeliverer
from rfe.adapters.llm.openai_compat import OpenAICompatProvider
from rfe.adapters.persistence.sqlite_repo import (SqliteRepository,
                                                  open_connection)
from rfe.api.app import build_app
from rfe.api.auth import api_keys_from_env
from rfe.domain.entities import (Candidate, Evaluation, Feedback, Role, Rubric)
from rfe.security.audit import AuditLog
from rfe.security.clock import SystemClock
from rfe.security.tokens import TokenSigner


def _select_deliverer():
    if os.environ.get("RFE_WEBHOOK_URL"):
        return WebhookDeliverer.from_env()
    if os.environ.get("RFE_SMTP_HOST"):
        return SmtpDeliverer(SmtpConfig.from_env())
    return ConsoleDeliverer()


provider = OpenAICompatProvider.from_env(
    base_url=os.environ.get("RFE_LLM_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.environ.get("RFE_LLM_API_KEY", ""),
    model=os.environ.get("RFE_LLM_MODEL", "llama3"),
)

_conn = open_connection()
repos = {
    "roles": SqliteRepository(_conn, Role, "roles"),
    "rubrics": SqliteRepository(_conn, Rubric, "rubrics"),
    "candidates": SqliteRepository(_conn, Candidate, "candidates"),
    "evaluations": SqliteRepository(_conn, Evaluation, "evaluations"),
    "feedbacks": SqliteRepository(_conn, Feedback, "feedbacks"),
}

clock = SystemClock()

app = build_app(
    model_provider=provider,
    deliverer=_select_deliverer(),
    repos=repos,
    audit=AuditLog.from_env(clock=clock),
    api_keys=api_keys_from_env(),
    token_signer=(TokenSigner.from_env(clock=clock)
                  if os.environ.get("RFE_TOKEN_SECRET") else None),
)
