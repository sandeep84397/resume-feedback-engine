import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rfe.api.auth import (
    ApiKeyAuthMiddleware,
    parse_api_keymap,
    parse_api_keys,
    role_for_key,
)


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


def test_parse_keymap_with_roles():
    m = parse_api_keymap("k1:admin, k2:recruiter ,k3:viewer")
    assert m == {"k1": "admin", "k2": "recruiter", "k3": "viewer"}


def test_bare_key_defaults_to_admin():
    assert parse_api_keymap("k1,k2:viewer") == {"k1": "admin", "k2": "viewer"}


def test_parse_keymap_empty():
    assert parse_api_keymap("") == {}


def test_parse_keymap_rejects_unknown_role():
    with pytest.raises(ValueError):
        parse_api_keymap("k1:wizard")


def test_role_for_key_constant_time_lookup():
    m = {"k1": "admin", "k2": "viewer"}
    assert role_for_key("k2", m) == "viewer"
    assert role_for_key("nope", m) is None
