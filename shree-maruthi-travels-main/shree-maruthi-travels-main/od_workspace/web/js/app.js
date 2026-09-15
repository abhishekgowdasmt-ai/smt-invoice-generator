const CIRC = 2 * Math.PI * 56;
let state = null;
let charts = {};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const OD_BASE = "/admin/workspace";

async function api(path, options = {}) {
  const res = await fetch(OD_BASE + path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function inr(n) {
  const value = Number(n) || 0;
  const neg = value < 0;
  const [w, f] = Math.abs(value).toFixed(2).split(".");
  let grouped = w;
  if (w.length > 3) {
    const last3 = w.slice(-3);
    let rest = w.slice(0, -3);
    const parts = [];
    while (rest) {
      parts.unshift(rest.slice(-2));
      rest = rest.slice(0, -2);
    }
    grouped = `${parts.join(",")},${last3}`;
  }
  return `${neg ? "-" : ""}₹${grouped}.${f}`;
}

function lakhs(n) {
  return `₹${(Math.abs(Number(n) || 0) / 100000).toFixed(2)} L`;
}

function chipClass(type) {
  const key = String(type).toLowerCase();
  if (key === "credit") return "credit";
  if (key === "interest" || key === "charge") return "interest";
  return "";
}

function statement(rows, mount, onClick) {
  if (!rows.length) {
    mount.innerHTML = `<p class="empty">No movements yet. Post the first drawdown from New entry.</p>`;
    return;
  }
  const ordered = [...rows].reverse();
  mount.innerHTML = ordered
    .map((row) => {
      const incoming = row.type === "Credit";
      const extra = [row.category, row.counterparty, row.project].filter(Boolean).join(" · ");
      const bal = row.outstanding != null ? ` · bal ${inr(row.outstanding)}` : "";
      return `<button class="txn" data-id="${row.id}" type="button">
        <time>${row.date || ""}</time>
        <div>
          <b><span class="chip ${chipClass(row.type)}">${row.type}</span>${row.purpose || row.category || "Entry"}</b>
          <small>${extra}${bal}</small>
        </div>
        <span class="amt ${incoming ? "in" : "out"}">${incoming ? "+" : "−"}${inr(Math.abs(row.amount))}</span>
      </button>`;
    })
    .join("");
  if (onClick) {
    $$(".txn", mount).forEach((el) => el.addEventListener("click", () => onClick(el.dataset.id)));
  }
}

function setRing(pct) {
  const clamped = Math.max(0, Math.min(100, pct));
  $("#ov-ring").style.strokeDashoffset = String(CIRC * (1 - clamped / 100));
}

function fillSelect(select, values, selected = "") {
  select.innerHTML = values.map((v) => `<option ${v === selected ? "selected" : ""}>${v}</option>`).join("");
}

function destroyChart(key) {
  if (charts[key]) {
    charts[key].destroy();
    delete charts[key];
  }
}

function lineChart(key, canvas, labels, data, color = "#2f9e5f") {
  destroyChart(key);
  charts[key] = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data,
        borderColor: color,
        backgroundColor: "rgba(47, 158, 95, 0.12)",
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#5d7a64" }, grid: { color: "rgba(28, 92, 52, 0.08)" } },
        y: { ticks: { color: "#5d7a64" }, grid: { color: "rgba(28, 92, 52, 0.08)" } },
      },
    },
  });
}

function renderOverview() {
  const snap = state.snapshot;
  const fac = state.facility;
  $("#ov-kicker").textContent = fac.bank || "Bank of Baroda";
  $("#ov-sub").textContent = [fac.holder_name || "Private account", fac.product, fac.account_last4 ? `A/c ••${fac.account_last4}` : "", fac.branch].filter(Boolean).join(" · ");
  $("#ov-available").textContent = snap.labels.available;
  $("#ov-out").textContent = snap.labels.outstanding;
  $("#ov-limit").textContent = snap.labels.limit;
  $("#ov-rate").textContent = `${snap.rate.toFixed(2)}%`;
  $("#ov-count").textContent = snap.txn_count;
  $("#ov-util").textContent = snap.labels.utilization;
  $("#ov-meter").style.width = `${Math.min(100, snap.utilization)}%`;
  $("#ov-meter-label").textContent = `${snap.labels.outstanding_l} used of ${snap.labels.limit_l}`;
  setRing(snap.utilization);
  $("#storage-pill").textContent = state.storage === "zoho" ? "Zoho Sheet" : "This device";
  $("#ov-month").innerHTML = [
    ["Drawdowns", snap.drawdowns_month],
    ["Credits", snap.credits_month],
    ["Interest posted", snap.interest_month],
    ["Charges", snap.charges_month],
    ["Estimated interest", state.interest.estimated],
  ].map(([k, v]) => `<li><span>${k}</span><b>${inr(v)}</b></li>`).join("");
  statement(state.transactions.slice(-8), $("#ov-txns"));
  lineChart("ov", $("#ov-chart"), state.series.map((r) => r.date), state.series.map((r) => r.outstanding));
}

