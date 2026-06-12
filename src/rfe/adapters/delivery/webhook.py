"""Signed outbound webhook deliverer.

POSTs criterion-linked feedback JSON to the host's configured receiver with
an HMAC-SHA256 signature header (X-RFE-Signature) over the raw body so the
receiver can verify origin. Injected httpx.Client for testability.
"""
from __future__ import annotations

import hashlib
import hmac
import os

import httpx

from rfe.domain.entities import Candidate, Feedback

SIGNATURE_HEADER = "X-RFE-Signature"


class WebhookDeliverer:
    """FeedbackDeliverer over a signed HTTP webhook."""

    def __init__(self, client: httpx.Client, url: str, secret: str):
        self._client = client
        self._url = url
        self._secret = secret.encode("utf-8")

    @classmethod
    def from_env(cls, timeout_s: float = 30.0) -> "WebhookDeliverer":
        url = os.environ["RFE_WEBHOOK_URL"]
        secret = os.environ.get("RFE_WEBHOOK_SECRET", "")
        return cls(client=httpx.Client(timeout=timeout_s), url=url, secret=secret)

    def deliver(self, candidate: Candidate, feedback: Feedback) -> None:
        payload = {
            "feedback_id": feedback.id,
            "candidate_id": candidate.id,
            "intro": feedback.intro,
            "bullets": [{"criterion_id": b.criterion_id, "text": b.text}
                        for b in feedback.bullets],
        }
        body = httpx.Request("POST", self._url, json=payload).content
        sig = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        resp = self._client.post(
            self._url, content=body,
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
        )
        resp.raise_for_status()
