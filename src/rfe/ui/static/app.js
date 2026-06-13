"use strict";

const KEY_STORE = "rfe_api_key";
const DRAFT_STORE = "rfe_local_drafts";
let apiKey = localStorage.getItem(KEY_STORE) || "";
let criteria = [];   // working rubric criteria in the editor
let activeView = "roles";

// ---- toast ------------------------------------------------------------
const toastEl = document.getElementById("toast");
function toast(msg, ok = false) {
  toastEl.textContent = msg;
  toastEl.classList.toggle("ok", ok);
  toastEl.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { toastEl.hidden = true; }, 3500);
}

// ---- fetch wrapper ----------------------------------------------------
async function api(method, path, body) {
  const opts = { method, headers: { "X-API-Key": apiKey } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (err) {
    toast("Network error — is the server running?");
    throw err;
  }
  if (res.status === 401) { toast("401 — invalid or missing API key"); throw res; }
  if (res.status === 403) { toast("403 — your role cannot do that"); throw res; }
  if (res.status === 409) { toast("409 — invalid state transition"); throw res; }
  if (res.status === 422) {
    const d = await res.json().catch(() => ({}));
    toast("422 — " + (d.detail || "validation error")); throw res;
  }
  if (!res.ok) { toast(res.status + " — request failed"); throw res; }
  return res.status === 204 ? null : res.json();
}

// ---- local drafts -----------------------------------------------------
function getDrafts() {
  try { return JSON.parse(localStorage.getItem(DRAFT_STORE) || "{}"); }
  catch (_) { return {}; }
}

function saveDrafts() {
  const roleForm = document.getElementById("role-form");
  const candForm = document.getElementById("candidate-form");
  const draft = {
    activeView,
    role: {
      title: roleForm.elements["title"].value,
      description: roleForm.elements["description"].value,
    },
    rubric: {
      role_id: document.getElementById("rubric-role").value,
      criteria,
      salary_min: document.getElementById("salary-min").value,
      salary_max: document.getElementById("salary-max").value,
      experience_min: document.getElementById("experience-min").value,
      experience_max: document.getElementById("experience-max").value,
      allowed_levels: document.getElementById("allowed-levels").value,
    },
    candidate: {
      role_id: document.getElementById("candidate-role").value,
      name: candForm.elements["name"].value,
      email: candForm.elements["email"].value,
      salary_expectation: candForm.elements["salary_expectation"].value,
      years_experience: candForm.elements["years_experience"].value,
      current_level: candForm.elements["current_level"].value,
      resume_text: candForm.elements["resume_text"].value,
    },
  };
  try { localStorage.setItem(DRAFT_STORE, JSON.stringify(draft)); }
  catch (_) { /* draft persistence is best-effort */ }
}

function restoreDrafts() {
  const draft = getDrafts();
  const roleForm = document.getElementById("role-form");
  const candForm = document.getElementById("candidate-form");
  if (draft.role) {
    roleForm.elements["title"].value = draft.role.title || "";
    roleForm.elements["description"].value = draft.role.description || "";
  }
  if (draft.rubric) {
    criteria = Array.isArray(draft.rubric.criteria) ? draft.rubric.criteria : [];
    document.getElementById("salary-min").value = draft.rubric.salary_min || "";
    document.getElementById("salary-max").value = draft.rubric.salary_max || "";
    document.getElementById("experience-min").value = draft.rubric.experience_min || "";
    document.getElementById("experience-max").value = draft.rubric.experience_max || "";
    document.getElementById("allowed-levels").value = draft.rubric.allowed_levels || "";
    loadRoleOptions("rubric-role", draft.rubric.role_id || "");
    renderCriteria();
  }
  if (draft.candidate) {
    loadRoleOptions("candidate-role", draft.candidate.role_id || "");
    candForm.elements["name"].value = draft.candidate.name || "";
    candForm.elements["email"].value = draft.candidate.email || "";
    candForm.elements["salary_expectation"].value = draft.candidate.salary_expectation || "";
    candForm.elements["years_experience"].value = draft.candidate.years_experience || "";
    candForm.elements["current_level"].value = draft.candidate.current_level || "";
    candForm.elements["resume_text"].value = draft.candidate.resume_text || "";
  }
  activeView = draft.activeView || activeView;
}

document.getElementById("clear-local-drafts").onclick = () => {
  localStorage.removeItem(DRAFT_STORE);
  document.getElementById("role-form").reset();
  document.getElementById("candidate-form").reset();
  document.getElementById("salary-min").value = "";
  document.getElementById("salary-max").value = "";
  document.getElementById("experience-min").value = "";
  document.getElementById("experience-max").value = "";
  document.getElementById("allowed-levels").value = "";
  criteria = [];
  renderCriteria();
  toast("Local drafts cleared", true);
};

document.querySelector("main").addEventListener("input", saveDrafts);
document.querySelector("main").addEventListener("change", saveDrafts);

// ---- key / connect ----------------------------------------------------
const keyInput = document.getElementById("api-key");
const roleBadge = document.getElementById("role-badge");
keyInput.value = apiKey;

document.getElementById("save-key").onclick = async () => {
  apiKey = keyInput.value.trim();
  localStorage.setItem(KEY_STORE, apiKey);
  try {
    rolesCache = await api("GET", "/roles");            // probe: confirms key works
    document.getElementById("nav").hidden = false;
    document.querySelector("main").hidden = false;
    roleBadge.textContent = "connected";
    restoreDrafts();
    showView(activeView);
    toast("Connected", true);
  } catch (_) { roleBadge.textContent = ""; }
};

// ---- view switching ---------------------------------------------------
function showView(name) {
  activeView = name;
  document.querySelectorAll(".view").forEach(v => { v.hidden = true; });
  document.getElementById("view-" + name).hidden = false;
  document.querySelectorAll("#nav button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === name));
  if (name === "roles") loadRoles();
  if (name === "rubric") loadRoleOptions("rubric-role");
  if (name === "candidates") loadRoleOptions("candidate-role");
  if (name === "feedback") loadFeedback();
  saveDrafts();
}
document.querySelectorAll("#nav button").forEach(b =>
  b.onclick = () => showView(b.dataset.view));

// ---- roles ------------------------------------------------------------
async function loadRoles() {
  if (rolesCache.length === 0) rolesCache = await api("GET", "/roles");
  const list = document.getElementById("role-list");
  list.innerHTML = (rolesCache.map(r =>
    `<li><b>${esc(r.title)}</b> <small>${esc(r.id)}</small></li>`).join("")) || "<li>None yet</li>";
}
let rolesCache = [];
document.getElementById("role-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const role = await api("POST", "/roles",
    { title: f.elements["title"].value, description: f.elements["description"].value });
  rolesCache.push(role);
  f.reset(); loadRoles(); saveDrafts(); toast("Role created", true);
};
function loadRoleOptions(selectId, selectedValue = "") {
  const sel = document.getElementById(selectId);
  const current = selectedValue || sel.value;
  sel.innerHTML = rolesCache.map(r =>
    `<option value="${esc(r.id)}">${esc(r.title)}</option>`).join("");
  if (current) sel.value = current;
}

// ---- rubric editor ----------------------------------------------------
function renderCriteria() {
  const tbody = document.querySelector("#criteria-table tbody");
  tbody.innerHTML = criteria.map((c, i) =>
    `<tr><td>${esc(c.id)}</td><td>${esc(c.name)}</td>` +
    `<td>${esc(c.type)}</td><td>${c.weight}</td></tr>`).join("");
}
document.getElementById("add-criterion").onclick = () => {
  const id = prompt("criterion id"); if (!id) return;
  const name = prompt("name") || id;
  const type = (prompt("type: must_have | weighted", "weighted") || "weighted");
  const weight = parseFloat(prompt("weight", "1") || "1");
  criteria.push({ id, name, type, weight }); renderCriteria();
  saveDrafts();
};
const draftButton = document.getElementById("draft-from-jd");
draftButton.onclick = async () => {
  const roleId = document.getElementById("rubric-role").value;
  if (!roleId) { toast("Pick a role first"); return; }
  draftButton.disabled = true; draftButton.textContent = "Drafting...";
  try {
    const rubric = await api("POST", `/roles/${roleId}/rubric/draft`);
    criteria = rubric.criteria.map(c =>
      ({ id: c.id, name: c.name, type: c.type, weight: c.weight }));
    document.getElementById("experience-min").value = rubric.experience_min_years ?? "";
    document.getElementById("experience-max").value = rubric.experience_max_years ?? "";
    document.getElementById("allowed-levels").value = (rubric.allowed_seniority_levels || []).join(", ");
    renderCriteria(); saveDrafts(); toast("Drafted from JD", true);
  } finally {
    draftButton.disabled = false; draftButton.textContent = "Draft from JD";
  }
};
document.getElementById("publish-rubric").onclick = async () => {
  const roleId = document.getElementById("rubric-role").value;
  if (!roleId) { toast("Pick a role first"); return; }
  const salaryMin = document.getElementById("salary-min").value;
  const salaryMax = document.getElementById("salary-max").value;
  const expMin = document.getElementById("experience-min").value;
  const expMax = document.getElementById("experience-max").value;
  const rubricPayload = {
    criteria,
    salary_band_min: salaryMin === "" ? null : parseFloat(salaryMin),
    salary_band_max: salaryMax === "" ? null : parseFloat(salaryMax),
    experience_min_years: expMin === "" ? null : parseFloat(expMin),
    experience_max_years: expMax === "" ? null : parseFloat(expMax),
    allowed_seniority_levels: document.getElementById("allowed-levels").value.split(",").map(s => s.trim()).filter(Boolean),
  };
  const rubric = await api("POST", `/roles/${roleId}/rubric/publish`, rubricPayload);
  criteria = rubric.criteria.map(c =>
    ({ id: c.id, name: c.name, type: c.type, weight: c.weight }));
  document.getElementById("salary-min").value = rubric.salary_band_min ?? "";
  document.getElementById("salary-max").value = rubric.salary_band_max ?? "";
  document.getElementById("experience-min").value = rubric.experience_min_years ?? "";
  document.getElementById("experience-max").value = rubric.experience_max_years ?? "";
  document.getElementById("allowed-levels").value = (rubric.allowed_seniority_levels || []).join(", ");
  renderCriteria(); saveDrafts();
  toast("Rubric published", true);
};

// ---- candidates -------------------------------------------------------
let candidatesCache = [];
const resumeFileInput = document.getElementById("resume-file");
resumeFileInput.onchange = handleResumeFile;

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function handleResumeFile(e) {
  const file = e.target.files[0];
  if (!file) return;
  const form = document.getElementById("candidate-form");
  const name = file.name.toLowerCase();
  try {
    if (name.endsWith(".pdf")) {
      const dataUrl = await readFileAsDataURL(file);
      const extracted = await api("POST", "/resume/extract", {
        filename: file.name,
        content_base64: dataUrl.split(",")[1] || "",
      });
      form.resume_text.value = extracted.text;
    } else if (name.endsWith(".txt") || name.endsWith(".md")) {
      form.resume_text.value = await readFileAsText(file);
    } else {
      toast("Use a .txt, .md, or .pdf resume");
      return;
    }
    saveDrafts();
    toast("Resume loaded", true);
  } catch (_) {
    e.target.value = "";
  }
}

document.getElementById("candidate-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const roleId = document.getElementById("candidate-role").value;
  const salary = f.elements["salary_expectation"].value;
  const years = f.elements["years_experience"].value;
  const cand = await api("POST", `/roles/${roleId}/candidates`, {
    name: f.elements["name"].value, email: f.elements["email"].value,
    resume_text: f.elements["resume_text"].value,
    salary_expectation: salary === "" ? null : parseFloat(salary),
    years_experience: years === "" ? null : parseFloat(years),
    current_level: f.elements["current_level"].value,
  });
  candidatesCache.push(cand);
  renderCandidates(); f.reset(); saveDrafts(); toast("Candidate added", true);
};
function renderCandidates() {
  document.getElementById("candidate-list").innerHTML =
    candidatesCache.map(c =>
      `<li><b>${esc(c.name)}</b> <small>${esc(c.id)}</small>
       <button data-candidate-id="${esc(c.id)}" data-role-id="${esc(c.role_id)}">Evaluate</button></li>`).join("")
    || "<li>None yet</li>";
}
function setEvaluationProgress(message = "", active = false) {
  const panel = document.getElementById("evaluation-progress");
  const text = document.getElementById("evaluation-progress-text");
  const progress = panel.querySelector("progress");
  text.textContent = message;
  progress.hidden = !active;
  panel.hidden = !message;
}
document.getElementById("candidate-list").onclick = (e) => {
  const button = e.target.closest("button[data-candidate-id]");
  if (!button) return;
  evaluate(button.dataset.candidateId, button);
};
async function evaluate(candidateId, button) {
  const oldText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "Evaluating...";
  }
  setEvaluationProgress("Evaluation running...", true);
  toast("Evaluation running...", true);
  try {
    const ev = await api("POST", `/candidates/${candidateId}/evaluate`);
    evaluationsCache.push(ev);
    renderEvaluations();
    setEvaluationProgress("Evaluation complete", false);
    toast("Evaluation complete", true);
    showView("evaluations");
  } catch (err) {
    setEvaluationProgress("Evaluation failed", false);
    if (err.status === 422 && button && button.dataset.roleId) {
      showView("rubric");
      loadRoleOptions("rubric-role", button.dataset.roleId);
      toast("Publish rubric for this role before evaluating");
    }
    throw err;
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = oldText || "Evaluate";
    }
  }
}
window.evaluate = evaluate;

