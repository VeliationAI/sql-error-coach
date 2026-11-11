const samples = JSON.parse(document.querySelector("#samples").textContent);
const form = document.querySelector("#coach");
const errorEl = document.querySelector("#error");
const sqlEl = document.querySelector("#sql");
const dialectEl = document.querySelector("#dialect");
const explainButton = document.querySelector("#explain");
const emptyEl = document.querySelector("#empty");
const reportEl = document.querySelector("#report");

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const sample = samples[chip.dataset.code];
    errorEl.value = sample.error;
    sqlEl.value = sample.sql || "";
    dialectEl.value = "auto";
    form.requestSubmit();
  });
});

document.querySelector("#clear").addEventListener("click", () => {
  errorEl.value = "";
  sqlEl.value = "";
  dialectEl.value = "auto";
  reportEl.hidden = true;
  reportEl.textContent = "";
  emptyEl.hidden = false;
  errorEl.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = errorEl.value.trim();
  if (!error) {
    showFailure("Paste the error message.");
    return;
  }
  explainButton.disabled = true;
  explainButton.textContent = "Reading the error…";
  try {
    const response = await fetch("/api/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        error,
        sql: sqlEl.value,
        dialect: dialectEl.value,
      }),
    });
    const body = await response.json();
    if (!response.ok) {
      showFailure(body.detail || "Could not read that error.");
      return;
    }
    renderReport(body.report);
  } catch {
    showFailure("The coach could not be reached. Try again.");
  } finally {
    explainButton.disabled = false;
    explainButton.textContent = "Explain this error";
  }
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    form.requestSubmit();
  }
});

function showFailure(message) {
  emptyEl.hidden = true;
  reportEl.hidden = false;
  reportEl.className = "unmatched";
  reportEl.textContent = "";
  const title = document.createElement("h2");
  title.textContent = message;
  reportEl.append(title);
}

function renderReport(report) {
  emptyEl.hidden = true;
  reportEl.hidden = false;
  reportEl.className = report.matched ? "" : "unmatched";
  reportEl.textContent = "";

  const badge = document.createElement("p");
  badge.className = "badge";
  badge.textContent = `${report.dialect_label} · ${report.matched ? "Matched" : "Not in v0.1"}`;
  const title = document.createElement("h2");
  title.className = "plain";
  title.textContent = report.plain;
  const why = document.createElement("p");
  why.className = "why";
  why.textContent = report.why;
  const steps = document.createElement("ol");
  steps.className = "steps";
  report.steps.forEach((step, index) => {
    const item = document.createElement("li");
    const number = document.createElement("b");
    number.textContent = String(index + 1);
    const text = document.createElement("span");
    text.textContent = step;
    item.append(number, text);
    steps.append(item);
  });
  reportEl.append(badge, title, why, steps);

  if (report.corrected_query) {
    reportEl.append(codeBlock(report.correction_label, report.corrected_query, report.correction_note));
  }
  if (report.correction_source === "example") {
    reportEl.append(codeBlock("Typical mistake", report.example_before, ""));
  }
}

function codeBlock(label, code, note) {
  const wrap = document.createElement("section");
  wrap.className = "code";
  const header = document.createElement("header");
  const text = document.createElement("div");
  const name = document.createElement("p");
  name.textContent = label;
  text.append(name);
  if (note) {
    const extra = document.createElement("p");
    extra.className = "note";
    extra.textContent = note;
    text.append(extra);
  }
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "copy";
  copy.textContent = "Copy";
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(code);
      copy.textContent = "Copied";
    } catch {
      copy.textContent = "Copy failed";
    }
    window.setTimeout(() => {
      copy.textContent = "Copy";
    }, 1400);
  });
  header.append(text, copy);
  const pre = document.createElement("pre");
  pre.textContent = code;
  wrap.append(header, pre);
  return wrap;
}
