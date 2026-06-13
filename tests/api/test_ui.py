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
    assert r.headers["cache-control"] == "no-store"


def test_unknown_static_is_404():
    assert client().get("/static/nope.txt").status_code == 404


def test_index_has_key_entry_and_views():
    body = client().get("/").text
    for marker in ('id="api-key"', 'id="view-roles"', 'id="view-rubric"',
                   'id="view-candidates"', 'id="view-evaluations"',
                   'id="view-feedback"', 'id="toast"',
                   'id="clear-local-drafts"',
                   'id="resume-file"', 'accept=".txt,.md,.pdf"',
                   'id="experience-min"', 'id="experience-max"',
                   'id="allowed-levels"', 'name="years_experience"',
                   'name="current_level"',
                   'id="evaluation-progress"', '<progress',
                   'src="/static/app.js?v=', 'href="/static/app.css?v='):
        assert marker in body, marker


def test_app_js_has_fetch_wrapper_and_handlers():
    js = client().get("/static/app.js").text
    for marker in ("X-API-Key", "localStorage", "function api",
                   "/roles", "/evaluate", "/feedback", "toast",
                   "401", "403", "409", "422"):
        assert marker in js, marker


def test_fetch_wrapper_shows_network_errors():
    js = client().get("/static/app.js").text
    for marker in ("catch (err)", "Network error", "throw err"):
        assert marker in js, marker


def test_app_js_persists_local_form_drafts():
    js = client().get("/static/app.js").text
    for marker in ("DRAFT_STORE", "saveDrafts", "restoreDrafts",
                   "clear-local-drafts", "localStorage.setItem(DRAFT_STORE",
                   "localStorage.removeItem(DRAFT_STORE", "activeView",
                   "rolesCache = await api(\"GET\", \"/roles\")"):
        assert marker in js, marker


def test_app_js_uses_form_elements_for_named_inputs():
    js = client().get("/static/app.js").text
    for marker in ('roleForm.elements["title"].value',
                   'candForm.elements["name"].value',
                   'f.elements["name"].value'):
        assert marker in js, marker
    assert "roleForm.title.value" not in js
    assert "candForm.name.value" not in js


def test_resume_file_picker_extracts_text_and_pdf():
    js = client().get("/static/app.js").text
    for marker in ("resume-file", "handleResumeFile", "readAsDataURL",
                   "readAsText", "/resume/extract", "resume_text.value"):
        assert marker in js, marker


def test_publish_rubric_sends_editor_payload():
    js = client().get("/static/app.js").text
    for marker in ("rubricPayload", "salary_band_min", "salary_band_max",
                   "experience_min_years", "experience_max_years",
                   "allowed_seniority_levels",
                   "const rubric = await api(\"POST\", `/roles/${roleId}/rubric/publish`, rubricPayload)",
                   "criteria = rubric.criteria.map", "renderCriteria()",
                   'document.getElementById("salary-min").value = rubric.salary_band_min ?? ""'):
        assert marker in js, marker


def test_candidate_form_sends_experience_and_level():
    js = client().get("/static/app.js").text
    for marker in ('candForm.elements["years_experience"].value',
                   'candForm.elements["current_level"].value',
                   "years_experience: years === \"\" ? null : parseFloat(years)",
                   "current_level: f.elements[\"current_level\"].value"):
        assert marker in js, marker


def test_evaluate_shows_evaluations_view():
    js = client().get("/static/app.js").text
    assert 'showView("evaluations")' in js


def test_evaluations_show_special_mismatch_states():
    js = client().get("/static/app.js").text
    for marker in ("salary_mismatch", "salary_band=mismatch",
                   "salary_band=ok", "salary_band=not_configured",
                   "experience_range=mismatch", "seniority_level=mismatch"):
        assert marker in js, marker


def test_evaluate_button_shows_pending_state():
    js = client().get("/static/app.js").text
    for marker in ('data-candidate-id="${esc(c.id)}"',
                   'data-role-id="${esc(c.role_id)}"',
                   'document.getElementById("candidate-list").onclick',
                   "setEvaluationProgress", "progress.hidden",
                   "Evaluating...", "Evaluation running...",
                   "button.disabled = true", "button.textContent"):
        assert marker in js, marker
    assert "onclick=\"evaluate(" not in js


def test_unpublished_rubric_evaluate_error_guides_to_rubric_editor():
    js = client().get("/static/app.js").text
    for marker in ('err.status === 422', 'button.dataset.roleId',
                   'showView("rubric")',
                   'loadRoleOptions("rubric-role", button.dataset.roleId)',
                   'Publish rubric for this role before evaluating'):
        assert marker in js, marker


def test_draft_buttons_show_pending_state():
    js = client().get("/static/app.js").text
    for marker in ('const draftButton = document.getElementById("draft-from-jd")',
                   'draftButton.disabled = true',
                   'draftButton.textContent = "Drafting..."',
                   'draftButton.textContent = "Draft from JD"',
                   "draftFeedback('${esc(ev.id)}', this)",
                   "async function draftFeedback(evaluationId, button)",
                   'button.textContent = "Drafting..."',
                   'button.textContent = oldText || "Draft feedback"'):
        assert marker in js, marker


def test_app_js_under_size_budget():
    js = client().get("/static/app.js").text
    assert js.count("\n") <= 450, "app.js must stay compact"
