let biz = null;

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function monthIso() {
  return new Date().toISOString().slice(0, 7);
}

function dough(key, canvas, labels, values) {
  destroyChart(key);
  if (!labels.length) return;
  charts[key] = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: ["#2f9e5f", "#7ed9a2", "#1f7a4d", "#4aa3d9", "#e8b86d", "#8bbf9a", "#a8e6bf", "#5d7a64"],
      }],
    },
    options: {
      plugins: { legend: { labels: { color: "#16301c" } } },
      cutout: "62%",
    },
  });
}

function bizRows(rows, mount, incoming) {
  if (!rows.length) {
    mount.innerHTML = `<p class="empty">Nothing here for this month yet.</p>`;
    return;
  }
  const ordered = [...rows].reverse();
  mount.innerHTML = ordered
    .map((row) => {
      const title = row.stream || row.category || row.party || row.kind;
      const extra = [row.party, row.vehicle, row.mode, row.reference, row.notes].filter(Boolean).join(" · ");
      const money = Number(row.amount) || 0;
      const showAmt = row.kind !== "note";
      return `<div class="txn" data-id="${row.id}">
        <time>${row.date || ""}</time>
        <div>
          <b><span class="chip ${incoming ? "credit" : ""}">${title}</span>${row.party && row.kind !== "note" ? row.party : ""}</b>
          <small>${extra || "—"}</small>
        </div>
        ${showAmt ? `<span class="amt ${incoming ? "in" : "out"}">${incoming ? "+" : "−"}${inr(Math.abs(money))}</span>` : ""}
        <button type="button" class="mini-del" data-id="${row.id}">Remove</button>
      </div>`;
    })
    .join("");
  $$(".mini-del", mount).forEach((el) => {
    el.addEventListener("click", () => removeBiz(el.dataset.id));
  });
}

function registerRows(rows, mount, key, line) {
  if (!rows.length) {
    mount.innerHTML = `<p class="empty">None saved yet.</p>`;
    return;
  }
  mount.innerHTML = rows
    .map((row) => `<div class="txn">
      <time></time>
      <div><b>${row.name || "Unnamed"}</b><small>${line(row)}</small></div>
      <button type="button" class="mini-del" data-id="${row.id}" data-key="${key}">Remove</button>
    </div>`)
    .join("");
  $$(".mini-del", mount).forEach((el) => {
    el.addEventListener("click", () => removeRegister(el.dataset.key, el.dataset.id));
  });
}

async function removeBiz(id) {
  if (!id || !confirm("Remove this row?")) return;
  await api(`/api/business/entries/${id}`, { method: "DELETE" });
  await loadBiz();
}

async function removeRegister(key, id) {
  if (!id || !confirm("Remove this record?")) return;
  await api(`/api/business/registers/${key}/${id}`, { method: "DELETE" });
  await loadBiz();
}

function formPayload(form, extra) {
  return { ...Object.fromEntries(new FormData(form).entries()), ...extra };
}

function stampDates() {
  $$("form[id^='biz-'] input[type=date]").forEach((el) => {
    if (!el.value) el.value = todayIso();
  });
}

async function loadBiz() {
  const month = $("#biz-month").value || monthIso();
  if (!$("#biz-month").value) $("#biz-month").value = month;
  biz = await api(`/api/business?month=${encodeURIComponent(month)}`);
  const active = document.querySelector("#smt-nav button.active");
  if (document.body.dataset.ws === "smt") {
    renderBiz((active && active.dataset.view) || "smt-home");
  }
}

function renderBiz(view) {
  if (!biz) return;
  stampDates();
  if (view === "smt-home") renderBizHome();
  if (view === "smt-income") bizRows(biz.summary.incomes, $("#biz-income-list"), true);
  if (view === "smt-rac") renderRac();
  if (view === "smt-ets") renderEts();
  if (view === "smt-other") renderOther();
  if (view === "smt-drivers") renderDrivers();
  if (view === "smt-people") renderPeople();
  if (view === "smt-savings") {
    const pots = Object.entries(biz.summary.savings_by_pot || {});
    $("#biz-pots").innerHTML = pots.length
      ? pots.map(([k, v]) => `<li><span>${k}</span><b>${inr(v)}</b></li>`).join("")
      : `<li><span>No pots this month</span><b>—</b></li>`;
    bizRows(biz.summary.savings, $("#biz-save-list"), true);
  }
  if (view === "smt-notes") {
    bizRows(biz.summary.all_notes || [], $("#biz-note-list"), false);
  }
}

