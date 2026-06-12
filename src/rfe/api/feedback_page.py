"""Public read-only tokenized feedback page (GET /f/{token}).

Single page, no accounts, no scores. A bad, expired, or unknown token all
return 404 — indistinguishable, so there is no enumeration oracle.
"""
from __future__ import annotations

from html import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from rfe.ports.repositories import NotFoundError
from rfe.security.tokens import TokenError, TokenSigner


def _render_html(intro: str, bullets: list) -> str:
    items = "".join(f"<li>{escape(b.text)}</li>" for b in bullets)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Application feedback</title></head><body>"
        f"<p>{escape(intro)}</p><ul>{items}</ul>"
        "<p><small>This is an automated, one-way message.</small></p>"
        "</body></html>"
    )


def build_feedback_router(feedbacks_repo, signer: TokenSigner) -> APIRouter:
    router = APIRouter()

    @router.get("/f/{token}")
    def feedback_page(token: str, format: str = "json"):
        try:
            feedback_id = signer.verify(token)
            feedback = feedbacks_repo.get(feedback_id)
        except (TokenError, NotFoundError):
            raise HTTPException(status_code=404, detail="not found")

        if format == "html":
            return HTMLResponse(_render_html(feedback.intro, feedback.bullets))
        return JSONResponse({
            "intro": feedback.intro,
            "bullets": [{"criterion_id": b.criterion_id, "text": b.text}
                        for b in feedback.bullets],
        })

    return router
