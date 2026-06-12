"use strict";

const KEY_STORE = "rfe_api_key";
let apiKey = localStorage.getItem(KEY_STORE) || "";
let criteria = [];   // working rubric criteria in the editor

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
  const res = await fetch(path, opts);
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

// ---- key / connect ----------------------------------------------------
const keyInput = document.getElementById("api-key");
const roleBadge = document.getElementById("role-badge");
keyInput.value = apiKey;

document.getElementById("save-key").onclick = async () => {
  apiKey = keyInput.value.trim();
  localStorage.setItem(KEY_STORE, apiKey);
  try {
    await api("GET", "/roles");            // probe: confirms key works
    document.getElementById("nav").hidden = false;
    document.querySelector("main").hidden = false;
    roleBadge.textContent = "connected";
    showView("roles");
    toast("Connected", true);
  } catch (_) { roleBadge.textContent = ""; }
};

// ---- view switching ---------------------------------------------------
function showView(name) {
  document.querySelectorAll(".view").forEach(v => { v.hidden = true; });
  document.getElementById("view-" + name).hidden = false;
  document.querySelectorAll("#nav button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === name));
  if (name === "roles") loadRoles();
  if (name === "rubric") loadRoleOptions("rubric-role");
  if (name === "candidates") loadRoleOptions("candidate-role");
  if (name === "feedback") loadFeedback();
}
document.querySelectorAll("#nav button").forEach(b =>
  b.onclick = () => showView(b.dataset.view));

// ---- roles ------------------------------------------------------------
async function loadRoles() {
  const list = document.getElementById("role-list");
  list.innerHTML = (rolesCache.map(r =>
    `<li><b>${esc(r.title)}</b> <small>${esc(r.id)}</small></li>`).join("")) || "<li>None yet</li>";
}
let rolesCache = [];
document.getElementById("role-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const role = await api("POST", "/roles",
    { title: f.title.value, description: f.description.value });
  rolesCache.push(role);
  f.reset(); loadRoles(); toast("Role created", true);
};
function loadRoleOptions(selectId) {
  const sel = document.getElementById(selectId);
  sel.innerHTML = rolesCache.map(r =>
    `<option value="${esc(r.id)}">${esc(r.title)}</option>`).join("");
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
};
document.getElementById("draft-from-jd").onclick = async () => {
  const roleId = document.getElementById("rubric-role").value;
  if (!roleId) { toast("Pick a role first"); return; }
  const rubric = await api("POST", `/roles/${roleId}/rubric/draft`);
  criteria = rubric.criteria.map(c =>
    ({ id: c.id, name: c.name, type: c.type, weight: c.weight }));
  renderCriteria(); toast("Drafted from JD", true);
};
document.getElementById("publish-rubric").onclick = async () => {
  const roleId = document.getElementById("rubric-role").value;
  if (!roleId) { toast("Pick a role first"); return; }
  await api("POST", `/roles/${roleId}/rubric/publish`);
  toast("Rubric published", true);
};

// ---- candidates -------------------------------------------------------
let candidatesCache = [];
document.getElementById("candidate-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const roleId = document.getElementById("candidate-role").value;
  const salary = f.salary_expectation.value;
  const cand = await api("POST", `/roles/${roleId}/candidates`, {
    name: f.name.value, email: f.email.value,
    resume_text: f.resume_text.value,
    salary_expectation: salary === "" ? null : parseFloat(salary),
  });
  candidatesCache.push(cand);
  renderCandidates(); f.reset(); toast("Candidate added", true);
};
function renderCandidates() {
  document.getElementById("candidate-list").innerHTML =
    candidatesCache.map(c =>
      `<li><b>${esc(c.name)}</b> <small>${esc(c.id)}</small>
       <button onclick="evaluate('${esc(c.id)}')">Evaluate</button></li>`).join("")
    || "<li>None yet</li>";
}
async function evaluate(candidateId) {
  const ev = await api("POST", `/candidates/${candidateId}/evaluate`);
  evaluationsCache.push(ev);
  renderEvaluations(); toast("Evaluation complete", true);
}
window.evaluate = evaluate;

// ---- evaluations ------------------------------------------------------
let evaluationsCache = [];
function renderEvaluations() {
  document.getElementById("evaluation-list").innerHTML =
    evaluationsCache.map(ev => {
      const scores = (ev.scores || []).map(s =>
        `${esc(s.criterion_id)}=${s.score}`).join(", ");
      return `<li><b>${esc(ev.id)}</b> <span class="badge">${esc(ev.status)}</span>
        <div>${scores}</div>
        <button onclick="draftFeedback('${esc(ev.id)}')">Draft feedback</button></li>`;
    }).join("") || "<li>None yet</li>";
}
async function draftFeedback(evaluationId) {
  const fb = await api("POST", `/evaluations/${evaluationId}/feedback/draft`);
  feedbackCache.push(fb);
  toast("Feedback drafted", true); showView("feedback");
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
