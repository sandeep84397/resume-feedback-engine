from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from rfe.adapters.delivery.console import ConsoleDeliverer
from rfe.adapters.persistence.memory import InMemoryRepository
from rfe.domain.entities import (Candidate, Evaluation, Feedback, Role, Rubric)
from rfe.domain.errors import DomainError, InvalidTransitionError
from rfe.ports.deliverer import FeedbackDeliverer
from rfe.ports.model_provider import ModelProvider
from rfe.ports.repositories import NotFoundError
from rfe.usecases.compose_feedback import ComposeFeedback
from rfe.usecases.deliver_feedback import DeliverFeedback
from rfe.usecases.draft_rubric import DraftRubric
from rfe.usecases.evaluate_candidate import EvaluateCandidate


class RoleIn(BaseModel):
    title: str
    description: str = ""


class CandidateIn(BaseModel):
    name: str
    email: str
    resume_text: str
    salary_expectation: float | None = None


def build_app(model_provider: ModelProvider,
              deliverer: FeedbackDeliverer | None = None) -> FastAPI:
    app = FastAPI(title="Rejection Feedback Engine")

    roles: InMemoryRepository[Role] = InMemoryRepository()
    rubrics: InMemoryRepository[Rubric] = InMemoryRepository()
    candidates: InMemoryRepository[Candidate] = InMemoryRepository()
    evaluations: InMemoryRepository[Evaluation] = InMemoryRepository()
    feedbacks: InMemoryRepository[Feedback] = InMemoryRepository()

    draft_rubric = DraftRubric(model_provider)
    evaluate = EvaluateCandidate(model_provider)
    compose = ComposeFeedback(model_provider)
    deliver = DeliverFeedback(deliverer or ConsoleDeliverer())

    def rubric_for_role(role_id: str) -> Rubric:
        for r in rubrics.list():
            if r.role_id == role_id:
                return r
        raise NotFoundError(f"rubric for role {role_id}")

    @app.exception_handler(NotFoundError)
    async def not_found(_, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransitionError)
    async def bad_transition(_, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_error(_, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.post("/roles")
    def create_role(body: RoleIn) -> Role:
        role = Role(id=str(uuid4()), title=body.title, description=body.description)
        roles.save(role)
        return role

    @app.post("/roles/{role_id}/rubric/draft")
    def draft(role_id: str) -> Rubric:
        rubric = draft_rubric.execute(roles.get(role_id), rubric_id=str(uuid4()))
        rubrics.save(rubric)
        return rubric

    @app.post("/roles/{role_id}/rubric/publish")
    def publish(role_id: str) -> Rubric:
        roles.get(role_id)
        rubric = rubric_for_role(role_id)
        rubric.publish()
        rubrics.save(rubric)
        return rubric

    @app.post("/roles/{role_id}/candidates")
    def add_candidate(role_id: str, body: CandidateIn) -> Candidate:
        roles.get(role_id)
        cand = Candidate(id=str(uuid4()), role_id=role_id, **body.model_dump())
        candidates.save(cand)
        return cand

    @app.post("/candidates/{candidate_id}/evaluate")
    def evaluate_candidate(candidate_id: str) -> Evaluation:
        cand = candidates.get(candidate_id)
        ev = evaluate.execute(cand, rubric_for_role(cand.role_id),
                              evaluation_id=str(uuid4()))
        evaluations.save(ev)
        return ev

    @app.post("/evaluations/{evaluation_id}/feedback/draft")
    def draft_feedback(evaluation_id: str) -> Feedback:
        ev = evaluations.get(evaluation_id)
        cand = candidates.get(ev.candidate_id)
        fb = compose.execute(cand, rubrics.get(ev.rubric_id), ev,
                             feedback_id=str(uuid4()))
        feedbacks.save(fb)
        return fb

    @app.post("/feedback/{feedback_id}/approve")
    def approve_feedback(feedback_id: str) -> Feedback:
        fb = feedbacks.get(feedback_id)
        fb.approve()
        feedbacks.save(fb)
        return fb

    @app.post("/feedback/{feedback_id}/send")
    def send_feedback(feedback_id: str) -> Feedback:
        fb = feedbacks.get(feedback_id)
        deliver.execute(candidates.get(fb.candidate_id), fb)
        feedbacks.save(fb)
        return fb

    return app