function renderBizHome() {
  const s = biz.summary;
  $("#biz-hero").innerHTML = [
    ["Income", s.income_total, "in"],
    ["Expenses", s.expense_total, "out"],
    ["Net this month", s.net, s.net >= 0 ? "in" : "out"],
  ].map(([k, v, cls]) => `<div><span>${k}</span><b class="${cls === "in" ? "amt in" : "amt out"}">${inr(v)}</b></div>`).join("");

  const streams = Object.entries(s.income_by_stream || {});
  dough("biz-in", $("#biz-in-chart"), streams.map(([k]) => k), streams.map(([, v]) => v));
  const cats = Object.entries(s.expense_by_category || {});
  dough("biz-out", $("#biz-out-chart"), cats.map(([k]) => k), cats.map(([, v]) => v));

  const streamOrder = ["Employee transport", "Insurance", "RAC"];
  $("#biz-streams").innerHTML = streamOrder
    .map((name) => `<li><span>${name}</span><b>${inr((s.income_by_stream || {})[name] || 0)}</b></li>`)
    .concat([["Saved this month", s.savings_total]].map(([k, v]) => `<li><span>${k}</span><b>${inr(v)}</b></li>`))
    .join("");

  $("#biz-rac").innerHTML = [
    ["RAC billed (income)", s.rac_income],
    ["RAC paid to drivers", s.rac_payout],
    ["RAC cash still held", s.rac_gap],
    ["ETS spend", s.ets_total],
    ["Insurance / other spend", s.other_total],
    ["Overdue RAC (48h)", (s.rac_sla || {}).overdue || 0],
  ].map(([k, v]) => `<li><span>${k}</span><b>${typeof v === "number" && String(k).includes("Overdue") ? v : inr(v)}</b></li>`).join("");

  const recent = [...(biz.entries || [])]
    .filter((row) => ["income", "expense", "saving"].includes(row.kind))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
    .slice(-8);
  const incoming = (row) => row.kind === "income" || row.kind === "saving";
  if (!recent.length) {
    $("#biz-recent").innerHTML = `<p class="empty">Post the first income or expense from the Travels tabs.</p>`;
  } else {
    $("#biz-recent").innerHTML = [...recent].reverse().map((row) => {
      const title = row.stream || row.category || row.kind;
      const extra = [row.party, row.vehicle].filter(Boolean).join(" · ");
      return `<div class="txn">
        <time>${row.date || ""}</time>
        <div><b><span class="chip ${incoming(row) ? "credit" : ""}">${title}</span>${row.party || ""}</b><small>${extra || "—"}</small></div>
        <span class="amt ${incoming(row) ? "in" : "out"}">${incoming(row) ? "+" : "−"}${inr(Math.abs(Number(row.amount) || 0))}</span>
      </div>`;
    }).join("");
  }

  const storage = $("#biz-storage");
  if (storage) {
    storage.innerHTML = biz.zoho_configured
      ? `<p class="label">Cloud</p><p>Same Zoho workbook. Create a worksheet named <b>SMT Books</b> (exact name), then initialise so Travels rows stay off the OD Usage tab.</p><button id="smt-zoho-init-home" class="primary" type="button">Initialise SMT Books</button>`
      : `<p class="label">This device</p><p>Travels books are saved locally. Connect Zoho in Settings (OD 99L) if you want the same cloud sheet.</p>`;
    const btn = $("#smt-zoho-init-home");
    if (btn) btn.onclick = initSmtSheet;
  }
}

const SLA_LABEL = {
  pending: "Within 48h",
  overdue: "Overdue",
  on_time: "Paid on time",
  late: "Paid late",
  historical: "Paid (history)",
  unknown: "Check date",
};

