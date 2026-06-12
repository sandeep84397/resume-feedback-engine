from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelOutputError(Exception):
    """The model returned output that failed schema validation."""


class ModelProvider(Protocol):
    def complete(self, system_prompt: str, user_content: str, schema: type[T]) -> T:
        """Run the model and return output validated against `schema`.

        Raises ModelOutputError if the output cannot be validated.
        """
        ...
