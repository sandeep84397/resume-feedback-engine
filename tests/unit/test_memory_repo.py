import pytest

from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.domain.entities import Role
from rfe.ports.repositories import NotFoundError


def test_save_and_get_roundtrip():
    repo: InMemoryRepository[Role] = InMemoryRepository()
    repo.save(Role(id="role1", title="SRE"))
    assert repo.get("role1").title == "SRE"


def test_get_missing_raises():
    repo: InMemoryRepository[Role] = InMemoryRepository()
    with pytest.raises(NotFoundError):
        repo.get("nope")


def test_delete_removes_entity():
    repo: InMemoryRepository[Role] = InMemoryRepository()
    repo.save(Role(id="r1", title="SRE"))
    repo.delete("r1")
    assert repo.list() == []


def test_delete_missing_is_noop():
    repo: InMemoryRepository[Role] = InMemoryRepository()
    repo.delete("nope")  # should not raise
