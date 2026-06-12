"""Right-to-erasure use-case (GDPR/DSAR). Cascade-deletes a candidate plus
their evaluations and feedback. Audit-logged with the candidate id only — no
PII (matches AuditLog.record(action, entity_id)). Raises NotFoundError if the
candidate does not exist."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EraseReport:
    candidate_id: str
    evaluations_deleted: int
    feedbacks_deleted: int


class EraseCandidate:
    def __init__(self, candidates, evaluations, feedbacks, audit=None):
        self._candidates = candidates
        self._evaluations = evaluations
        self._feedbacks = feedbacks
        self._audit = audit

    def execute(self, candidate_id: str) -> EraseReport:
        self._candidates.get(candidate_id)   # raises NotFoundError if absent
        fb_ids = [f.id for f in self._feedbacks.list()
                  if f.candidate_id == candidate_id]
        ev_ids = [e.id for e in self._evaluations.list()
                  if e.candidate_id == candidate_id]
        for fid in fb_ids:
            self._feedbacks.delete(fid)
        for eid in ev_ids:
            self._evaluations.delete(eid)
        self._candidates.delete(candidate_id)
        if self._audit is not None:
            self._audit.record("erase", candidate_id)
        return EraseReport(candidate_id, len(ev_ids), len(fb_ids))