function racRate(vehicle, pkg, hours, kms) {
  const table = (biz.rates || {})[vehicle] || {};
  const named = { "4hrs / 40km": "4-40", "8hrs / 80km": "8-80", "12hrs / 120km": "12-120", Airport: "Airport", Outstation: "Outstation", Drop: "Drop" };
  return Number(table[named[pkg] || `${hours}-${kms}`] || 0);
}

function fillRacSelects() {
  const hours = $("#rac-hours");
  const kms = $("#rac-kms");
  if (!hours.dataset.ready) {
    hours.innerHTML = Array.from({ length: 16 }, (_, i) => `<option value="${i + 1}">${i + 1} hrs</option>`).join("");
    kms.innerHTML = Array.from({ length: 40 }, (_, i) => `<option value="${(i + 1) * 10}">${(i + 1) * 10} km</option>`).join("");
    hours.dataset.ready = "1";
    hours.value = "12";
    kms.value = "120";
  }
}

function syncRacPackage() {
  const pkg = $("#rac-package").value;
  const map = { "4hrs / 40km": [4, 40], "8hrs / 80km": [8, 80], "12hrs / 120km": [12, 120] };
  if (map[pkg]) {
    $("#rac-hours").value = String(map[pkg][0]);
    $("#rac-kms").value = String(map[pkg][1]);
  }
  const amt = racRate($("#rac-booking-form [name=vehicle]").value, pkg, $("#rac-hours").value, $("#rac-kms").value);
  if (amt > 0) $("#rac-amount").value = amt;
}

function renderRates() {
  const rates = biz.rates || {};
  const keys = ["4-40", "8-80", "12-120", "Airport", "Outstation", "Drop"];
  const labels = { "4-40": "4h/40km", "8-80": "8h/80km", "12-120": "12h/120km", Airport: "Airport", Outstation: "Outstation", Drop: "Drop" };
  $("#rac-rates-grid").innerHTML = ["Sedan", "Ertiga", "Crysta"].map((vehicle) => {
    const cells = keys.map((key) => `<label>${vehicle} · ${labels[key]}<input type="number" min="0" step="1" name="${vehicle}::${key}" value="${Number((rates[vehicle] || {})[key] || 0)}" /></label>`).join("");
    return `<div class="rate-row">${cells}</div>`;
  }).join("");
}

function renderRac() {
  fillRacSelects();
  renderRates();
  const s = biz.summary;
  const sla = s.rac_sla || {};
  $("#rac-sla-hero").innerHTML = [
    ["Bookings", (s.bookings || []).length],
    ["Unpaid / pending", (sla.pending || 0) + (sla.unknown || 0)],
    ["Overdue 48h", sla.overdue || 0],
    ["Paid on time", (sla.on_time || 0) + (sla.historical || 0)],
    ["Paid late", sla.late || 0],
    ["Paid this month", s.rac_payout],
  ].map(([k, v]) => `<div><span>${k}</span><b>${k === "Paid this month" ? inr(v) : v}</b></div>`).join("");

  ["Sedan", "Ertiga", "Crysta"].forEach((vehicle) => {
    const mount = $(`#rac-${vehicle.toLowerCase()}`);
    const rows = (s.bookings || []).filter((row) => row.vehicle === vehicle);
    const stats = (s.rac_vehicles || {})[vehicle] || {};
    const head = `<p class="muted">${stats.count || 0} trips · unpaid ${stats.unpaid || 0} · overdue ${stats.overdue || 0} · paid ${inr(stats.paid || 0)}</p>`;
    if (!rows.length) {
      mount.innerHTML = `${head}<p class="empty">No ${vehicle} bookings this month. Upload the RAC Excel or add one above.</p>`;
      return;
    }
    const ordered = [...rows].sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const shown = ordered.slice(0, 80);
    const more = ordered.length > 80 ? `<p class="muted">Showing 80 of ${ordered.length} this month. Change month above to page through.</p>` : "";
    mount.innerHTML = head + more + shown.map((row) => {
      const sla = row.sla || "unknown";
      const paid = Boolean(row.paid_at);
      const duty = row.package === "Custom" ? `${row.duty_hours}h / ${row.duty_kms}km` : row.package;
      const extra = [row.booking_id, row.cab_reg, duty, row.pickup, row.employee].filter(Boolean).join(" · ");
      return `<div class="txn rac-row">
        <time>${row.date || ""} ${row.pickup_time || ""}</time>
        <div>
          <b><span class="chip sla-${sla}">${SLA_LABEL[sla] || sla}</span>${row.driver || "Driver"}</b>
          <small>${extra}</small>
        </div>
        <span class="amt ${paid ? "in" : "out"}">${paid ? inr(row.amount) : (Number(row.amount) ? inr(row.amount) : "Pay")}</span>
        ${paid ? "" : `<button type="button" class="primary mini-pay" data-id="${row.id}">Paid</button>`}
        <button type="button" class="mini-del" data-booking="${row.id}">Remove</button>
      </div>`;
    }).join("");
    $$(".mini-pay", mount).forEach((el) => el.addEventListener("click", () => payRac(el.dataset.id)));
    $$("[data-booking]", mount).forEach((el) => el.addEventListener("click", () => removeRac(el.dataset.booking)));
  });
}

