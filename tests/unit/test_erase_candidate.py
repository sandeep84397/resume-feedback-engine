import pytest

from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.domain.entities import (Candidate, Evaluation, Feedback,
                                 FeedbackBullet)
from rfe.ports.repositories import NotFoundError
from rfe.usecases.erase_candidate import EraseCandidate, EraseReport


class _SpyAudit:
    def __init__(self):
        self.entries = []

    def record(self, action, entity_id):
        self.entries.append((action, entity_id))


def _seed():
    cands, evals, fbs = (InMemoryRepository(), InMemoryRepository(),
                         InMemoryRepository())
    cands.save(Candidate(id="c1", role_id="r", name="A", email="a@x.com",
                         resume_text="hi"))
    evals.save(Evaluation(id="e1", candidate_id="c1", rubric_id="ru"))
    fbs.save(Feedback(id="f1", evaluation_id="e1", candidate_id="c1", intro="i",
                      bullets=[FeedbackBullet(criterion_id="k", text="t")]))
    return cands, evals, fbs


def test_erase_cascades():
    cands, evals, fbs = _seed()
    uc = EraseCandidate(cands, evals, fbs, audit=_SpyAudit())
    report = uc.execute("c1")
    assert isinstance(report, EraseReport)
    assert report.evaluations_deleted == 1 and report.feedbacks_deleted == 1
    assert cands.list() == [] and evals.list() == [] and fbs.list() == []


def test_erase_audited_with_id_only():
    cands, evals, fbs = _seed()
    audit = _SpyAudit()
    EraseCandidate(cands, evals, fbs, audit=audit).execute("c1")
    assert ("erase", "c1") in audit.entries
    # no PII leaked into audit
    assert all("a@x.com" not in e[1] for e in audit.entries)


def test_erase_unknown_candidate_raises():
    cands, evals, fbs = _seed()
    with pytest.raises(NotFoundError):
        EraseCandidate(cands, evals, fbs, audit=_SpyAudit()).execute("nope")


def test_erase_without_audit_still_works():
    cands, evals, fbs = _seed()
    EraseCandidate(cands, evals, fbs, audit=None).execute("c1")
    assert cands.list() == []
