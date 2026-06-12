"""Append-only JSONL audit log.

One JSON object per line: {action, entity_id, timestamp}. No PII — only the
action verb and an opaque entity id. Timestamp from an injected Clock.
"""
from __future__ import annotations

import json
import os

from rfe.security.clock import Clock, SystemClock


class AuditLog:
    def __init__(self, path: str, clock: Clock):
        self._path = path
        self._clock = clock

    @classmethod
    def from_env(cls, clock: Clock | None = None) -> "AuditLog":
        path = os.environ.get("RFE_AUDIT_LOG", "./audit.jsonl")
        return cls(path=path, clock=clock or SystemClock())

    def record(self, action: str, entity_id: str) -> None:
        entry = {
            "action": action,
            "entity_id": entity_id,
            "timestamp": self._clock.now().isoformat(),
        }
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
