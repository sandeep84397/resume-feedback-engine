from typing import Protocol, TypeVar

from pydantic import BaseModel

E = TypeVar("E", bound=BaseModel)


class NotFoundError(Exception):
    """Entity not found in repository."""


class Repository(Protocol[E]):
    def save(self, entity: E) -> None: ...

    def get(self, entity_id: str) -> E:
        """Raises NotFoundError if absent."""
        ...
