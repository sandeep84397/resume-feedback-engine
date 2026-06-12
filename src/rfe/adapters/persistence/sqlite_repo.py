"""SQLite persistence adapter implementing the Repository port.

Stdlib sqlite3 only (no ORM) — keeps deploy deps minimal. Each entity type
gets its own table with two columns: id TEXT PRIMARY KEY, payload TEXT
(the pydantic entity serialized via model_dump_json). One connection is
shared across repositories; identifier safety is enforced by validating
table names against a strict allowlist pattern.
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Generic, TypeVar

from pydantic import BaseModel

from rfe.ports.repositories import NotFoundError

E = TypeVar("E", bound=BaseModel)

DEFAULT_DB_PATH = "./rfe.db"
_TABLE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def db_path_from_env() -> str:
    return os.environ.get("RFE_DB_PATH", DEFAULT_DB_PATH)


def open_connection(path: str | None = None) -> sqlite3.Connection:
    """Open (and configure) a SQLite connection. Caller owns closing it."""
    conn = sqlite3.connect(path or db_path_from_env(), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class SqliteRepository(Generic[E]):
    """Repository port over a single SQLite table. Same surface as
    InMemoryRepository: save / get / list."""

    def __init__(self, conn: sqlite3.Connection, entity_type: type[E], table: str):
        if not _TABLE_NAME_RE.match(table):
            raise ValueError(f"unsafe table name: {table!r}")
        self._conn = conn
        self._type = entity_type
        self._table = table
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table} "
            "(id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        self._conn.commit()

    def save(self, entity: E) -> None:
        self._conn.execute(
            f"INSERT INTO {self._table} (id, payload) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
            (entity.id, entity.model_dump_json()),
        )
        self._conn.commit()

    def get(self, entity_id: str) -> E:
        row = self._conn.execute(
            f"SELECT payload FROM {self._table} WHERE id = ?", (entity_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(entity_id)
        return self._type.model_validate_json(row[0])

    def list(self) -> list[E]:
        rows = self._conn.execute(
            f"SELECT payload FROM {self._table}"
        ).fetchall()
        return [self._type.model_validate_json(r[0]) for r in rows]

    def delete(self, entity_id: str) -> None:
        self._conn.execute(
            f"DELETE FROM {self._table} WHERE id = ?", (entity_id,)
        )
        self._conn.commit()
