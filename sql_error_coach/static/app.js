const FACTS = {
  token: "Stopped at",
  table: "Table",
  column: "Column",
  hint: "Try instead",
  value: "Value",
  parent: "Parent",
  type_name: "Type",
  literal: "Literal",
  function: "Function",
  line: "Line",
  object: "Name",
  vendor_code: "Code",
  sqlstate: "SQLSTATE",
};

const samples = JSON.parse(document.querySelector("#samples").textContent);
const form = document.querySelector("#coach");
const errorEl = document.querySelector("#error");
const sqlEl = document.querySelector("#sql");
const queryBox = document.querySelector("#query-box");
const dialectEl = document.querySelector("#dialect");
const explainButton = document.querySelector("#explain");
const emptyEl = document.querySelector("#empty");
const reportEl = document.querySelector("#report");
const resultEl = document.querySelector("#result");

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const sample = samples[chip.dataset.code];
    errorEl.value = sample.error;
    sqlEl.value = sample.sql || "";
    queryBox.open = Boolean(sample.sql);
    dialectEl.value = "auto";
    setPressed(chip);
    form.requestSubmit();
  });
});

document.querySelector("#clear").addEventListener("click", () => {
  errorEl.value = "";
  sqlEl.value = "";
  queryBox.open = false;
  dialectEl.value = "auto";
  setPressed(null);
  showEmpty();
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
    if (window.matchMedia("(max-width: 860px)").matches) {
      resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
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

function setPressed(active) {
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.setAttribute("aria-pressed", chip === active ? "true" : "false");
  });
}

function showEmpty() {
  reportEl.hidden = true;
  reportEl.textContent = "";
  emptyEl.hidden = false;
  resultEl.classList.remove("unmatched");
}

function showFailure(message) {
  emptyEl.hidden = true;
  reportEl.hidden = false;
  resultEl.classList.add("unmatched");
  reportEl.textContent = "";
  const title = document.createElement("h2");
  title.textContent = message;
  reportEl.append(title);
}

function renderReport(report) {
  emptyEl.hidden = true;
  reportEl.hidden = false;
  resultEl.classList.toggle("unmatched", !report.matched);
  reportEl.textContent = "";

  const badge = document.createElement("p");
  badge.className = "badge";
  badge.textContent = report.dialect_label;
  const heading = document.createElement("h2");
  heading.className = "diagnosis";
  heading.textContent = report.title;
  const plain = document.createElement("p");
  plain.className = "plain";
  plain.textContent = report.plain;
  const why = document.createElement("p");
  why.className = "why";
  why.textContent = report.why;
  reportEl.append(badge, heading, plain, why, facts(report.identifiers));

  if (report.steps.length) {
    const label = document.createElement("p");
    label.className = "step-label";
    label.textContent = "Do this";
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
    reportEl.append(label, steps);
  }

  const before = report.correction_source === "yours" ? report.sql : report.example_before;
  if (report.corrected_query && before && before.trim() !== report.corrected_query.trim()) {
    const pair = document.createElement("div");
    pair.className = "compare";
    pair.append(
      codeBlock("What failed", before, "", false),
      codeBlock(report.correction_label, report.corrected_query, "", true),
    );
    const note = document.createElement("p");
    note.className = "compare-note";
    note.textContent = report.correction_note;
    reportEl.append(pair, note);
  } else if (report.corrected_query) {
    reportEl.append(codeBlock(report.correction_label, report.corrected_query, report.correction_note, true));
  }
}

function facts(identifiers) {
  const row = document.createElement("div");
  row.className = "facts";
  Object.entries(FACTS).forEach(([key, label]) => {
    const value = identifiers && identifiers[key];
    if (!value) return;
    const pill = document.createElement("span");
    pill.className = "fact";
    const name = document.createElement("b");
    name.textContent = `${label} `;
    pill.append(name, document.createTextNode(value));
    row.append(pill);
  });
  return row;
}

function codeBlock(label, code, note, canCopy) {
  const wrap = document.createElement("section");
  wrap.className = canCopy ? "code after" : "code before";
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
  header.append(text);
  if (canCopy) {
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
    header.append(copy);
  }
  const pre = document.createElement("pre");
  pre.textContent = code;
  wrap.append(header, pre);
  return wrap;
}
