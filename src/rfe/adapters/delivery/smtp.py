"""SMTP feedback deliverer (stdlib smtplib + email).

One-way, self-contained message: the body is the full criterion-based
feedback and never invites a reply (sent from a no-reply address).
Config from env. Tests inject a fake SMTP factory.
"""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable

from rfe.domain.entities import Candidate, Feedback


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        return cls(
            host=os.environ.get("RFE_SMTP_HOST", "localhost"),
            port=int(os.environ.get("RFE_SMTP_PORT", "587")),
            user=os.environ.get("RFE_SMTP_USER", ""),
            password=os.environ.get("RFE_SMTP_PASS", ""),
            from_addr=os.environ.get("RFE_SMTP_FROM", "no-reply@localhost"),
        )


SUBJECT = "Feedback on your application"
FOOTER = "This is an automated, one-way message; the inbox is not monitored."


def build_email_body(feedback: Feedback) -> str:
    lines = [feedback.intro, ""]
    for bullet in feedback.bullets:
        lines.append(f"- {bullet.text}")
    lines += ["", FOOTER]
    return "\n".join(lines)


class SmtpDeliverer:
    """FeedbackDeliverer over SMTP."""

    def __init__(self, config: SmtpConfig,
                 smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP):
        self._cfg = config
        self._smtp_factory = smtp_factory

    def deliver(self, candidate: Candidate, feedback: Feedback) -> None:
        msg = EmailMessage()
        msg["Subject"] = SUBJECT
        msg["From"] = self._cfg.from_addr
        msg["To"] = candidate.email
        msg.set_content(build_email_body(feedback))

        with self._smtp_factory(self._cfg.host, self._cfg.port,
                                timeout=self._cfg.timeout_s) as smtp:
            smtp.starttls()
            if self._cfg.user:
                smtp.login(self._cfg.user, self._cfg.password)
            smtp.send_message(msg)
