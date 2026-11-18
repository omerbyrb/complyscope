// complyscope dashboard: reads the local read-only API and renders it.
// Every value from the API is inserted as text (textContent / append), never as HTML,
// because titles, notes and plans come from editable YAML files (ADR-0016).
"use strict";

const STATUS_LABELS = {
  fail: "Fail",
  partial: "Partial",
  not_assessed: "Not assessed",
  pass: "Pass",
};
const STATUSES = Object.keys(STATUS_LABELS);
const METHOD_LABELS = {
  automated: "Scan",
  questionnaire: "Questionnaire",
  hybrid: "Scan + questionnaire",
};

const state = { filter: "all", assessment: null };

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

const $ = (id) => document.getElementById(id);
const humanise = (text) => {
  const words = String(text).replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
};
const pill = (kind, label) => el("span", { class: `pill ${kind}`, text: label });

class ApiError extends Error {
  constructor(source, message) {
    super(message);
    this.source = source;
  }
}

async function getJSON(path) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("server", "The complyscope server is not reachable. Is it still running?");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && body.detail;
    if (detail && typeof detail === "object") throw new ApiError(detail.source, detail.message);
    throw new ApiError("server", typeof detail === "string" ? detail : `HTTP ${response.status}`);
  }
  return body;
}

function showError(error) {
  const box = $("error");
  const source = error.source && error.source !== "server" ? ` (${error.source} file)` : "";
  box.replaceChildren(
    el("strong", { text: `Could not load the assessment${source}` }),
    el("span", { text: error.message }),
  );
  box.hidden = false;
}

// --- summary ---------------------------------------------------------------------------

function tile(label, value, hint) {
  return el(
    "div",
    { class: "tile" },
    el("p", { class: "label", text: label }),
    el("p", { class: "value", text: value }),
    el("p", { class: "hint", text: hint }),
  );
}

function renderSummary(assessment, risks) {
  const s = assessment.score;
  const assessed = s.total - s.not_assessed;
  const open = risks.filter((r) => r.status === "open");
  const severe = open.filter((r) => r.level === "high" || r.level === "critical");
  $("tiles").replaceChildren(
    tile("Compliance", `${s.compliance_percent}%`, `${s.passed} of ${s.total} controls pass`),
    tile("Coverage", `${s.coverage_percent}%`, `${assessed} of ${s.total} controls assessed`),
    tile("Failing controls", String(s.failed), `${s.partial} partial`),
    tile("Open risks", String(open.length), `${severe.length} high or critical`),
  );
  const counts = { fail: s.failed, partial: s.partial, not_assessed: s.not_assessed, pass: s.passed };
  $("statusbar").replaceChildren(
    ...STATUSES.filter((k) => counts[k] > 0).map((k) => {
      // Set through the CSSOM: the CSP forbids inline style attributes.
      const segment = el("span", { class: `seg-${k}`, title: `${STATUS_LABELS[k]}: ${counts[k]}` });
      segment.style.flexGrow = String(counts[k]);
      return segment;
    }),
  );
  $("legend").replaceChildren(
    ...STATUSES.map((k) => el("li", { class: k, text: `${STATUS_LABELS[k]} ${counts[k]}` })),
  );
}

// --- controls --------------------------------------------------------------------------

function renderFilters(controls) {
  const options = ["all", ...STATUSES];
  $("filters").replaceChildren(
    ...options.map((key) => {
      const count = key === "all" ? controls.length : controls.filter((c) => c.status === key).length;
      const label = key === "all" ? "All" : STATUS_LABELS[key];
      return el("button", {
        type: "button",
        "aria-pressed": String(state.filter === key),
        text: `${label} (${count})`,
        onclick: () => {
          state.filter = key;
          renderControls(state.assessment.controls);
        },
      });
    }),
  );
}

function renderControls(controls) {
  renderFilters(controls);
  const shown = controls.filter((c) => state.filter === "all" || c.status === state.filter);
  const rows = shown.map((control) => {
    const detailRow = el("tr", { class: "detail", hidden: true });
    const toggle = el("button", {
      type: "button",
      class: "toggle",
      "aria-expanded": "false",
      text: control.id,
      onclick: () => toggleDetail(control.id, toggle, detailRow),
    });
    const row = el(
      "tr",
      {},
      el("td", { class: "id" }, toggle),
      el("td", {}, el("div", { text: control.title }), el("div", { class: "muted small", text: control.rationale })),
      el("td", { text: humanise(control.theme) }),
      el("td", { text: METHOD_LABELS[control.assessment] || humanise(control.assessment) }),
      el("td", {}, pill(control.status, STATUS_LABELS[control.status] || control.status)),
    );
    return [row, detailRow];
  });
  $("controls").replaceChildren(
    ...(rows.length ? rows.flat() : [el("tr", {}, el("td", { class: "empty", colspan: 5, text: "No controls with this status." }))]),
  );
}