async function payRac(id) {
  const row = (biz.summary.bookings || []).find((item) => item.id === id);
  if (!row) return;
  const suggested = Number(row.amount) || racRate(row.vehicle, row.package, row.duty_hours, row.duty_kms);
  const typed = prompt(`Amount paid to ${row.driver || "driver"}`, suggested || "");
  if (typed === null) return;
  const amount = Number(typed);
  if (!(amount > 0)) return alert("Enter the driver pay.");
  await api(`/api/business/bookings/${id}/pay`, {
    method: "POST",
    body: JSON.stringify({ amount, paid_at: new Date().toISOString().slice(0, 16), mode: "UPI" }),
  });
  await loadBiz();
}

async function removeRac(id) {
  if (!id || !confirm("Remove this RAC booking?")) return;
  await api(`/api/business/bookings/${id}`, { method: "DELETE" });
  await loadBiz();
}

function renderEts() {
  const s = biz.summary;
  $("#ets-hero").innerHTML = [
    ["ETS income", s.ets_income],
    ["ETS expenses", s.ets_total],
    ["ETS net", (s.ets_income || 0) - (s.ets_total || 0)],
  ].map(([k, v]) => `<div><span>${k}</span><b class="${String(k).includes("expense") ? "amt out" : "amt in"}">${inr(v)}</b></div>`).join("");
  bizRows(s.ets_expenses || [], $("#ets-list"), false);
}

function renderOther() {
  const s = biz.summary;
  $("#other-hero").innerHTML = [
    ["Insurance income", s.insurance_income],
    ["Insurance / other spend", s.other_total],
    ["Net", (s.insurance_income || 0) - (s.other_total || 0)],
  ].map(([k, v]) => `<div><span>${k}</span><b>${inr(v)}</b></div>`).join("");
  bizRows(s.other_expenses || [], $("#other-list"), false);
}

function renderDrivers() {
  const s = biz.summary;
  $("#biz-driver-hero").innerHTML = [
    ["Paid to drivers", s.driver_total],
    ["RAC booking payouts", s.rac_payout],
    ["Drivers this month", (s.drivers || []).length],
  ].map(([k, v]) => `<div><span>${k}</span><b>${typeof v === "number" && k !== "Drivers this month" ? inr(v) : v}</b></div>`).join("");

  const rows = s.drivers || [];
  if (!rows.length) {
    $("#biz-driver-list").innerHTML = `<p class="empty">Pay a driver from Expenses — salary, diesel advance, or RAC booking payment. Use the driver name in Paid to.</p>`;
    return;
  }
  $("#biz-driver-list").innerHTML = rows.map((row) => `<div class="txn">
    <time></time>
    <div>
      <b>${row.name}</b>
      <small>Salary ${inr(row.salary)} · Diesel ${inr(row.diesel)} · RAC ${inr(row.rac)}</small>
    </div>
    <span class="amt out">${inr(row.paid)}</span>
  </div>`).join("");
}

