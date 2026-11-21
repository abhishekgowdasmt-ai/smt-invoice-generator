# Shared Backend Integration (Master Prompt 5)

Three applications share one Flask backend and one PostgreSQL database for the
new operational workflows. Legacy RAC JSON/SQLite/Zoho paths remain separate
and are not migrated automatically.

## Architecture

```
┌─────────────────────┐  cookie smt_staff   ┌──────────────────────────────┐
│ Supervisor Website  │ ──────────────────► │ /api/operations/*             │
│ (owner / staff)     │                     │ /api/finance/*                │
└─────────────────────┘                     │ /api/companies|drivers|…      │
                                            │                               │
┌─────────────────────┐  Bearer token       │ /api/driver/*                 │
│ Flutter Driver App  │ ──────────────────► │                               │
└─────────────────────┘                     │ /api/client/*  + /client/     │
                                            │                               │
┌─────────────────────┐  cookie smt_client  │ authorized_transaction + RLS  │
│ Client Web Portal   │ ──────────────────► │ smt_owner|staff|driver|client │
└─────────────────────┘                     └──────────────┬───────────────┘
                                                           │
                                                           ▼
                                              PostgreSQL (smt_dev / _test)
                                              bookings · assignments · trips
                                              invoices · payments · payouts
                                              driver_notifications
```

Authoritative store for shared workflows: PostgreSQL. Business logic lives in
`backend/operations_*.py` and `dev_postgres.py`, not in the three frontends.

## Authentication and identity

| App | Transport | Secret | Server identity | DB role |
|-----|-----------|--------|-----------------|---------|
| Supervisor | httpOnly cookie `smt_staff` (Bearer also accepted) | `STAFF_TOKEN` | email → `resolve_login_identity` | `smt_owner` / `smt_staff` |
| Driver | `Authorization: Bearer` | `DRIVER_TOKEN` (local fallback `STAFF_TOKEN`) | token `uid`/`did` → `current_driver_id()` | `smt_driver` |
| Client | httpOnly cookie `smt_client` | `CLIENT_TOKEN` (local fallback `STAFF_TOKEN`) | token `uid`/`cid` → `client_can_company` | `smt_client` |

Common rules:

- Never trust frontend-supplied user/driver/client/company IDs as proof of identity.
- Every protected write runs inside `authorized_transaction` with `SET LOCAL ROLE`.
- Cross-role access is denied at the actor layer and by RLS.
- Auth mechanisms stay separate; see `backend/shared_api_contracts.py`.

## Role and permission matrix (shared workflows)

| Capability | Owner/Staff | Driver | Client |
|------------|-------------|--------|--------|
| Create ops booking | Yes | No | Request only (`origin=client_request`) |
| Assign / reassign / unassign | Yes | No | No |
| Accept / reject duty | Yes (ops) | Own duties | No |
| Start / complete trip | Yes (by booking) | Own duty + km | No |
| Read trip status | Full | Own duties | Company-visible fields only |
| Issue / void invoice | Yes | No | No |
| Record / reverse payment | Yes | No | Read issued invoices & payments |
| Driver payouts | Manage | Own read-only | No |
| Driver notifications | Manage | Own only | N/A |

## Shared vs application-specific APIs

**Shared data (same tables):** bookings, booking_assignments, trip_sessions,
duty_readings, invoices, payments, driver_payouts, companies, drivers, vehicles.

**Supervisor-specific:** `/api/operations/*`, `/api/finance/*`, master-data CRUD,
login provisioning for drivers/clients.

**Driver-specific:** `/api/driver/*` (Bearer), notifications, km on start/complete.

**Client-specific:** `/api/client/*` (cookie), booking requests, `client_duty_status`,
issued-invoice views.

**Not shared with Postgres ops:** `/api/v1` RAC JSON, `/api/admin/*` SQLite website
admin, Zoho Sheet inquiry append.

## API contracts

Internal service result: `{ok, error?, message?, …}`.

HTTP mapping (all three apps): `shared_api_contracts.ERROR_HTTP_STATUS`.

