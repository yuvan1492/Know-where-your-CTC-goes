const form = document.querySelector("#salary-form");
const calculateButton = document.querySelector("#calculate-button");
const runtimeStatus = document.querySelector("#runtime-status");
const runtimeDot = document.querySelector("#runtime-dot");
const formError = document.querySelector("#form-error");
const results = document.querySelector("#results");
const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

let pyodide;

function setRuntimeState(message, state) {
  runtimeStatus.textContent = message;
  runtimeDot.className = `runtime-dot ${state}`;
}

function amount(value) {
  return currency.format(value || 0);
}

function appendResultRow(list, label, value) {
  const row = document.createElement("div");
  row.className = "result-row";
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  row.append(term, description);
  list.append(row);
}

function renderRegime(name, data) {
  const card = document.createElement("article");
  card.className = `regime-card ${name.toLowerCase()}`;
  const title = document.createElement("p");
  title.className = "regime-name";
  title.textContent = `${name} regime`;
  const monthlyLabel = document.createElement("p");
  monthlyLabel.className = "monthly-label";
  monthlyLabel.textContent = "Estimated bank in-hand / month";
  const monthly = document.createElement("p");
  monthly.className = "monthly-value";
  monthly.textContent = amount(data.monthly_in_hand);
  const details = document.createElement("dl");
  details.className = "result-list";
  appendResultRow(details, "Annual in-hand", amount(data.bank_in_hand));
  appendResultRow(details, "Taxable salary", amount(data.taxable_salary));
  appendResultRow(details, "Income tax + cess", amount(data.income_tax));
  appendResultRow(details, "Retirement wealth", amount(data.employee_wealth));
  appendResultRow(details, "Government incl. PT", amount(data.government));
  appendResultRow(details, "Employer costs", amount(data.employer_costs));
  const note = document.createElement("p");
  note.className = "tax-note";
  note.textContent = data.tax_note;
  card.append(title, monthlyLabel, monthly, details, note);
  return card;
}

function appendTable(container, caption, headings, rows) {
  const table = document.createElement("table");
  table.className = "sweep-table";
  const tableCaption = document.createElement("caption");
  tableCaption.textContent = caption;
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const heading of headings) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = heading;
    headerRow.append(th);
  }
  thead.append(headerRow);
  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const value of row) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tableCaption, thead, tbody);
  container.append(table);
}

function renderSweep(sweep) {
  const container = document.querySelector("#sweep-tables");
  container.replaceChildren();
  for (const regime of ["NEW", "OLD"]) {
    const rows = sweep[regime];
    appendTable(
      container,
      `${regime} regime · income and take-home`,
      ["Hike", "CTC / year", "Tax / year", "In-hand / month", "Monthly gain"],
      rows.map((row) => [
        `${row.hike}%`,
        amount(row.ctc),
        amount(row.income_tax),
        amount(row.monthly_in_hand),
        amount(row.monthly_gain),
      ]),
    );
    appendTable(
      container,
      `${regime} regime · CTC destinations`,
      ["Hike", "Retirement wealth", "Government", "Employer costs", "Unallocated"],
      rows.map((row) => [
        `${row.hike}%`,
        amount(row.employee_wealth),
        amount(row.government),
        amount(row.employer_costs),
        amount(row.unallocated_ctc),
      ]),
    );
  }
}

function collectInputs() {
  const payload = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    if (element.type === "checkbox") {
      payload[element.name] = element.checked;
    } else if (element.type === "number") {
      payload[element.name] = Number(element.value || 0);
    } else {
      payload[element.name] = element.value;
    }
  }
  return payload;
}

function renderResults(output) {
  const cards = document.querySelector("#regime-results");
  cards.replaceChildren(renderRegime("NEW", output.new), renderRegime("OLD", output.old));
  renderSweep(output.sweep);
  document.querySelector("#result-summary").textContent =
    `CTC ${amount(output.new.ctc)} · CTC-flow reconciliation ${output.new.ctc_flow_total === output.new.ctc ? "matches" : "check components"}.`;
  results.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  if (!form.reportValidity()) return;
  if (!pyodide) {
    formError.textContent = "The Python runtime is still loading. Please wait a moment and try again.";
    return;
  }

  const payload = collectInputs();
  if (payload.hra_qualifying_commission > payload.commission) {
    formError.textContent = "HRA-qualifying commission is a subset and cannot exceed annual commission.";
    return;
  }
  if (payload.employer_nps_deduction > payload.employer_nps) {
    formError.textContent = "The employer NPS deduction cannot exceed the employer NPS contribution.";
    return;
  }

  calculateButton.disabled = true;
  calculateButton.querySelector("span:first-child").textContent = "Calculating…";
  try {
    pyodide.globals.set("_salary_payload", JSON.stringify(payload));
    const resultProxy = await pyodide.runPythonAsync(
      "web_calculator.calculate_json(_salary_payload)",
    );
    const output = JSON.parse(resultProxy.toString());
    if (typeof resultProxy.destroy === "function") resultProxy.destroy();
    renderResults(output);
  } catch (error) {
    formError.textContent = `Could not calculate: ${error.message}`;
  } finally {
    calculateButton.disabled = false;
    calculateButton.querySelector("span:first-child").textContent = "Calculate take-home";
  }
});

document.querySelector("#load-example").addEventListener("click", () => {
  const example = {
    ctc: 1250000,
    basic: 437500,
    hra: 391083,
    other_taxable_allowances: 385417,
    employer_pf: 36000,
  };
  for (const [name, value] of Object.entries(example)) {
    form.elements.namedItem(name).value = value;
  }
  form.elements.namedItem("ctc").focus();
});

async function startPython() {
  try {
    setRuntimeState("Loading Python engine…", "");
    pyodide = await loadPyodide();
    for (const filename of ["indian_salary_ctc_estimator.py", "web_calculator.py"]) {
      const response = await fetch(filename);
      if (!response.ok) throw new Error(`Could not load ${filename} (${response.status})`);
      pyodide.FS.writeFile(`/home/pyodide/${filename}`, await response.text());
    }
    await pyodide.runPythonAsync(
      'import sys; sys.path.insert(0, "/home/pyodide"); import web_calculator',
    );
    calculateButton.disabled = false;
    setRuntimeState("Python ready · calculations stay in this browser", "ready");
  } catch (error) {
    setRuntimeState("Python runtime unavailable", "error");
    formError.textContent = `Could not start the Python engine: ${error.message}. Check your connection and reload.`;
  }
}

startPython();