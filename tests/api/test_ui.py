from fastapi import FastAPI
from fastapi.testclient import TestClient

from rfe.api.ui import build_ui_router


def client():
    app = FastAPI()
    app.include_router(build_ui_router())
    return TestClient(app)


def test_root_serves_html():
    r = client().get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<html" in r.text.lower()


def test_static_css_served_with_type():
    r = client().get("/static/app.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]


def test_static_js_served_with_type():
    r = client().get("/static/app.js")
    assert r.status_code == 200
    ctype = r.headers["content-type"]
    assert "javascript" in ctype


def test_unknown_static_is_404():
    assert client().get("/static/nope.txt").status_code == 404
