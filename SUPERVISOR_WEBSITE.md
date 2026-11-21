# Supervisor Website

Master Prompt 6 documentation for the Shree Maruthi Travels supervisor portal at `/admin`.

## Navigation and screen structure

| Area | Tab / URL | Store |
|------|-----------|--------|
| Dashboard (operations board) | `#home` | PostgreSQL ops + finance summaries |
| PostgreSQL Duties | `#pg-duties` | Shared booking register |
| PostgreSQL Finance | `#pg-finance` | Invoices, payments, payouts, expenses |
| PostgreSQL Drivers / Vehicles | `#pg-drivers`, `#pg-vehicles` | Owner directories |
| Corporate clients (companies) | `#companies` | Companies, clients, fleet links |
| RAC Management | `/admin/dispatch/` | RAC JSON (separate) |
| ETS | `#tracking` | SQLite simulation (not live GPS) |
| Enquiries / SQLite cabs / drivers | DataSource submenu | Legacy website admin |
| Invoice print layouts | `/admin/invoices/` | Print/PDF tool (not the finance ledger) |

PostgreSQL operational work lives under **Duties**, **Finance**, **Drivers**, **Vehicles**, and **Companies**. RAC JSON remains a separate stack.

## Operational workflows

1. Client portal creates a `client_request` booking, or supervisor creates a retail/company booking.
2. Supervisor opens **PostgreSQL Duties**, filters by origin/status/date/branch, opens the booking.
3. Assign a verified active driver (and optional vehicle). Backend enforces branch, company, verification, and active rules.
4. Driver accepts / starts / completes in the Flutter app, or supervisor uses the same lifecycle actions.
5. Supervisor refreshes duties or the home board to see updated statuses.
6. Finance creates invoices from company work, records payments, manages payouts and expenses.

## Booking and assignment management

- Filters: search, branch, status, **origin** (`client_request` / `rac` / `retail`), trip date.
- Create booking with branch, optional company, passenger, duty/cab, pickup/route.
- Detail actions: assign, reassign, unassign, change vehicle, accept/reject, resend WhatsApp, start, complete, cancel (with confirmation).
- Assignment history and booking events are shown on the detail panel.
- Lifecycle and concurrency stay in PostgreSQL / Flask — the UI never invents status changes.

## Driver and vehicle management

- Driver directory: search, branch, active, verification filters; profile, documents metadata, verification and suspension history.
- Owner-only: verification decisions, login provisioning for the driver app.
- Vehicle directory: registration, model, status, branch, documents metadata, company links.
- Unverified or inactive drivers cannot be assigned (backend + verified/active picker).

## Company and client management

- Company directory with branches, linked drivers/vehicles, and linked client users.
- Company = corporate account; client user = portal login person linked to a company.
- Owner-only: create companies/clients, provision client portal passwords, manage links.

## Finance operations

- Dashboard totals plus **by branch** and **by company** (existing API fields).
- Invoices: create draft, open, issue, void, record payment, reverse payment, print layout link.
- Payouts: create pending, mark paid, cancel.
- Expenses: create, cancel.
- Company settlement panel + billable bookings list.
- Owner/staff finance permissions remain enforced by backend and RLS.

## Role and branch permissions

- Staff cookie session (`smt_staff`) maps to PostgreSQL `owner` / `staff`.
- Owner (`od` in the UI session) gates company/client/driver directory writes and login provisioning.
- Staff see branch-scoped rows via RLS (`staff_can_branch`).
- Clients and drivers cannot use supervisor APIs.

## API dependencies

| Endpoint | Used by |
|----------|---------|
| `GET /api/operations/dashboard` | Home operations board |
| `GET /api/reports/<name>` (+ `export=csv`) | Reports tab (see `REPORTING_AND_NOTIFICATIONS.md`) |
| `GET/POST /api/operations/notifications` | Supervisor alerts (migration 016) |
| `GET/POST /api/operations/bookings` | Duty board / create |
| `…/assign|reassign|unassign|cancel|start|complete` | Duty actions |
| `PATCH /api/operations/assignments/<id>/vehicle` | Change vehicle |
| `GET …/assignments`, `GET …/trip` | History / detail |
| `GET /api/finance/dashboard` | Home + finance tab |
| `GET/POST /api/finance/invoices`, payments, reverse | Finance |
| `GET/POST/PATCH /api/finance/payouts` | Driver payouts |
| `GET/POST/PATCH /api/finance/expenses` | Expenses |
| `GET /api/finance/companies/<id>/settlement` | Settlement panel |
| `GET /api/finance/companies/<id>/billable-bookings` | Billable list |
| `POST /api/drivers|clients/<id>/login-account` | Login provisioning |

## Local setup

1. Local Flask with `SMT_DEV_DATABASE_URL` (or disposable override).
2. For disposable tests: `SMT_REVISION8_DISPOSABLE=yes`, `SMT_REVISION8_DATABASE_URL=…/smt_revision8_test`, bootstrap owner id.
3. Open `/admin`, sign in (Google or local loopback staff login).
4. Use PostgreSQL Duties / Finance for shared-register work; keep RAC dispatch separate.

## Known limitations

- No WebSocket / push refresh — use Refresh or re-open the tab.
- ETS map remains a SQLite simulator, not live PostgreSQL GPS.
- Invoice print layouts are a separate UI from the PostgreSQL finance ledger.
- Browser acceptance tests are reserved for Master Prompt 10.
- No new database migration was required for Prompt 6.

## Automated tests

Focused suite: `tests/test_supervisor_website.py` (operations dashboard, origin filter, finance dashboard, auth denial, RAC untouched).

Also keep running existing duty/finance/shared suites against `smt_revision8_test` after related changes.
