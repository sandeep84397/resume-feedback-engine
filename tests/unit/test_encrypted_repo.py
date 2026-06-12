from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from rfe.adapters.persistence.encrypted_repo import EncryptedCandidateRepository
from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.adapters.persistence.sqlite_repo import SqliteRepository, open_connection
from rfe.domain.entities import Candidate
from rfe.ports.repositories import NotFoundError
from rfe.security.crypto import FieldCipher


def cipher() -> FieldCipher:
    return FieldCipher(Fernet.generate_key())


def cand(**over) -> Candidate:
    base = dict(id="c1", role_id="r1", name="Alice", email="alice@x.com",
                resume_text="5 years python", salary_expectation=120000.0)
    base.update(over)
    return Candidate(**base)


def test_created_at_is_optional_and_defaults_none():
    c = Candidate(id="c", role_id="r", name="A", email="a@x.com",
                  resume_text="hi")
    assert c.created_at is None


def test_created_at_roundtrips_when_set():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    c = cand(created_at=ts)
    assert Candidate.model_validate_json(c.model_dump_json()).created_at == ts


def test_old_payload_without_created_at_still_loads():
    # a candidate JSON persisted before Phase 3 (no created_at key)
    legacy = '{"id":"c1","role_id":"r1","name":"A","email":"a@x.com",' \
             '"resume_text":"hi","salary_expectation":null}'
    c = Candidate.model_validate_json(legacy)
    assert c.created_at is None


def test_save_encrypts_pii_in_backing_store():
    backing = InMemoryRepository()
    repo = EncryptedCandidateRepository(backing, cipher())
    repo.save(cand())
    stored = backing.get("c1")           # raw row as the backing store holds it
    assert stored.name != "Alice"        # ciphertext, not plaintext
    assert stored.email != "alice@x.com"
    assert stored.resume_text != "5 years python"


def test_get_decrypts_back_to_plaintext():
    repo = EncryptedCandidateRepository(InMemoryRepository(), cipher())
    repo.save(cand())
    got = repo.get("c1")
    assert got.name == "Alice"
    assert got.email == "alice@x.com"
    assert got.resume_text == "5 years python"
    assert got.salary_expectation == 120000.0


def test_list_decrypts_all():
    repo = EncryptedCandidateRepository(InMemoryRepository(), cipher())
    repo.save(cand(id="c1"))
    repo.save(cand(id="c2", name="Bob"))
    names = sorted(c.name for c in repo.list())
    assert names == ["Alice", "Bob"]


def test_none_salary_is_preserved():
    repo = EncryptedCandidateRepository(InMemoryRepository(), cipher())
    repo.save(cand(salary_expectation=None))
    assert repo.get("c1").salary_expectation is None


def test_non_pii_fields_not_encrypted():
    backing = InMemoryRepository()
    repo = EncryptedCandidateRepository(backing, cipher())
    repo.save(cand(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    stored = backing.get("c1")
    assert stored.id == "c1"            # id/role_id/created_at stay plaintext
    assert stored.role_id == "r1"


def test_encryption_survives_sqlite_roundtrip(tmp_path):
    conn = open_connection(str(tmp_path / "enc.db"))
    backing = SqliteRepository(conn, Candidate, "candidates")
    repo = EncryptedCandidateRepository(backing, cipher())
    repo.save(cand())
    # row on disk is ciphertext
    raw = conn.execute("SELECT payload FROM candidates WHERE id='c1'").fetchone()[0]
    assert "alice@x.com" not in raw
    assert "5 years python" not in raw
    # but decorator decrypts on read
    assert repo.get("c1").email == "alice@x.com"
    conn.close()


def test_get_missing_raises_notfound():
    repo = EncryptedCandidateRepository(InMemoryRepository(), cipher())
    with pytest.raises(NotFoundError):
        repo.get("nope")
