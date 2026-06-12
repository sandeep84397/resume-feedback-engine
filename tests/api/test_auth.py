import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rfe.api.auth import ApiKeyAuthMiddleware, parse_api_keys


def build() -> TestClient:
    app = FastAPI()
    app.add_middleware(ApiKeyAuthMiddleware, api_keys={"key-a", "key-b"})

    @app.get("/protected")
    def protected():
        return {"ok": True}

    @app.get("/f/sometoken")
    def public():
        return {"public": True}

    return TestClient(app)


def test_parse_api_keys_splits_and_strips():
    assert parse_api_keys("a, b ,c") == {"a", "b", "c"}
    assert parse_api_keys("") == set()


def test_valid_key_allowed():
    client = build()
    r = client.get("/protected", headers={"X-API-Key": "key-a"})
    assert r.status_code == 200


def test_missing_key_is_401():
    assert build().get("/protected").status_code == 401


def test_wrong_key_is_401():
    assert build().get("/protected", headers={"X-API-Key": "nope"}).status_code == 401


def test_feedback_page_is_public():
    assert build().get("/f/sometoken").status_code == 200