function renderEntry() {
  fillSelect($("#entry-category"), state.categories);
  const snap = state.snapshot;
  $("#entry-sub").textContent = `Outstanding ${snap.labels.outstanding} · available ${snap.labels.available}`;
  const date = $("#entry-form [name=date]");
  if (!date.value) date.value = new Date().toISOString().slice(0, 10);
}

function renderLedger() {
  const type = $("#ledger-type").value;
  const q = $("#ledger-search").value.toLowerCase();
  const rows = state.transactions.filter((row) => {
    if (type && row.type !== type) return false;
    if (!q) return true;
    return `${row.purpose} ${row.counterparty} ${row.reference} ${row.notes} ${row.project}`.toLowerCase().includes(q);
  });
  $("#ledger-sub").textContent = `${rows.length} rows`;
  statement(rows, $("#ledger-txns"), openEdit);
}

function openEdit(id) {
  const row = state.transactions.find((item) => item.id === id);
  if (!row) return;
  const form = $("#edit-form");
  form.hidden = false;
  form.id.value = row.id;
  form.date.value = row.date;
  form.type.value = row.type;
  form.amount.value = row.amount;
  fillSelect($("#edit-category"), state.categories, row.category);
  form.mode.value = row.mode || "NEFT";
  form.counterparty.value = row.counterparty;
  form.purpose.value = row.purpose;
  form.project.value = row.project;
  form.reference.value = row.reference;
  form.notes.value = row.notes;
  form.scrollIntoView({ behavior: "smooth" });
}

function renderInsights() {
  $("#ins-stats").innerHTML = [
    ["Total drawdowns", state.snapshot.drawdowns_all],
    ["Total credits", state.snapshot.credits_all],
    ["Interest + charges", state.snapshot.interest_all + state.snapshot.charges_all],
  ].map(([k, v]) => `<div><span>${k}</span><b>${inr(v)}</b></div>`).join("");
  destroyChart("cat");
  destroyChart("mon");
  if (state.breakdown.length) {
    charts.cat = new Chart($("#cat-chart"), {
      type: "doughnut",
      data: {
        labels: state.breakdown.map((r) => r.category),
        datasets: [{ data: state.breakdown.map((r) => r.drawdown), backgroundColor: ["#2f9e5f", "#7ed9a2", "#1f7a4d", "#a8e6bf", "#4aa3d9", "#e8b86d", "#8bbf9a"] }],
      },
      options: { plugins: { legend: { labels: { color: "#16301c" } } }, cutout: "62%" },
    });
  }
  if (state.monthly.length) {
    charts.mon = new Chart($("#mon-chart"), {
      type: "bar",
      data: {
        labels: state.monthly.map((r) => r.month),
        datasets: [
          { label: "Drawdown", data: state.monthly.map((r) => r.drawdown), backgroundColor: "#2f9e5f" },
          { label: "Credit", data: state.monthly.map((r) => r.credit), backgroundColor: "#4ade9b" },
        ],
      },
      options: {
        plugins: { legend: { labels: { color: "#16301c" } } },
        scales: {
          x: { ticks: { color: "#5d7a64" }, grid: { display: false } },
          y: { ticks: { color: "#5d7a64" }, grid: { color: "rgba(28, 92, 52, 0.08)" } },
        },
      },
    });
  }
}

function renderSettings() {
  const f = state.facility;
  const form = $("#facility-form");
  form.bank.value = f.bank || "";
  form.product.value = f.product || "";
  form.limit.value = f.limit || "";
  form.rate.value = f.rate || "";
  form.sanction_date.value = f.sanction_date || "";
  form.opening_outstanding.value = f.opening_outstanding || 0;
  form.holder_name.value = f.holder_name || "";
  form.account_last4.value = f.account_last4 || "";
  form.branch.value = f.branch || "";
  form.notes.value = f.notes || "";
  $("#cat-text").value = state.categories.join("\n");
  $("#zoho-box").innerHTML = state.zoho_configured
    ? `<p class="label">Zoho Sheet</p><p>OD 99L writes to <b>OD Usage</b>. Travels writes to a separate worksheet named <b>SMT Books</b> — create that tab in Zoho (the API cannot create it), then initialise.</p><div class="btn-row"><button id="zoho-init" class="primary" type="button">Refresh OD headers</button><button id="smt-zoho-init" class="primary" type="button">Initialise SMT Books</button></div>`
    : `<p class="label">Zoho Sheet</p><p>Not connected. Data stays on this device until you add the refresh token to secrets.toml.</p>`;
  const init = $("#zoho-init");
  if (init) init.onclick = async () => {
    await api("/api/zoho/init", { method: "POST" });
    await load();
  };
  const smtInit = $("#smt-zoho-init");
  if (smtInit) smtInit.onclick = () => initSmtSheet();
}

