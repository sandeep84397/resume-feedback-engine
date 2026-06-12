"""Retention purge use-case. Deletes candidates whose created_at is strictly
older than `retention_days`, cascading their evaluations and feedback. Pure:
depends only on the Repository port (save/list/delete) + an injected Clock.
retention_days=0 disables purge entirely. Candidates with created_at=None are
never purged (we cannot prove their age, so we keep them — fail safe)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from rfe.security.clock import Clock


@dataclass(frozen=True)
class PurgeReport:
    candidates_deleted: int
    evaluations_deleted: int
    feedbacks_deleted: int


class PurgeCandidates:
    def __init__(self, candidates, evaluations, feedbacks, clock: Clock,
                 retention_days: int = 365):
        self._candidates = candidates
        self._evaluations = evaluations
        self._feedbacks = feedbacks
        self._clock = clock
        self._retention_days = retention_days

    def execute(self) -> PurgeReport:
        if self._retention_days <= 0:
            return PurgeReport(0, 0, 0)
        cutoff = self._clock.now() - timedelta(days=self._retention_days)
        stale = [c for c in self._candidates.list()
                 if c.created_at is not None and c.created_at < cutoff]
        cand_n = eval_n = fb_n = 0
        for cand in stale:
            ev_ids = [e.id for e in self._evaluations.list()
                      if e.candidate_id == cand.id]
            for fb in [f for f in self._feedbacks.list()
                       if f.candidate_id == cand.id]:
                self._feedbacks.delete(fb.id)
                fb_n += 1
            for ev_id in ev_ids:
                self._evaluations.delete(ev_id)
                eval_n += 1
            self._candidates.delete(cand.id)
            cand_n += 1
        return PurgeReport(cand_n, eval_n, fb_n)
