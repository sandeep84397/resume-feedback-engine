import base64
import binascii
from io import BytesIO
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from pydantic import BaseModel, Field

from rfe.adapters.delivery.console import ConsoleDeliverer
from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.api.feedback_page import build_feedback_router
from rfe.api.rbac import RoleResolverMiddleware, require_role
from rfe.api.ui import build_ui_router
from rfe.domain.entities import (Candidate, Criterion, Evaluation, Feedback,
                                 Role, Rubric, normalize_seniority_level)
from rfe.domain.errors import DomainError, InvalidTransitionError
from rfe.ports.deliverer import FeedbackDeliverer
from rfe.ports.model_provider import ModelOutputError, ModelProvider
from rfe.ports.repositories import NotFoundError
from rfe.security.audit import AuditLog
from rfe.security.clock import Clock, SystemClock
from rfe.security.tokens import TokenSigner
from rfe.usecases.compose_feedback import ComposeFeedback
from rfe.usecases.deliver_feedback import DeliverFeedback
from rfe.usecases.draft_rubric import DraftRubric
from rfe.usecases.erase_candidate import EraseCandidate
from rfe.usecases.evaluate_candidate import EvaluateCandidate
from rfe.usecases.compute_stats import compute_stats
from rfe.usecases.purge_candidates import PurgeCandidates


class RoleIn(BaseModel):
    title: str
    description: str = ""


class CandidateIn(BaseModel):
    name: str
    email: str
    resume_text: str
    salary_expectation: float | None = None
    years_experience: float | None = None
    current_level: str | None = None


class RubricPublishIn(BaseModel):
    criteria: list[Criterion]
    salary_band_min: float | None = None
    salary_band_max: float | None = None
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    allowed_seniority_levels: list[str] = Field(default_factory=list)


class ResumeExtractIn(BaseModel):
    filename: str
    content_base64: str


class ResumeExtractOut(BaseModel):
    text: str


_MAX_RESUME_BYTES = 2_000_000