function renderPeople() {
  registerRows(biz.summary.partners || biz.partners || [], $("#biz-partner-list"), "partners", (row) =>
    `Share ${row.share_pct || 0}% · paid this month ${inr(row.paid_month || 0)}${row.notes ? ` · ${row.notes}` : ""}`);
  registerRows(biz.loans || [], $("#biz-loan-list"), "loans", (row) =>
    `${row.lender || "Lender"} · EMI ${inr(row.emi)} · outstanding ${inr(row.outstanding)}`);
  registerRows(biz.cards || [], $("#biz-card-list"), "cards", (row) =>
    `${row.last4 ? `•••• ${row.last4}` : "Card"} · limit ${inr(row.limit)} · due ${inr(row.outstanding)}`);
}

async function initSmtSheet() {
  try {
    await api("/api/business/zoho", { method: "POST" });
    alert("SMT Books is ready. New Travels rows will write there.");
    await loadBiz();
  } catch (err) {
    alert(err.message);
  }
}

function bindBiz() {
  if (!$("#biz-month")) return;
  $("#biz-month").addEventListener("change", () => loadBiz().catch((err) => alert(err.message)));

  const posts = [
    ["#biz-income-form", { kind: "income" }],
    ["#biz-ets-form", { kind: "expense", extra: "ETS" }],
    ["#biz-other-form", { kind: "expense", extra: "Other" }],
    ["#biz-save-form", { kind: "saving" }],
    ["#biz-note-form", { kind: "note", amount: 0, category: "Note" }],
  ];
  posts.forEach(([sel, extra]) => {
    $(sel).addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await api("/api/business/entries", { method: "POST", body: JSON.stringify(formPayload(ev.target, extra)) });
        ev.target.reset();
        stampDates();
        await loadBiz();
      } catch (err) {
        alert(err.message);
      }
    });
  });

  [
    ["#biz-partner-form", "partners"],
    ["#biz-loan-form", "loans"],
    ["#biz-card-form", "cards"],
  ].forEach(([sel, key]) => {
    $(sel).addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await api(`/api/business/registers/${key}`, { method: "POST", body: JSON.stringify(formPayload(ev.target, {})) });
        ev.target.reset();
        await loadBiz();
      } catch (err) {
        alert(err.message);
      }
    });
  });

  fillRacSelects();
  $("#rac-package").addEventListener("change", syncRacPackage);
  $("#rac-booking-form [name=vehicle]").addEventListener("change", syncRacPackage);
  $("#rac-hours").addEventListener("change", syncRacPackage);
  $("#rac-kms").addEventListener("change", syncRacPackage);

  $("#rac-booking-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await api("/api/business/bookings", { method: "POST", body: JSON.stringify(formPayload(ev.target, {})) });
      ev.target.reset();
      stampDates();
      fillRacSelects();
      $("#rac-hours").value = "12";
      $("#rac-kms").value = "120";
      await loadBiz();
    } catch (err) {
      alert(err.message);
    }
  });

  $("#rac-rates-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const rates = { Sedan: {}, Ertiga: {}, Crysta: {} };
    new FormData(ev.target).forEach((value, name) => {
      if (!name.includes("::")) return;
      const [vehicle, key] = name.split("::");
      rates[vehicle][key] = value;
    });
    await api("/api/business/rates", { method: "PUT", body: JSON.stringify({ rates }) });
    await loadBiz();
  });

  $("#rac-import-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("#rac-import-msg");
    msg.textContent = "Reading Excel…";
    const body = new FormData(ev.target);
    try {
      const res = await fetch("/admin/workspace/api/business/bookings/import", { credentials: "same-origin", method: "POST", body });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Import failed");
      msg.textContent = `Imported ${data.imported} bookings` + (data.skipped ? `, skipped ${data.skipped} duplicates.` : ".");
      ev.target.reset();
      await loadBiz();
    } catch (err) {
      msg.textContent = err.message;
    }
  });
}

bindBiz();