async function loadInterest() {
  const start = $("#int-start").value;
  const end = $("#int-end").value;
  const rate = $("#int-rate").value;
  const qs = new URLSearchParams({ start, end, rate });
  const data = await api(`/api/interest?${qs}`);
  $("#int-stats").innerHTML = [
    ["Estimated", data.estimated],
    ["Posted by bank", data.posted],
    ["Difference", data.difference],
    ["Average outstanding", data.average],
  ].map(([k, v]) => `<div><span>${k}</span><b>${inr(v)}</b></div>`).join("");
  lineChart("int", $("#int-chart"), data.daily.map((r) => r.date), data.daily.map((r) => r.outstanding), "#2f9e5f");
}

function workspace() {
  return localStorage.getItem("ws") || "smt";
}

function setWorkspace(ws) {
  localStorage.setItem("ws", ws);
  document.body.dataset.ws = ws;
  $("#ws-smt").classList.toggle("on", ws === "smt");
  $("#ws-od").classList.toggle("on", ws === "od");
  $("#smt-nav").hidden = ws !== "smt";
  $("#od-nav").hidden = ws !== "od";
  $(".mark").textContent = ws === "smt" ? "S" : "B";
  if (ws === "smt") {
    const current = document.querySelector("#smt-nav button.active");
    show((current && current.dataset.view) || "smt-home");
  } else {
    const current = document.querySelector("#od-nav button.active");
    show((current && current.dataset.view) || "overview");
  }
}

function show(view) {
  view = view || (workspace() === "smt" ? "smt-home" : "overview");
  $$(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${view}`));
  $$("#smt-nav button, #od-nav button").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  if (String(view).startsWith("smt-")) {
    if (typeof renderBiz === "function") renderBiz(view);
    return;
  }
  if (!state) return;
  if (view === "overview") renderOverview();
  if (view === "entry") renderEntry();
  if (view === "ledger") renderLedger();
  if (view === "insights") renderInsights();
  if (view === "settings") renderSettings();
  if (view === "interest") {
    $("#int-rate").value = state.snapshot.rate;
    if (!$("#int-end").value) $("#int-end").value = new Date().toISOString().slice(0, 10);
    if (!$("#int-start").value) $("#int-start").value = state.facility.sanction_date || new Date().toISOString().slice(0, 8) + "01";
    loadInterest().catch((err) => alert(err.message));
  }
}

async function load() {
  state = await api("/api/overview");
  if (workspace() === "od") {
    const current = document.querySelector("#od-nav button.active");
    show((current && current.dataset.view) || "overview");
  }
}

function unlockUi() {
  document.body.classList.remove("locked");
  $("#lock").hidden = true;
  $("#shell").hidden = false;
}

async function boot() {
  const session = await api("/api/session");
  if (!session.ok) {
    location.href = "/admin";
    return;
  }
  unlockUi();
  await load();
  if (typeof loadBiz === "function") await loadBiz();
  setWorkspace(workspace());
}

const lockForm = $("#lock-form");
if (lockForm) {
  lockForm.addEventListener("submit", (ev) => ev.preventDefault());
}

$("#lock-btn").addEventListener("click", async () => {
  await fetch("/api/admin/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/admin";
});

$$("#smt-nav button, #od-nav button").forEach((btn) => btn.addEventListener("click", () => show(btn.dataset.view)));
$("#ws-smt").addEventListener("click", () => setWorkspace("smt"));
$("#ws-od").addEventListener("click", () => setWorkspace("od"));
$("#ledger-search").addEventListener("input", renderLedger);
$("#ledger-type").addEventListener("change", renderLedger);

$("#entry-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const data = Object.fromEntries(new FormData(ev.target).entries());
  try {
    await api("/api/transactions", { method: "POST", body: JSON.stringify(data) });
    ev.target.reset();
    $("#entry-msg").textContent = "Saved.";
    await load();
    show("overview");
  } catch (err) {
    $("#entry-msg").textContent = err.message;
  }
});

$("#edit-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const data = Object.fromEntries(new FormData(ev.target).entries());
  const id = data.id;
  delete data.id;
  await api(`/api/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) });
  await load();
  show("ledger");
});

$("#delete-btn").addEventListener("click", async () => {
  const id = $("#edit-form [name=id]").value;
  if (!id || !confirm("Delete this entry?")) return;
  await api(`/api/transactions/${id}`, { method: "DELETE" });
  $("#edit-form").hidden = true;
  await load();
  show("ledger");
});

$("#facility-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await api("/api/facility", { method: "PUT", body: JSON.stringify(Object.fromEntries(new FormData(ev.target).entries())) });
  await load();
  show("settings");
});

$("#cat-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const categories = $("#cat-text").value.split("\n").map((s) => s.trim()).filter(Boolean);
  await api("/api/categories", { method: "PUT", body: JSON.stringify({ categories }) });
  await load();
  show("settings");
});

$("#int-run").addEventListener("click", () => loadInterest().catch((err) => alert(err.message)));

boot().catch((err) => {
  $("#lock-error").hidden = false;
  $("#lock-error").textContent = err.message;
});
