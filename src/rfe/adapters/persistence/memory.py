from typing import Generic, TypeVar

from pydantic import BaseModel

from rfe.ports.repositories import NotFoundError

E = TypeVar("E", bound=BaseModel)


class InMemoryRepository(Generic[E]):
    """Phase 1 persistence. SQLite adapter replaces this in Phase 2."""

    def __init__(self):
        self._items: dict[str, E] = {}

    def save(self, entity: E) -> None:
        self._items[entity.id] = entity

    def get(self, entity_id: str) -> E:
        try:
            return self._items[entity_id]
        except KeyError:
            raise NotFoundError(entity_id) from None

    def list(self) -> list[E]:
        return list(self._items.values())

    def delete(self, entity_id: str) -> None:
        self._items.pop(entity_id, None)
