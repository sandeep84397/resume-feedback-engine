from pydantic import BaseModel

from rfe.ports.model_provider import ModelOutputError


class MockModelProvider:
    """Test double: returns queued payloads (or raises queued exceptions) in order."""

    def __init__(self, responses: list[BaseModel | Exception]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    def complete(self, system_prompt: str, user_content: str, schema: type):
        self.calls.append((system_prompt, user_content, schema))
        if not self._responses:
            raise ModelOutputError("mock response queue exhausted")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
