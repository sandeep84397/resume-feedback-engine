import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from rfe.ports.model_provider import ModelOutputError

T = TypeVar("T", bound=BaseModel)


class OpenAICompatProvider:
    """Adapter for any OpenAI-compatible chat API (OpenAI, Ollama, vLLM, ...).

    BYO-model: base_url + api_key come from host config; we never pay inference.
    """

    def __init__(self, client: httpx.Client, model: str):
        self._client = client
        self._model = model

    @classmethod
    def from_env(cls, base_url: str, api_key: str, model: str,
                 timeout_s: float = 60.0) -> "OpenAICompatProvider":
        client = httpx.Client(
            base_url=base_url, timeout=timeout_s,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
        return cls(client=client, model=model)

    def complete(self, system_prompt: str, user_content: str, schema: type[T]) -> T:
        instruction = (
            f"{system_prompt}\n\nRespond with ONLY a JSON object matching this "
            f"JSON schema:\n{json.dumps(schema.model_json_schema())}"
        )
        try:
            resp = self._client.post("/chat/completions", json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
            })
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ModelOutputError(f"LLM call failed: {exc}") from exc

        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            raise ModelOutputError(f"schema validation failed: {exc}") from exc
