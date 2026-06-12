"""Compute aggregate evaluation statistics for bias-audit support.

Purpose: supports external bias audits (e.g. NYC Local Law 144 and similar
automated-employment-decision-tool regulations). Returns aggregate counts and
rates only — no candidate PII. Auditors join these aggregates with their own
demographic data.

This is a pure function over the evaluations list; no I/O, no external deps.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rfe.domain.entities import Evaluation, EvaluationStatus
from rfe.domain.selection import PASS_SCORE


@dataclass
class CriterionStats:
    criterion_id: str
    evaluated: int = 0
    total_score: float = 0.0
    passed: int = 0

    @property
    def avg_score(self) -> float:
        return self.total_score / self.evaluated if self.evaluated else 0.0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.evaluated if self.evaluated else 0.0


@dataclass
class AggregateStats:
    evaluations: int = 0
    needs_human: int = 0
    salary_mismatch_count: int = 0
    criteria: dict[str, CriterionStats] = field(default_factory=dict)

    @property
    def salary_mismatch_rate(self) -> float:
        return self.salary_mismatch_count / self.evaluations if self.evaluations else 0.0


def compute_stats(evaluations: list[Evaluation]) -> AggregateStats:
    """Aggregate evaluation data for bias auditing.

    No PII is included in the result — only counts, sums, and rates.
    """
    stats = AggregateStats()

    for ev in evaluations:
        stats.evaluations += 1

        if ev.status == EvaluationStatus.NEEDS_HUMAN:
            stats.needs_human += 1

        if ev.salary_mismatch:
            stats.salary_mismatch_count += 1

        for score in ev.scores:
            cid = score.criterion_id
            if cid not in stats.criteria:
                stats.criteria[cid] = CriterionStats(criterion_id=cid)
            cs = stats.criteria[cid]
            cs.evaluated += 1
            cs.total_score += score.score
            if score.score >= PASS_SCORE:
                cs.passed += 1

    return stats
