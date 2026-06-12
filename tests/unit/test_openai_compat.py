import json

import httpx
import pytest
from pydantic import BaseModel

from rfe.adapters.llm.openai_compat import OpenAICompatProvider
from rfe.ports.model_provider import ModelOutputError


class Payload(BaseModel):
    answer: str


def make_provider(handler) -> OpenAICompatProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://llm.local/v1")
    return OpenAICompatProvider(client=client, model="llama3")


def ok_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}}]
    })


def test_parses_valid_json_content():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "llama3"
        assert body["messages"][0]["role"] == "system"
        return ok_response('{"answer": "hi"}')

    result = make_provider(handler).complete("sys", "user", Payload)
    assert result.answer == "hi"


def test_invalid_json_raises_model_output_error():
    provider = make_provider(lambda r: ok_response("not json at all"))
    with pytest.raises(ModelOutputError):
        provider.complete("sys", "user", Payload)


def test_http_error_raises_model_output_error():
    provider = make_provider(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(ModelOutputError):
        provider.complete("sys", "user", Payload)