def build_app(model_provider: ModelProvider,
              deliverer: FeedbackDeliverer | None = None,
              repos: dict | None = None,
              audit: AuditLog | None = None,
              api_keys: set[str] | dict[str, str] | None = None,
              token_signer: TokenSigner | None = None,
              clock: Clock | None = None,
              serve_ui: bool = False,
              retention_days: int = 365) -> FastAPI:
    app = FastAPI(title="Rejection Feedback Engine")

    repos = repos or {}
    roles = repos.get("roles") or InMemoryRepository()
    rubrics = repos.get("rubrics") or InMemoryRepository()
    candidates = repos.get("candidates") or InMemoryRepository()
    evaluations = repos.get("evaluations") or InMemoryRepository()
    feedbacks = repos.get("feedbacks") or InMemoryRepository()

    _clock = clock or SystemClock()

    draft_rubric = DraftRubric(model_provider)
    evaluate = EvaluateCandidate(model_provider)
    compose = ComposeFeedback(model_provider)
    deliver = DeliverFeedback(deliverer or ConsoleDeliverer())

    def _audit(action: str, entity_id: str) -> None:
        if audit is not None:
            audit.record(action, entity_id)

    def rubric_for_role(role_id: str) -> Rubric:
        matches = [r for r in rubrics.list() if r.role_id == role_id]
        if not matches:
            raise NotFoundError(f"rubric for role {role_id}")
        return max(matches, key=lambda r: r.version)

    @app.exception_handler(NotFoundError)
    async def not_found(_, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransitionError)
    async def bad_transition(_, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_error(_, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ModelOutputError)
    async def model_output_error(_, exc):
        return JSONResponse(status_code=503, content={
            "detail": "the LLM returned invalid output after retry; "
                      "try again or check the configured model"})

    # RBAC: only add role guards when api_keys are configured.
    # When api_keys is None/empty, RBAC is disabled — all routes are open.
    _viewer_guard = ([Depends(require_role("viewer"))] if api_keys else [])
    _recruiter_guard = ([Depends(require_role("recruiter"))] if api_keys else [])
    _admin_guard = ([Depends(require_role("admin"))] if api_keys else [])

    @app.get("/roles", dependencies=_viewer_guard)
    def list_roles() -> list[Role]:
        return roles.list()

    @app.post("/roles", dependencies=_recruiter_guard)
    def create_role(body: RoleIn) -> Role:
        role = Role(id=str(uuid4()), title=body.title, description=body.description)
        roles.save(role)
        return role

    @app.post("/roles/{role_id}/rubric/draft", dependencies=_recruiter_guard)
    def draft(role_id: str) -> Rubric:
        rubric = draft_rubric.execute(roles.get(role_id), rubric_id=str(uuid4()))
        rubrics.save(rubric)
        return rubric

    @app.post("/roles/{role_id}/rubric/publish", dependencies=_recruiter_guard)
    def publish(role_id: str, body: RubricPublishIn | None = None) -> Rubric:
        roles.get(role_id)
        if body is None:
            rubric = rubric_for_role(role_id)
        else:
            criteria = body.criteria
            allowed_levels = [
                n for item in body.allowed_seniority_levels
                if (n := normalize_seniority_level(item))
            ]
            try:
                existing = rubric_for_role(role_id)
                if not criteria:
                    criteria = list(existing.criteria)
                if existing.published:
                    unchanged = (
                        list(existing.criteria) == criteria
                        and existing.salary_band_min == body.salary_band_min
                        and existing.salary_band_max == body.salary_band_max
                        and existing.experience_min_years == body.experience_min_years
                        and existing.experience_max_years == body.experience_max_years
                        and existing.allowed_seniority_levels == allowed_levels
                    )
                    if unchanged:
                        return existing
                    rubric_id = str(uuid4())
                    version = existing.version + 1
                else:
                    rubric_id = existing.id
                    version = existing.version
            except NotFoundError:
                rubric_id = str(uuid4())
                version = 1
            rubric = Rubric(
                id=rubric_id,
                role_id=role_id,
                version=version,
                criteria=criteria,
                salary_band_min=body.salary_band_min,
                salary_band_max=body.salary_band_max,
                experience_min_years=body.experience_min_years,
                experience_max_years=body.experience_max_years,
                allowed_seniority_levels=allowed_levels,
            )
        rubric.publish()
        rubrics.save(rubric)
        _audit("publish", rubric.id)
        return rubric

    @app.post("/roles/{role_id}/candidates", dependencies=_recruiter_guard)
    def add_candidate(role_id: str, body: CandidateIn) -> Candidate:
        roles.get(role_id)
        cand = Candidate(id=str(uuid4()), role_id=role_id,
                         created_at=_clock.now(), **body.model_dump())
        candidates.save(cand)
        return cand

    @app.post("/resume/extract", dependencies=_recruiter_guard)
    def extract_resume(body: ResumeExtractIn) -> ResumeExtractOut:
        suffix = body.filename.lower().rsplit(".", 1)[-1]
        if suffix not in {"pdf", "txt", "md"}:
            raise DomainError("resume file must be .txt, .md, or .pdf")
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise DomainError("resume file content is not valid base64") from exc
        if len(data) > _MAX_RESUME_BYTES:
            raise DomainError("resume file must be 2 MB or smaller")
        if suffix in {"txt", "md"}:
            return ResumeExtractOut(text=data.decode("utf-8", errors="replace"))
        try:
            reader = PdfReader(BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise DomainError("could not extract text from PDF resume") from exc
        if not text.strip():
            raise DomainError("PDF resume did not contain extractable text")
        return ResumeExtractOut(text=text)

    @app.post("/candidates/{candidate_id}/evaluate", dependencies=_recruiter_guard)
    def evaluate_candidate(candidate_id: str) -> Evaluation:
        cand = candidates.get(candidate_id)
        ev = evaluate.execute(cand, rubric_for_role(cand.role_id),
                              evaluation_id=str(uuid4()))
        evaluations.save(ev)
        return ev

    @app.post("/evaluations/{evaluation_id}/feedback/draft",
              dependencies=_recruiter_guard)
    def draft_feedback(evaluation_id: str) -> Feedback:
        ev = evaluations.get(evaluation_id)
        cand = candidates.get(ev.candidate_id)
        fb = compose.execute(cand, rubrics.get(ev.rubric_id), ev,
                             feedback_id=str(uuid4()))
        feedbacks.save(fb)
        return fb

    @app.post("/feedback/{feedback_id}/approve", dependencies=_recruiter_guard)
    def approve_feedback(feedback_id: str) -> Feedback:
        fb = feedbacks.get(feedback_id)
        fb.approve()
        feedbacks.save(fb)
        _audit("approve", fb.id)
        return fb

    @app.post("/feedback/{feedback_id}/send", dependencies=_recruiter_guard)
    def send_feedback(feedback_id: str) -> Feedback:
        fb = feedbacks.get(feedback_id)
        deliver.execute(candidates.get(fb.candidate_id), fb)
        feedbacks.save(fb)
        _audit("send", fb.id)
        return fb

    @app.delete("/candidates/{candidate_id}", dependencies=_admin_guard)
    def erase_candidate_route(candidate_id: str):
        EraseCandidate(candidates, evaluations, feedbacks, audit=audit
                       ).execute(candidate_id)
        return {"erased": candidate_id}

    @app.post("/admin/purge", dependencies=_admin_guard)
    def purge():
        report = PurgeCandidates(candidates, evaluations, feedbacks, _clock,
                                 retention_days=retention_days).execute()
        return {
            "candidates_deleted": report.candidates_deleted,
            "evaluations_deleted": report.evaluations_deleted,
            "feedbacks_deleted": report.feedbacks_deleted,
        }

    @app.get("/admin/stats", dependencies=_admin_guard)
    def admin_stats():
        # Supports external bias audits (e.g. NYC LL144): returns aggregate
        # counts and rates only. Contains NO candidate PII. Auditors join
        # these aggregates with their own demographic data to assess disparate
        # impact. The engine stores no demographic data.
        stats = compute_stats(evaluations.list())
        return {
            "evaluations": stats.evaluations,
            "needs_human": stats.needs_human,
            "salary_mismatch_rate": stats.salary_mismatch_rate,
            "criteria": [
                {
                    "criterion_id": cs.criterion_id,
                    "evaluated": cs.evaluated,
                    "avg_score": cs.avg_score,
                    "pass_rate": cs.pass_rate,
                }
                for cs in stats.criteria.values()
            ],
        }

    if serve_ui:
        app.include_router(build_ui_router())

    if token_signer is not None:
        app.include_router(build_feedback_router(feedbacks, token_signer))

    if api_keys:
        # set -> every key is admin (Phase 2 compat); dict -> key:role map
        keymap = ({k: "admin" for k in api_keys} if isinstance(api_keys, set)
                  else dict(api_keys))
        app.add_middleware(RoleResolverMiddleware, keymap=keymap)

    return app
