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


def test_index_has_key_entry_and_views():
    body = client().get("/").text
    for marker in ('id="api-key"', 'id="view-roles"', 'id="view-rubric"',
                   'id="view-candidates"', 'id="view-evaluations"',
                   'id="view-feedback"', 'id="toast"',
                   'src="/static/app.js"', 'href="/static/app.css"'):
        assert marker in body, marker


def test_app_js_has_fetch_wrapper_and_handlers():
    js = client().get("/static/app.js").text
    for marker in ("X-API-Key", "localStorage", "function api",
                   "/roles", "/evaluate", "/feedback", "toast",
                   "401", "403", "409", "422"):
        assert marker in js, marker


def test_app_js_under_size_budget():
    js = client().get("/static/app.js").text
    assert js.count("\n") <= 400, "app.js must stay under ~400 lines"
