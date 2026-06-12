"""Adapter-layer decorator: transparent PII encryption for Candidate.

Wraps any Repository[Candidate] (in-memory or SQLite). On save, the four PII
fields (name, email, resume_text, salary_expectation) are replaced with Fernet
ciphertext before delegating; on get/list they are decrypted back. The domain
Candidate entity is unaware of ciphertext — encryption lives entirely here, at
the adapter boundary. Non-PII fields (id, role_id, created_at) stay plaintext
so retention/erasure can query by id and time without a key.
"""
from __future__ import annotations

from rfe.domain.entities import Candidate
from rfe.security.crypto import FieldCipher

# Encrypted at rest. name + email encrypt directly. salary_expectation is
# float|None (cannot hold ciphertext), so it is packed into the encrypted
# resume_text blob and nulled on disk; split back out on read.
_SALARY_SENTINEL = "__none__"
_SEP = "\x00"


class EncryptedCandidateRepository:
    """Same surface as Repository[Candidate]: save / get / list / delete."""

    def __init__(self, backing, cipher: FieldCipher):
        self._backing = backing
        self._cipher = cipher

    def save(self, candidate: Candidate) -> None:
        data = candidate.model_dump()
        data["name"] = self._cipher.encrypt(candidate.name)
        data["email"] = self._cipher.encrypt(candidate.email)
        salary = candidate.salary_expectation
        salary_repr = _SALARY_SENTINEL if salary is None else repr(salary)
        # pack resume + salary into one encrypted blob; salary column nulled
        data["resume_text"] = self._cipher.encrypt(
            candidate.resume_text + _SEP + salary_repr
        )
        data["salary_expectation"] = None
        self._backing.save(Candidate.model_validate(data))

    def _decrypt(self, c: Candidate) -> Candidate:
        data = c.model_dump()
        data["name"] = self._cipher.decrypt(data["name"])
        data["email"] = self._cipher.decrypt(data["email"])
        joined = self._cipher.decrypt(data["resume_text"])
        resume, _, raw_salary = joined.partition(_SEP)
        data["resume_text"] = resume
        data["salary_expectation"] = (
            None if raw_salary == _SALARY_SENTINEL else float(raw_salary)
        )
        return Candidate.model_validate(data)

    def get(self, candidate_id: str) -> Candidate:
        return self._decrypt(self._backing.get(candidate_id))

    def list(self) -> list[Candidate]:
        return [self._decrypt(c) for c in self._backing.list()]

    def delete(self, candidate_id: str) -> None:
        self._backing.delete(candidate_id)