// ---- evaluations ------------------------------------------------------
let evaluationsCache = [];
function renderEvaluations() {
  document.getElementById("evaluation-list").innerHTML =
    evaluationsCache.map(ev => {
      const scores = (ev.scores || []).map(s =>
        `${esc(s.criterion_id)}=${s.score}`).join(", ");
      let salary = "salary_band=not_configured";
      if (ev.salary_checked) salary = ev.salary_mismatch ? "salary_band=mismatch" : "salary_band=ok";
      let exp = "experience_range=not_configured";
      if (ev.experience_checked) exp = ev.experience_mismatch ? "experience_range=mismatch" : "experience_range=ok";
      let level = "seniority_level=not_configured";
      if (ev.seniority_checked) level = ev.seniority_mismatch ? "seniority_level=mismatch" : "seniority_level=ok";
      return `<li><b>${esc(ev.id)}</b> <span class="badge">${esc(ev.status)}</span>
        <div>${scores}</div><div>${salary}</div><div>${exp}</div><div>${level}</div>
        <button onclick="draftFeedback('${esc(ev.id)}', this)">Draft feedback</button></li>`;
    }).join("") || "<li>None yet</li>";
}
async function draftFeedback(evaluationId, button) {
  const oldText = button ? button.textContent : "";
  if (button) { button.disabled = true; button.textContent = "Drafting..."; }
  try {
    const fb = await api("POST", `/evaluations/${evaluationId}/feedback/draft`);
    feedbackCache.push(fb);
    toast("Feedback drafted", true); showView("feedback");
  } finally {
    if (button) { button.disabled = false; button.textContent = oldText || "Draft feedback"; }
  }
}
window.draftFeedback = draftFeedback;