| error | HTTP |
|-------|------|
| invalid | 400 |
| unauthorized | 401 |
| forbidden / disabled | 403 |
| not_found | 404 |
| conflict | 409 |
| unavailable | 503 |

Success envelopes differ by design (do not rename without updating consumers):

- Supervisor ops/finance: `{success, data}`
- Driver / client: `{success, …flattened keys}`

Identifiers are UUID strings. Dates are ISO `YYYY-MM-DD`. Money amounts are
decimal strings from finance services. Timestamps use ISO via backend helpers.

Supervisor booking list supports `?origin=client_request` so client requests
appear in the same register without a second booking store.

## Booking and trip lifecycle

1. Client creates `origin=client_request` booking (`unassigned`), **or** supervisor
   creates an ops booking (stored as `origin=rac` for the shared register; RAC JSON
   remains a separate store).
2. Supervisor assigns a verified active driver (+ vehicle when required). Assignable
   origins: `rac`, `retail`, `client_request` (not `ets_occurrence` via this API).
3. Assignment notification is written for the driver (`driver_notifications`, migration 010).
4. Driver (or supervisor) accepts or rejects.
5. Driver starts with `start_km`, or supervisor starts without km.
6. Driver completes with `end_km`, or supervisor completes the session.
7. Client polls bookings/trips; supervisor sees full operational status.

Guards: booking/assignment transition triggers, `one_open_assignment_per_booking`,
`one_active_session_per_assignment` / `per_driver`, `FOR UPDATE` locks on start paths.

## Financial ownership

Finance APIs under `/api/finance/*` are authoritative. Clients only read issued,
non-void invoices and payments for their company. Drivers only read their own
payouts. No frontend recalculates invoice totals.

## Notifications

Assignment / reassignment / cancellation / release create `driver_notifications`
via a `SECURITY DEFINER` trigger. Notification insert failures are isolated from
optional push providers (not configured here). WhatsApp delivery for staff assign
runs after the DB commit path and must not undo the duty write.

## Database dependencies and migrations

Order for a disposable `*_test` database (do not apply here without approval):

1. `001_smt_dev_schema.sql` (+ branch/staff seeds as needed)
2. `003`–`008` duty/definer/search_path/guards as already used for Revision 8
3. `009_finance_lifecycle.sql`
4. `010_driver_app.sql`
5. `011_client_portal.sql`
6. `012_driver_booking_lock_grant.sql` — `GRANT UPDATE (status) ON bookings TO smt_driver`
   so `assignment_guard` can `SELECT … FOR UPDATE` during driver accept/reject.
   No driver UPDATE RLS policy is added; actual booking updates remain denied.

Master Prompt 5 prepares migration **012** (not applied automatically). Apply to
`smt_revision8_test` only after approval; see `dev-db/012_driver_booking_lock_grant_APPLY.txt`.

## Run each application locally

1. Point `SMT_DEV_DATABASE_URL` at local Postgres (or disposable override for tests).
2. Set `STAFF_TOKEN` (≥32). Optional: `DRIVER_TOKEN`, `CLIENT_TOKEN`.
3. Start Flask from `shree-maruthi-travels-main/shree-maruthi-travels-main`.
4. Supervisor: `/admin` (staff cookie).
5. Client portal: `/client/`.
6. Driver app: Flutter project under `driver_app/` against the same host `/api/driver/*`.

## Integration tests

`tests/test_shared_integration.py` on disposable `smt_revision8_test` only:

```
SMT_REVISION8_DISPOSABLE=yes
SMT_REVISION8_DATABASE_URL=<dsn for smt_revision8_test>
SMT_REVISION8_BOOTSTRAP_OWNER_ID=<owner uuid in that database>
```

Do not run against `smt_dev` or production.

## Known limitations

- RAC JSON and Postgres ops remain separate stores.
- No live GPS / push provider credentials.
- Client trip visibility is poll-based (`client_duty_status`); no client push inbox.
- Staff start/complete does not require kilometre readings; driver path does.
- Success JSON envelopes are not identical across apps (documented above).
- Comprehensive browser acceptance is reserved for Master Prompt 10.
