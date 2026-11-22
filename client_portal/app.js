(() => {
  const app = document.getElementById("app");
  const state = {
    user: null,
    company: null,
    view: "dashboard",
    loading: false,
    error: "",
    notice: "",
    data: {},
  };

  async function api(path, options = {}) {
    const opts = {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.headers || {}) },
      ...options,
    };
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    let response;
    try {
      response = await fetch(path, opts);
    } catch (_) {
      const err = new Error("Cannot reach the server. Check your connection and try again.");
      err.status = 0;
      throw err;
    }
    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }
    if (response.status === 401) {
      state.user = null;
      state.company = null;
      const err = new Error(payload.message || "Session expired. Sign in again.");
      err.status = 401;
      throw err;
    }
    if (!response.ok || payload.success === false) {
      const err = new Error(payload.message || "Request failed.");
      err.status = response.status;
      throw err;
    }
    return payload;
  }

  function money(value) {
    const n = Number(value || 0);
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(n);
  }

  function chip(status) {
    const s = String(status || "").toLowerCase();
    let cls = "chip";
    if (["cancelled", "reversed", "rejected"].includes(s)) cls += " danger";
    else if (["unassigned", "assigned", "outstanding", "pending"].includes(s)) cls += " warn";
    else if (["completed", "paid", "accepted", "recorded"].includes(s)) cls += " ok";
    return `<span class="${cls}">${escapeHtml(status || "—")}</span>`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setView(view) {
    state.view = view;
    state.error = "";
    state.notice = "";
    render();
    loadView();
  }

  async function restore() {
    try {
      const session = await api("/api/client/session");
      state.user = session.user;
      state.company = session.company;
      setView("dashboard");
    } catch (_) {
      state.user = null;
      renderLogin();
    }
  }

  function renderLogin() {
    app.innerHTML = `
      <div class="login-shell">
        <form class="login-card" id="login-form">
          <div class="brand">
            <h1>Shree Maruthi Travels</h1>
            <p>Client portal sign-in</p>
          </div>
          <div class="form-grid" style="grid-template-columns:1fr">
            <label>Email
              <input name="email" type="email" autocomplete="username" required />
            </label>
            <label>Password
              <input name="password" type="password" autocomplete="current-password" required minlength="8" />
            </label>
          </div>
          <div id="login-msg"></div>
          <div class="actions">
            <button class="btn" type="submit" id="login-btn">Sign in</button>
          </div>
        </form>
      </div>`;
    document.getElementById("login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.target;
      const btn = document.getElementById("login-btn");
      const msg = document.getElementById("login-msg");
      btn.disabled = true;
      msg.innerHTML = "";
      try {
        const payload = await api("/api/client/login", {
          method: "POST",
          body: {
            email: form.email.value.trim(),
            password: form.password.value,
          },
        });
        state.user = payload.user;
        state.company = payload.company;
        setView("dashboard");
      } catch (error) {
        msg.innerHTML = `<div class="msg error">${escapeHtml(error.message)}</div>`;
        btn.disabled = false;
      }
    });
  }

  function shell(content) {
    const unread = state.data.notifications?.unread_count || 0;
    const notifLabel = unread > 0 ? `Alerts (${unread})` : "Alerts";
    const items = [
      ["dashboard", "Dashboard"],
      ["bookings", "Bookings"],
      ["trips", "Trips"],
      ["invoices", "Invoices"],
      ["payments", "Payments"],
      ["notifications", notifLabel],
      ["profile", "Account"],
      ["support", "Support"],
    ];
    return `
      <div class="shell">
        <aside class="nav">
          <div class="brand-mini">Shree Maruthi Travels<br/><small style="opacity:.8">Client Portal</small></div>
          ${items.map(([id, label]) =>
            `<button data-nav="${id}" class="${state.view === id ? "active" : ""}">${label}</button>`
          ).join("")}
          <div class="spacer"></div>
          <button data-nav="logout">Sign out</button>
        </aside>
        <section class="main">
          <div class="topbar">
            <div>
              <h2>${escapeHtml(titleFor(state.view))}</h2>
              <div style="color:var(--muted);font-size:.92rem">
                ${escapeHtml(state.company?.name || "")}
                ${state.user?.full_name ? " · " + escapeHtml(state.user.full_name) : ""}
              </div>
            </div>
          </div>
          ${state.error ? `<div class="msg error">${escapeHtml(state.error)}</div>` : ""}
          ${state.notice ? `<div class="msg ok">${escapeHtml(state.notice)}</div>` : ""}
          ${state.loading ? `<div class="empty">Loading…</div>` : content}
        </section>
      </div>`;
  }

  function titleFor(view) {
    return ({
      dashboard: "Dashboard",
      bookings: "Bookings",
      trips: "Trip history",
      invoices: "Invoices",
      payments: "Payments",
      notifications: "Alerts",
      profile: "Account",
      support: "Support",
      booking_new: "New booking request",
      booking_detail: "Booking details",
      invoice_detail: "Invoice details",
    })[view] || "Client portal";
  }

  function render() {
    if (!state.user) {
      renderLogin();
      return;
    }
    let content = `<div class="empty">Loading…</div>`;
    if (!state.loading) {
      if (state.view === "dashboard") content = renderDashboard();
      else if (state.view === "bookings") content = renderBookings();
      else if (state.view === "booking_new") content = renderBookingForm();
      else if (state.view === "booking_detail") content = renderBookingDetail();
      else if (state.view === "trips") content = renderTrips();
      else if (state.view === "invoices") content = renderInvoices();
      else if (state.view === "invoice_detail") content = renderInvoiceDetail();
      else if (state.view === "payments") content = renderPayments();
      else if (state.view === "notifications") content = renderNotifications();
      else if (state.view === "profile") content = renderProfile();
      else if (state.view === "support") content = renderSupport();
    }
    app.innerHTML = shell(content);
    app.querySelectorAll("[data-nav]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-nav");
        if (id === "logout") {
          await api("/api/client/logout", { method: "POST" }).catch(() => {});
          state.user = null;
          state.company = null;
          renderLogin();
          return;
        }
        setView(id);
      });
    });
    bindViewHandlers();
  }

  async function loadView() {
    if (!state.user) return;
    state.loading = true;
    render();
    try {
      if (state.view === "dashboard") {
        state.data.dashboard = await api("/api/client/dashboard");
      } else if (state.view === "bookings") {
        const status = state.data.bookingStatus || "";
        const search = state.data.bookingSearch || "";
        const q = new URLSearchParams();
        if (status) q.set("status", status);
        if (search) q.set("search", search);
        state.data.bookings = await api("/api/client/bookings?" + q.toString());
      } else if (state.view === "booking_new") {
        state.data.session = await api("/api/client/session");
      } else if (state.view === "booking_detail" && state.data.bookingId) {
        state.data.booking = await api("/api/client/bookings/" + state.data.bookingId);
      } else if (state.view === "trips") {
        const filter = state.data.tripFilter || "all";
        state.data.trips = await api("/api/client/trips?filter=" + encodeURIComponent(filter));
      } else if (state.view === "invoices") {
        state.data.invoices = await api("/api/client/invoices");
      } else if (state.view === "invoice_detail" && state.data.invoiceId) {
        state.data.invoice = await api("/api/client/invoices/" + state.data.invoiceId);
      } else if (state.view === "payments") {
        state.data.payments = await api("/api/client/payments");
      } else if (state.view === "notifications") {
        try {
          state.data.notifications = await api("/api/client/notifications");
        } catch (error) {
          state.data.notifications = { notifications: [], unread_count: 0, unavailable: true, message: error.message };
        }
      } else if (state.view === "profile") {
        state.data.session = await api("/api/client/session");
      } else if (state.view === "support") {
        state.data.support = await api("/api/client/support");
      }
      state.error = "";
    } catch (error) {
      state.error = error.message;
      if (error.status === 401) {
        renderLogin();
        return;
      }
    } finally {
      state.loading = false;
      render();
    }
  }

  function renderDashboard() {
    const d = state.data.dashboard || {};
    return `
      <div class="grid stats">
        <div class="card stat"><strong>${money(d.outstanding_balance)}</strong><span>Outstanding balance</span></div>
        <div class="card stat"><strong>${(d.upcoming_bookings || []).length}</strong><span>Upcoming bookings shown</span></div>
        <div class="card stat"><strong>${(d.recent_completed || []).length}</strong><span>Recent completed</span></div>
      </div>
      <div class="actions">
        <button class="btn" data-action="goto-bookings">View bookings</button>
        <button class="btn secondary" data-action="goto-invoices">View invoices</button>
        <button class="btn secondary" data-action="new-booking">Request booking</button>
      </div>
      <div class="grid" style="margin-top:1rem;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
        <div class="card">
          <h3>Upcoming bookings</h3>
          ${listBookingsMini(d.upcoming_bookings)}
        </div>
        <div class="card">
          <h3>Recent payments</h3>
          ${(d.recent_payments || []).length ? `
            <div class="table-wrap"><table>
              <thead><tr><th>Invoice</th><th>Amount</th><th>Date</th><th>Status</th></tr></thead>
              <tbody>
                ${(d.recent_payments || []).map((p) => `
                  <tr>
                    <td>${escapeHtml(p.invoice_number)}</td>
                    <td>${money(p.amount)}</td>
                    <td>${escapeHtml(p.paid_on || "—")}</td>
                    <td>${chip(p.status)}</td>
                  </tr>`).join("")}
              </tbody>
            </table></div>` : `<div class="empty">No recent payments.</div>`}
        </div>
      </div>`;
  }

  function listBookingsMini(rows) {
    if (!rows || !rows.length) return `<div class="empty">No bookings in this list.</div>`;
    return `<div class="table-wrap"><table>
      <thead><tr><th>Reference</th><th>Date</th><th>Status</th></tr></thead>
      <tbody>
        ${rows.map((b) => `
          <tr>
            <td><button class="linkish" data-booking="${escapeHtml(b.id)}">${escapeHtml(b.booking_reference)}</button></td>
            <td>${escapeHtml(b.trip_date || "—")}</td>
            <td>${chip(b.status)}</td>
          </tr>`).join("")}
      </tbody>
    </table></div>`;
  }

  function renderBookings() {
    const rows = state.data.bookings?.bookings || [];
    return `
      <div class="toolbar">
        <select id="booking-status">
          <option value="">All statuses</option>
          ${["unassigned","assigned","accepted","started","completed","cancelled"].map((s) =>
            `<option value="${s}" ${state.data.bookingStatus === s ? "selected" : ""}>${s}</option>`
          ).join("")}
        </select>
        <input id="booking-search" placeholder="Search reference / passenger / pickup" value="${escapeHtml(state.data.bookingSearch || "")}" />
        <button class="btn secondary" data-action="filter-bookings">Filter</button>
        <button class="btn" data-action="new-booking">New request</button>
      </div>
      <div class="card">
        ${rows.length ? `
          <div class="table-wrap"><table>
            <thead><tr><th>Reference</th><th>Date</th><th>Pickup</th><th>Passenger</th><th>Status</th></tr></thead>
            <tbody>
              ${rows.map((b) => `
                <tr>
                  <td><button class="linkish" data-booking="${escapeHtml(b.id)}">${escapeHtml(b.booking_reference)}</button></td>
                  <td>${escapeHtml(b.trip_date || "—")} ${escapeHtml(b.pickup_time || "")}</td>
                  <td>${escapeHtml(b.pickup_location || "—")}</td>
                  <td>${escapeHtml(b.passenger_name || "—")}</td>
                  <td>${chip(b.status)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<div class="empty">No bookings found.</div>`}
      </div>`;
  }

  function renderBookingForm() {
    const branches = state.data.session?.company?.branches || [];
    return `
      <div class="card">
        <form id="booking-form" class="form-grid">
          <label>Branch
            <select name="branch_code" required>
              <option value="">Select city</option>
              ${branches.map((b) => `<option value="${escapeHtml(b.code)}">${escapeHtml(b.name || b.code)}</option>`).join("")}
            </select>
          </label>
          <label>Trip date
            <input name="trip_date" type="date" required />
          </label>
          <label>Pickup time
            <input name="pickup_time" type="time" />
          </label>
          <label>Pickup location
            <input name="pickup_location" required />
          </label>
          <label>Route / drop
            <input name="route" />
          </label>
          <label>Passenger name
            <input name="passenger_name" />
          </label>
          <label>Passenger phone
            <input name="passenger_phone" />
          </label>
          <label>Duty type
            <input name="duty_type" placeholder="Airport / Local / Outstation" />
          </label>
          <label>Cab type
            <input name="cab_type" placeholder="Sedan / SUV" />
          </label>
          <label style="grid-column:1/-1">Remarks
            <textarea name="remarks" rows="3"></textarea>
          </label>
          <div class="actions" style="grid-column:1/-1">
            <button class="btn" type="submit">Submit request</button>
            <button class="btn secondary" type="button" data-action="goto-bookings">Cancel</button>
          </div>
        </form>
        <p class="empty">Requests stay unassigned until a supervisor assigns a driver and vehicle.</p>
      </div>`;
  }

  function renderBookingDetail() {
    const b = state.data.booking?.booking;
    const trip = state.data.booking?.trip;
    if (!b) return `<div class="empty">Booking not found.</div>`;
    const canEdit = b.origin === "client_request" && b.status === "unassigned";
    return `
      <div class="card">
        <div class="actions" style="margin-top:0">
          <button class="btn secondary" data-action="goto-bookings">Back</button>
          ${canEdit ? `<button class="btn danger" data-action="cancel-booking" data-id="${escapeHtml(b.id)}">Cancel request</button>` : ""}
        </div>
        <p><strong>${escapeHtml(b.booking_reference)}</strong> ${chip(b.status)}</p>
        <div class="form-grid">
          <div><span style="color:var(--muted)">Date</span><div>${escapeHtml(b.trip_date || "—")} ${escapeHtml(b.pickup_time || "")}</div></div>
          <div><span style="color:var(--muted)">Pickup</span><div>${escapeHtml(b.pickup_location || "—")}</div></div>
          <div><span style="color:var(--muted)">Route</span><div>${escapeHtml(b.route || "—")}</div></div>
          <div><span style="color:var(--muted)">Passenger</span><div>${escapeHtml(b.passenger_name || "—")}</div></div>
          <div><span style="color:var(--muted)">Phone</span><div>${escapeHtml(b.passenger_phone || "—")}</div></div>
          <div><span style="color:var(--muted)">Branch</span><div>${escapeHtml(b.branch_code || "—")}</div></div>
        </div>
        ${trip ? `
          <h3 style="margin-top:1.25rem">Assignment</h3>
          <div class="form-grid">
            <div><span style="color:var(--muted)">Driver</span><div>${escapeHtml(trip.driver_name || "Not assigned")}</div></div>
            <div><span style="color:var(--muted)">Driver phone</span><div>${escapeHtml(trip.driver_phone || "—")}</div></div>
            <div><span style="color:var(--muted)">Vehicle</span><div>${escapeHtml(trip.vehicle_registration || "—")} ${escapeHtml(trip.vehicle_model || "")}</div></div>
            <div><span style="color:var(--muted)">Duty status</span><div>${chip(trip.duty_status)}</div></div>
          </div>` : ""}
        ${canEdit ? `
          <h3 style="margin-top:1.25rem">Edit request</h3>
          <form id="edit-booking-form" class="form-grid">
            <label>Trip date<input name="trip_date" type="date" value="${escapeHtml(b.trip_date || "")}" /></label>
            <label>Pickup location<input name="pickup_location" value="${escapeHtml(b.pickup_location || "")}" /></label>
            <label>Route<input name="route" value="${escapeHtml(b.route || "")}" /></label>
            <label>Passenger<input name="passenger_name" value="${escapeHtml(b.passenger_name || "")}" /></label>
            <div class="actions" style="grid-column:1/-1">
              <button class="btn" type="submit">Save changes</button>
            </div>
          </form>` : `<p class="empty">Assigned or non-request bookings are managed by supervisors.</p>`}
      </div>`;
  }

  function renderTrips() {
    const rows = state.data.trips?.trips || [];
    return `
      <div class="toolbar">
        <select id="trip-filter">
          ${[["all","All"],["upcoming","Upcoming"],["assigned","Assigned"],["completed","Completed"]].map(([v,l]) =>
            `<option value="${v}" ${state.data.tripFilter === v ? "selected" : ""}>${l}</option>`
          ).join("")}
        </select>
        <button class="btn secondary" data-action="filter-trips">Filter</button>
      </div>
      <div class="card">
        ${rows.length ? `
          <div class="table-wrap"><table>
            <thead><tr><th>Date</th><th>Pickup</th><th>Driver</th><th>Vehicle</th><th>Status</th></tr></thead>
            <tbody>
              ${rows.map((t) => `
                <tr>
                  <td>${escapeHtml(t.trip_date || "—")}</td>
                  <td>${escapeHtml(t.pickup_location || "—")}</td>
                  <td>${escapeHtml(t.driver_name || "—")}</td>
                  <td>${escapeHtml(t.vehicle_registration || "—")}</td>
                  <td>${chip(t.duty_status)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<div class="empty">No trips found.</div>`}
      </div>
      <p class="empty">Live GPS tracking is not shown. Assignment details appear only when authorized for client viewing.</p>`;
  }

  function renderInvoices() {
    const rows = state.data.invoices?.invoices || [];
    return `
      <div class="card">
        ${rows.length ? `
          <div class="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Issued</th><th>Total</th><th>Outstanding</th><th>Status</th></tr></thead>
            <tbody>
              ${rows.map((i) => `
                <tr>
                  <td><button class="linkish" data-invoice="${escapeHtml(i.id)}">${escapeHtml(i.invoice_number)}</button></td>
                  <td>${escapeHtml(i.issued_at || "—")}</td>
                  <td>${money(i.total_amount)}</td>
                  <td>${money(i.outstanding_amount)}</td>
                  <td>${chip(i.status)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<div class="empty">No issued invoices.</div>`}
      </div>`;
  }

  function renderInvoiceDetail() {
    const inv = state.data.invoice?.invoice;
    if (!inv) return `<div class="empty">Invoice not found.</div>`;
    return `
      <div class="card" id="invoice-print">
        <div class="actions" style="margin-top:0">
          <button class="btn secondary" data-action="goto-invoices">Back</button>
          <button class="btn" data-action="print-invoice">Print / Save PDF</button>
        </div>
        <h3>${escapeHtml(inv.invoice_number)}</h3>
        <p>${escapeHtml(inv.company_name || "")} · ${chip(inv.status)}</p>
        <div class="form-grid">
          <div><span style="color:var(--muted)">Issued</span><div>${escapeHtml(inv.issued_at || "—")}</div></div>
          <div><span style="color:var(--muted)">Due</span><div>${escapeHtml(inv.due_date || "—")}</div></div>
          <div><span style="color:var(--muted)">Total</span><div>${money(inv.total_amount)}</div></div>
          <div><span style="color:var(--muted)">Paid</span><div>${money(inv.paid_amount)}</div></div>
          <div><span style="color:var(--muted)">Outstanding</span><div>${money(inv.outstanding_amount)}</div></div>
        </div>
        <h4>Line items</h4>
        <div class="table-wrap"><table>
          <thead><tr><th>Description</th><th>Amount</th></tr></thead>
          <tbody>
            ${(inv.lines || []).map((l) => `
              <tr><td>${escapeHtml(l.description)}</td><td>${money(l.amount)}</td></tr>
            `).join("") || `<tr><td colspan="2">No lines</td></tr>`}
          </tbody>
        </table></div>
      </div>`;
  }

  function renderPayments() {
    const rows = state.data.payments?.payments || [];
    return `
      <div class="card">
        ${rows.length ? `
          <div class="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Amount</th><th>Date</th><th>Method</th><th>Status</th></tr></thead>
            <tbody>
              ${rows.map((p) => `
                <tr>
                  <td>${escapeHtml(p.invoice_number)}</td>
                  <td>${money(p.amount)}</td>
                  <td>${escapeHtml(p.paid_on || "—")}</td>
                  <td>${escapeHtml(p.method || "—")}</td>
                  <td>${chip(p.status)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<div class="empty">No payments recorded.</div>`}
      </div>`;
  }

  function renderNotifications() {
    const payload = state.data.notifications || {};
    if (payload.unavailable) {
      return `<div class="card"><div class="empty">${escapeHtml(payload.message || "Alerts need migration 016 or are temporarily unavailable.")}</div></div>`;
    }
    const rows = payload.notifications || [];
    const unread = payload.unread_count || 0;
    return `
      <div class="actions" style="margin-top:0">
        <button class="btn secondary" data-action="refresh-notifications">Refresh</button>
        <span style="color:var(--muted)">${unread} unread</span>
      </div>
      <div class="card">
        ${rows.length ? rows.map((n) => `
          <div style="display:flex;justify-content:space-between;gap:1rem;padding:.75rem 0;border-bottom:1px solid #e8edf3">
            <div>
              <strong>${escapeHtml(n.title)}</strong>
              <div style="color:var(--muted);font-size:.92rem">${escapeHtml(n.body)}</div>
              <div style="color:var(--muted);font-size:.8rem">${escapeHtml(n.created_at || "")} · ${escapeHtml(n.kind || "")}</div>
            </div>
            <div class="actions" style="margin:0;flex-direction:column;align-items:flex-end">
              ${n.booking_id ? `<button class="btn secondary" data-booking="${escapeHtml(n.booking_id)}">Open booking</button>` : ""}
              ${n.invoice_id ? `<button class="btn secondary" data-invoice="${escapeHtml(n.invoice_id)}">Open invoice</button>` : ""}
              ${!n.read_at ? `<button class="btn" data-action="mark-notif-read" data-id="${escapeHtml(n.id)}">Mark read</button>` : `<span class="chip ok">Read</span>`}
            </div>
          </div>`).join("") : `<div class="empty">No alerts yet. Booking and invoice updates appear here after migration 016.</div>`}
      </div>`;
  }

  function renderProfile() {
    const u = state.data.session?.user || state.user || {};
    const c = state.data.session?.company || state.company || {};
    return `
      <div class="card">
        <h3>Company</h3>
        <p><strong>${escapeHtml(c.name || "")}</strong></p>
        <p style="color:var(--muted)">${escapeHtml(c.address || "")}</p>
        <h3>Your account</h3>
        <form id="profile-form" class="form-grid">
          <label>Full name<input name="full_name" value="${escapeHtml(u.full_name || "")}" required /></label>
          <label>Email<input value="${escapeHtml(u.email || "")}" disabled /></label>
          <label>Phone<input name="phone" value="${escapeHtml(u.phone || "")}" /></label>
          <div class="actions" style="grid-column:1/-1">
            <button class="btn" type="submit">Save profile</button>
          </div>
        </form>
        <p class="empty">Company association and privileged settings cannot be changed here.</p>
      </div>`;
  }

  function renderSupport() {
    const s = state.data.support?.support || {};
    return `
      <div class="card">
        <h3>${escapeHtml(s.company || "Shree Maruthi Travels")}</h3>
        <p>Phone: <a href="tel:${escapeHtml((s.phone || "").replace(/\s/g, ""))}">${escapeHtml(s.phone || "")}</a></p>
        <p>Email: <a href="mailto:${escapeHtml(s.email || "")}">${escapeHtml(s.email || "")}</a></p>
        <p>${escapeHtml(s.address || "")}</p>
        <p><a href="${escapeHtml(s.site_url || "#")}" target="_blank" rel="noopener">Website</a></p>
      </div>`;
  }

  function bindViewHandlers() {
    app.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", () => {
        const action = el.getAttribute("data-action");
        if (action === "goto-bookings") setView("bookings");
        if (action === "goto-invoices") setView("invoices");
        if (action === "new-booking") setView("booking_new");
        if (action === "filter-bookings") {
          state.data.bookingStatus = document.getElementById("booking-status")?.value || "";
          state.data.bookingSearch = document.getElementById("booking-search")?.value || "";
          setView("bookings");
        }
        if (action === "filter-trips") {
          state.data.tripFilter = document.getElementById("trip-filter")?.value || "all";
          setView("trips");
        }
        if (action === "print-invoice") window.print();
        if (action === "refresh-notifications") setView("notifications");
        if (action === "mark-notif-read") {
          const id = el.getAttribute("data-id");
          if (!id) return;
          api("/api/client/notifications/" + id + "/read", { method: "POST", body: {} })
            .then(() => setView("notifications"))
            .catch((error) => {
              state.error = error.message;
              render();
            });
        }
        if (action === "cancel-booking") {
          const id = el.getAttribute("data-id");
          if (!id || !confirm("Cancel this booking request?")) return;
          api("/api/client/bookings/" + id + "/cancel", { method: "POST" })
            .then(() => {
              state.notice = "Booking request cancelled.";
              state.data.bookingId = id;
              setView("booking_detail");
            })
            .catch((error) => {
              state.error = error.message;
              render();
            });
        }
      });
    });
    app.querySelectorAll("[data-booking]").forEach((el) => {
      el.addEventListener("click", () => {
        state.data.bookingId = el.getAttribute("data-booking");
        setView("booking_detail");
      });
    });
    app.querySelectorAll("[data-invoice]").forEach((el) => {
      el.addEventListener("click", () => {
        state.data.invoiceId = el.getAttribute("data-invoice");
        setView("invoice_detail");
      });
    });
    const bookingForm = document.getElementById("booking-form");
    if (bookingForm) {
      bookingForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;
        const body = Object.fromEntries(new FormData(form).entries());
        try {
          const result = await api("/api/client/bookings", { method: "POST", body });
          state.notice = result.message || "Booking request submitted.";
          state.data.bookingId = result.booking?.id;
          setView("booking_detail");
        } catch (error) {
          state.error = error.message;
          if (submitBtn) submitBtn.disabled = false;
          render();
        }
      });
    }
    const editForm = document.getElementById("edit-booking-form");
    if (editForm) {
      editForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const body = Object.fromEntries(new FormData(event.target).entries());
        try {
          await api("/api/client/bookings/" + state.data.bookingId, { method: "PATCH", body });
          state.notice = "Booking request updated.";
          setView("booking_detail");
        } catch (error) {
          state.error = error.message;
          render();
        }
      });
    }
    const profileForm = document.getElementById("profile-form");
    if (profileForm) {
      profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const body = Object.fromEntries(new FormData(event.target).entries());
        try {
          const result = await api("/api/client/profile", { method: "PATCH", body });
          state.user = result.user;
          state.company = result.company;
          state.notice = "Profile saved.";
          setView("profile");
        } catch (error) {
          state.error = error.message;
          render();
        }
      });
    }
  }

  restore();
})();
