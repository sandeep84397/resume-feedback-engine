"""Inbound adapter: serves the vanilla-JS single-page UI. No build step; the
SPA is three static files (index.html, app.css, app.js) talking to the REST
API with an X-API-Key from localStorage. GET / returns the shell; /static/*
serves assets. Path traversal is prevented by resolving within STATIC_DIR."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def build_ui_router() -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(
            (STATIC_DIR / "index.html").read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/static/{name}")
    def static_asset(name: str) -> FileResponse:
        target = (STATIC_DIR / name).resolve()
        if STATIC_DIR not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="not found")
        media = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        return FileResponse(target, media_type=media,
                            headers={"Cache-Control": "no-store"})

    return router
