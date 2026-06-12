import pytest

from rfe.adapters.persistence.sqlite_repo import SqliteRepository, open_connection
from rfe.domain.entities import (Candidate, Criterion, CriterionType,
                                 Feedback, FeedbackBullet, Role, Rubric)
from rfe.ports.repositories import NotFoundError


@pytest.fixture
def conn(tmp_path):
    c = open_connection(str(tmp_path / "test.db"))
    yield c
    c.close()


def test_save_and_get_roundtrip(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    repo.save(Role(id="role1", title="SRE", description="5y K8s"))
    loaded = repo.get("role1")
    assert loaded.title == "SRE"
    assert loaded.description == "5y K8s"
    assert isinstance(loaded, Role)


def test_get_missing_raises(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    with pytest.raises(NotFoundError):
        repo.get("nope")


def test_save_is_upsert(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    repo.save(Role(id="role1", title="SRE"))
    repo.save(Role(id="role1", title="Senior SRE"))
    assert repo.get("role1").title == "Senior SRE"
    assert len(repo.list()) == 1


def test_list_returns_all(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    repo.save(Role(id="r1", title="A"))
    repo.save(Role(id="r2", title="B"))
    titles = sorted(r.title for r in repo.list())
    assert titles == ["A", "B"]


def test_list_empty(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    assert repo.list() == []


def test_separate_tables_are_isolated(conn):
    roles: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    cands: SqliteRepository[Candidate] = SqliteRepository(conn, Candidate, "candidates")
    roles.save(Role(id="x", title="A"))
    cands.save(Candidate(id="x", role_id="x", name="N", email="n@x.com",
                         resume_text="resume body"))
    assert roles.get("x").title == "A"
    assert cands.get("x").email == "n@x.com"
    assert len(roles.list()) == 1
    assert len(cands.list()) == 1


def test_published_rubric_roundtrips(conn):
    repo: SqliteRepository[Rubric] = SqliteRepository(conn, Rubric, "rubrics")
    r = Rubric(id="r1", role_id="role1", criteria=[
        Criterion(id="k8s", name="Kubernetes", type=CriterionType.MUST_HAVE),
    ])
    r.publish()
    repo.save(r)
    loaded = repo.get("r1")
    assert loaded.published is True
    assert loaded.criteria[0].id == "k8s"


def test_feedback_roundtrips_with_bullets(conn):
    repo: SqliteRepository[Feedback] = SqliteRepository(conn, Feedback, "feedbacks")
    fb = Feedback(id="f1", evaluation_id="e1", candidate_id="c1", intro="Hi",
                  bullets=[FeedbackBullet(criterion_id="k8s", text="...")])
    repo.save(fb)
    loaded = repo.get("f1")
    assert loaded.intro == "Hi"
    assert loaded.bullets[0].criterion_id == "k8s"


def test_delete_removes_entity(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    repo.save(Role(id="r1", title="SRE"))
    repo.delete("r1")
    assert repo.list() == []


def test_delete_missing_is_noop(conn):
    repo: SqliteRepository[Role] = SqliteRepository(conn, Role, "roles")
    repo.delete("nope")  # should not raise


def test_persists_across_repo_instances(tmp_path):
    path = str(tmp_path / "persist.db")
    c1 = open_connection(path)
    SqliteRepository(c1, Role, "roles").save(Role(id="r1", title="Persisted"))
    c1.close()
    c2 = open_connection(path)
    assert SqliteRepository(c2, Role, "roles").get("r1").title == "Persisted"
    c2.close()
