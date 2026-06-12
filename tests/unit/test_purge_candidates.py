from datetime import datetime, timedelta, timezone

from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.domain.entities import (Candidate, Evaluation, Feedback,
                                 FeedbackBullet)
from rfe.security.clock import FixedClock
from rfe.usecases.purge_candidates import PurgeCandidates, PurgeReport

NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)


def _repos():
    return (InMemoryRepository(), InMemoryRepository(), InMemoryRepository())


def _cand(cid, age_days):
    return Candidate(id=cid, role_id="r", name="N", email="e@x.com",
                     resume_text="hi", created_at=NOW - timedelta(days=age_days))


def test_purges_candidate_older_than_retention():
    cands, evals, fbs = _repos()
    cands.save(_cand("old", 400))
    cands.save(_cand("new", 10))
    evals.save(Evaluation(id="e1", candidate_id="old", rubric_id="ru"))
    fbs.save(Feedback(id="f1", evaluation_id="e1", candidate_id="old",
                      intro="hi", bullets=[FeedbackBullet(criterion_id="k", text="t")]))
    uc = PurgeCandidates(cands, evals, fbs, FixedClock(NOW), retention_days=365)
    report = uc.execute()
    assert isinstance(report, PurgeReport)
    assert report.candidates_deleted == 1
    assert report.evaluations_deleted == 1
    assert report.feedbacks_deleted == 1
    assert [c.id for c in cands.list()] == ["new"]
    assert evals.list() == []
    assert fbs.list() == []


def test_disabled_when_retention_zero():
    cands, evals, fbs = _repos()
    cands.save(_cand("old", 9999))
    uc = PurgeCandidates(cands, evals, fbs, FixedClock(NOW), retention_days=0)
    report = uc.execute()
    assert report.candidates_deleted == 0
    assert len(cands.list()) == 1


def test_candidate_without_created_at_is_never_purged():
    cands, evals, fbs = _repos()
    cands.save(Candidate(id="legacy", role_id="r", name="N", email="e@x.com",
                         resume_text="hi", created_at=None))
    uc = PurgeCandidates(cands, evals, fbs, FixedClock(NOW), retention_days=365)
    assert uc.execute().candidates_deleted == 0
    assert len(cands.list()) == 1


def test_boundary_exactly_retention_days_not_purged():
    cands, evals, fbs = _repos()
    cands.save(_cand("edge", 365))   # exactly 365d old -> kept (strictly older purged)
    uc = PurgeCandidates(cands, evals, fbs, FixedClock(NOW), retention_days=365)
    assert uc.execute().candidates_deleted == 0
