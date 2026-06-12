from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from rfe.api.rbac import RoleResolverMiddleware, require_role


def build(keymap):
    app = FastAPI()
    app.add_middleware(RoleResolverMiddleware, keymap=keymap)

    @app.get("/read")
    def read():
        return {"ok": True}

    @app.post("/write", dependencies=[Depends(require_role("recruiter"))])
    def write():
        return {"ok": True}

    @app.delete("/danger", dependencies=[Depends(require_role("admin"))])
    def danger():
        return {"ok": True}

    return TestClient(app)


KEYMAP = {"ak": "admin", "rk": "recruiter", "vk": "viewer"}


def test_viewer_can_read():
    assert build(KEYMAP).get("/read", headers={"X-API-Key": "vk"}).status_code == 200


def test_viewer_cannot_write():
    assert build(KEYMAP).post("/write", headers={"X-API-Key": "vk"}).status_code == 403


def test_recruiter_can_write():
    assert build(KEYMAP).post("/write", headers={"X-API-Key": "rk"}).status_code == 200


def test_recruiter_cannot_delete():
    assert build(KEYMAP).delete("/danger", headers={"X-API-Key": "rk"}).status_code == 403


def test_admin_can_delete():
    assert build(KEYMAP).delete("/danger", headers={"X-API-Key": "ak"}).status_code == 200


def test_missing_key_is_401():
    assert build(KEYMAP).get("/read").status_code == 401


def test_bad_key_is_401():
    assert build(KEYMAP).get("/read", headers={"X-API-Key": "nope"}).status_code == 401


def test_public_feedback_path_skips_auth():
    app = FastAPI()
    app.add_middleware(RoleResolverMiddleware, keymap=KEYMAP)

    @app.get("/f/tok")
    def pub():
        return {"public": True}

    assert TestClient(app).get("/f/tok").status_code == 200