async function toggleDetail(id, toggle, row) {
  const open = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!open));
  row.hidden = open;
  if (open || row.dataset.loaded) return;
  row.replaceChildren(el("td", { colspan: 5, class: "muted", text: "Loading…" }));
  try {
    const detail = await getJSON(`/api/controls/${encodeURIComponent(id)}`);
    row.replaceChildren(el("td", { colspan: 5 }, renderDetail(detail)));
    row.dataset.loaded = "true";
  } catch (error) {
    row.replaceChildren(el("td", { colspan: 5, class: "warn", text: error.message }));
  }
}

function block(title, ...content) {
  return el("div", {}, el("h3", { text: title }), ...content);
}

function smallTable(headers, rows) {
  return el(
    "table",
    {},
    el("thead", {}, el("tr", {}, ...headers.map((h) => el("th", { scope: "col", text: h })))),
    el("tbody", {}, ...rows.map((cells) => el("tr", {}, ...cells.map((c) => el("td", {}, c))))),
  );
}

function renderDetail(detail) {
  const parts = [
    block("What the control requires", el("p", { text: detail.description })),
    block("Why this status", el("p", { text: detail.rationale })),
  ];
  if (detail.evidence.length) {
    parts.push(
      block(
        "Evidence",
        smallTable(
          ["Check", "Target", "Observed", "Severity", "Collected"],
          detail.evidence.map((e) => [
            e.check,
            e.target,
            e.observed === "present" ? el("span", { class: "warn", text: "issue found" }) : el("span", { class: "ok", text: "not found" }),
            e.severity || "–",
            e.collected_at.slice(0, 16).replace("T", " "),
          ]),
        ),
      ),
    );
  }
  if (detail.answers.length) {
    parts.push(
      block(
        "Questionnaire answers",
        smallTable(
          ["Question", "Answer", "Answered by", "On", "Note"],
          detail.answers.map((a) => [a.question, humanise(a.answer), a.answered_by, a.answered_on, a.note || "–"]),
        ),
      ),
    );
  }
  const crosswalk = Object.entries(detail.crosswalk);
  if (crosswalk.length) {
    parts.push(
      block(
        "Related controls (indicative)",
        el("ul", {}, ...crosswalk.map(([framework, ids]) => el("li", { text: `${framework}: ${ids.join(", ")}` }))),
      ),
    );
  }
  return el("div", { class: "detail-body" }, ...parts);
}

// --- risks -----------------------------------------------------------------------------

function renderRisks(risks) {
  const open = risks
    .filter((r) => r.status === "open")
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  const rows = open.map((r) =>
    el(
      "tr",
      {},
      el("td", {}, el("div", { class: "id", text: r.id }), el("div", { text: r.title })),
      el("td", { class: "id", text: r.control_ids.join(", ") }),
      el("td", { class: "num", text: `${r.likelihood} × ${r.impact} = ${r.score}` }),
      el("td", {}, pill(r.level, humanise(r.level))),
      el("td", r.owner ? { text: r.owner } : { class: "warn", text: "Unassigned" }),
      el("td", { class: r.review_overdue ? "num warn" : "num", text: r.review_overdue ? `${r.review_by} (overdue)` : r.review_by }),
      el(
        "td",
        {},
        r.needs_attention.length
          ? el("ul", { class: "needs" }, ...r.needs_attention.map((n) => el("li", { text: n })))
          : el("span", { class: "ok", text: "Nothing outstanding" }),
      ),
    ),
  );
  const empty = risks.length
    ? "No open risks."
    : "No risk register yet. Run complyscope risks to draft risks from failed controls.";
  $("risks").replaceChildren(
    ...(rows.length ? rows : [el("tr", {}, el("td", { class: "empty", colspan: 7, text: empty }))]),
  );
  const closed = risks.length - open.length;
  $("risks-note").textContent = closed ? `${closed} closed risk(s) not shown.` : "";
}

// --- loading ---------------------------------------------------------------------------

async function load() {
  const button = $("refresh");
  button.disabled = true;
  try {
    const [assessment, register] = await Promise.all([getJSON("/api/assessment"), getJSON("/api/risks")]);
    state.assessment = assessment;
    $("error").hidden = true;
    $("organisation").textContent = assessment.organisation;
    $("framework").textContent = `${assessment.framework.name} v${assessment.framework.version} · self-assessment`;
    document.title = `${assessment.organisation} · complyscope`;
    renderSummary(assessment, register.risks);
    renderControls(assessment.controls);
    renderRisks(register.risks);
    $("updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("refresh").addEventListener("click", load);
  load();
});