// ---- feedback approval queue -----------------------------------------
let feedbackCache = [];
function loadFeedback() { renderFeedback(); }
function renderFeedback() {
  document.getElementById("feedback-list").innerHTML =
    feedbackCache.map(fb => {
      const bullets = (fb.bullets || []).map(b =>
        `<li>${esc(b.text)} <small>(${esc(b.criterion_id)})</small></li>`).join("");
      return `<li><span class="badge ${esc(fb.status)}">${esc(fb.status)}</span>
        <p>${esc(fb.intro)}</p><ul>${bullets}</ul>
        <button onclick="approve('${esc(fb.id)}')">Approve</button>
        <button onclick="send('${esc(fb.id)}')">Send</button></li>`;
    }).join("") || "<li>Queue empty</li>";
}
async function approve(id) {
  const fb = await api("POST", `/feedback/${id}/approve`);
  replaceFeedback(fb); toast("Approved", true);
}
async function send(id) {
  const fb = await api("POST", `/feedback/${id}/send`);
  replaceFeedback(fb); toast("Sent", true);
}
function replaceFeedback(fb) {
  const i = feedbackCache.findIndex(x => x.id === fb.id);
  if (i >= 0) feedbackCache[i] = fb; else feedbackCache.push(fb);
  renderFeedback();
}
window.approve = approve; window.send = send;

// ---- util -------------------------------------------------------------
function esc(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// auto-connect if a key is already stored
if (apiKey) document.getElementById("save-key").click();
