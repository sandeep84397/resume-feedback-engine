import pytest
from pydantic import BaseModel

from rfe.adapters.llm.mock import MockModelProvider
from rfe.ports.model_provider import ModelOutputError


class Payload(BaseModel):
    answer: str


def test_mock_returns_queued_payloads_in_order():
    mock = MockModelProvider([Payload(answer="one"), Payload(answer="two")])
    assert mock.complete("sys", "user", Payload).answer == "one"
    assert mock.complete("sys", "user", Payload).answer == "two"


def test_mock_raises_queued_errors():
    mock = MockModelProvider([ModelOutputError("bad json"), Payload(answer="ok")])
    with pytest.raises(ModelOutputError):
        mock.complete("sys", "user", Payload)
    assert mock.complete("sys", "user", Payload).answer == "ok"


def test_mock_records_calls():
    mock = MockModelProvider([Payload(answer="one")])
    mock.complete("SYSTEM", "USER", Payload)
    assert mock.calls == [("SYSTEM", "USER", Payload)]
