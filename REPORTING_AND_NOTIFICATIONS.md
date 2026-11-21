# Reporting and Notifications (Master Prompt 7)

## Implemented features

### Reporting architecture

- Backend module: `shree-maruthi-travels-main/backend/operations_reports.py`
- HTTP: `GET /api/reports/<report_name>` (staff/owner cookie auth)
- CSV: same route with `export=csv`
- Calculations run under RLS via `_actor_work` / existing finance helpers
- No separate analytics database; no frontend KPI invention
- Detail rows capped at 500; date filters validated server-side

### Available reports

| Name | Source | Notes |
|------|--------|-------|
| `bookings` | `bookings` | Totals by status/origin; date/status/origin/branch/company filters |
| `trips` | assignments + trip sessions / readings | Duration/km only when timestamps or readings exist |
| `drivers` | assignments + drivers | Assigned/accepted/rejected/completed counts — no invented ratings |
| `vehicles` | vehicles + assignments | Assigned/completed counts and current status |
| `branch-company` | bookings + branches + companies | Branch- and company-scoped aggregates |
| `invoices` | `invoices` + `invoice_balances` | Draft/void excluded from issued revenue |
| `payments` | `payments` | `collected_active` excludes reversed |
| `payouts` | `driver_payouts` | Pending/paid/cancelled from stored statuses |
| `expenses` | `expenses` | Category/status/branch/company |
| `company-settlement` | `operations_finance.company_settlement` | Requires `company_id` |
| `financial-summary` | combines invoice/payment/payout/expense | Net cash = collections − paid payouts − expenses; not “invoice cash revenue” |

### Filters

`from` / `to` (or `date_from` / `date_to`), `branch` (UUID or `BLR`/`HYD`), `company_id`, `driver_id`, `vehicle_id`, `status`, `origin`, plus report-specific invoice/payment/expense filters.

Unauthorized actors receive 401. Invalid filters return 400. Branch filtering for staff remains RLS-enforced.

### CSV exports

All listed reports support CSV. Cells starting with `=`, `+`, `-`, or `@` are prefixed with `'` to block spreadsheet formula injection. Filenames use `smt-<report>-YYYY-MM-DD.csv`.

### Supervisor UI

Reports tab in Supervisor Website: date/branch/company filters, report picker (operations + finance groups), summary cards, results table, CSV export, supervisor alerts list (when migration 016 is applied).

### Notifications

| Channel | Store | API |
|---------|-------|-----|
| Driver | `driver_notifications` (010; `event_key` in 016) | `/api/driver/notifications` (+ read); includes `unread_count` |
| Client | `client_notifications` (016) | `/api/client/notifications` (+ read) |
| Supervisor | `staff_notifications` (016) | `/api/operations/notifications` (+ read) |

Delivery model: **in-app persistence + polling**. No WebSockets or push credentials invented. Inserts use SECURITY DEFINER `post_client_notification` / `post_staff_notification` with savepoints so notification failure does not roll back the business transaction when emits run after success.

Event keys (idempotency): `event_key` unique indexes prevent duplicate rows for retried emits.

Recipient rules:

- Drivers see only their own notifications.
- Clients see only rows for companies they can access (`client_can_company`); never `driver_notifications`.
- Staff/owners see staff notifications under branch RLS.

Emitted events (best-effort after successful ops):

- Client booking request → client ack + staff alert
- Assignment status updates relevant to clients (assigned/accepted/started/completed/cancelled)
- Driver reject → staff alert
- Invoice issued / payment recorded / payment reversed → client

### Flutter driver app

Notifications list shows timestamps, unread indicator, network/empty states, and navigates to the linked duty when `assignment_id` is present. Home shell shows an unread badge on Alerts.

### Client portal

Alerts nav item lists company notifications with mark-read and booking/invoice deep links. Graceful empty/unavailable message until migration 016 is applied.

## Database migrations

| File | Status |
|------|--------|
| `dev-db/016_app_notifications.sql` | **Prepared only** — do not apply without approval |
| `dev-db/016_app_notifications_APPLY.txt` | Apply instructions for `smt_revision8_test` |

Reports require no new schema. Notification APIs return unavailable until 016 is applied.

## Scheduled reports

**Future capability.** No safe background job runner was added. Daily/weekly/monthly emailed summaries are documented as out of scope for Prompt 7 to avoid new worker/Docker changes.

## Authorization

- Owner: company-wide reports within RLS
- Staff: branch-scoped by RLS; filter values cannot bypass access
- Drivers/clients: personal/company isolation only
- No weakening of RLS; no broad grants

## Local setup

1. Use disposable `smt_revision8_test` with existing finance/ops migrations.
2. Optionally apply 016 per APPLY file (approval required).
3. Supervisor: open Reports tab.
4. Client: Alerts after 016.
5. Driver: Alerts tab (existing driver_notifications).

## Automated tests

- `tests/test_operations_reports.py` — aggregates, filters, CSV auth, injection escape
- `tests/test_app_notifications.py` — skips until 016; isolation, idempotency, privilege check

## Known limitations

- No PDF report export (no new PDF stack).
- No real-time push; polling only.
- Company settlement report requires explicit `company_id`; date range does not rewrite settlement totals.
- Trip duration/km omitted when source columns are null.
- Scheduled digest emails not implemented.
- Migration 016 not applied by the agent.

## Untouched systems

RAC JSON dashboard, SQLite admin paths, Zoho integrations, production/smt_dev data, Docker/startup scripts remain unchanged for this milestone.
