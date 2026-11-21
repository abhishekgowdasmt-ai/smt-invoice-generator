# Client Web Portal

Corporate client portal for Shree Maruthi Travels. Served by Flask at `/client/`
and backed by PostgreSQL RLS (`smt_client` + `client_can_company`).

## Architecture

| Piece | Location |
|-------|----------|
| Static SPA | `client_portal/` (`index.html`, `styles.css`, `app.js`) |
| Auth | `backend/client_auth.py` — signed httpOnly cookie `smt_client` |
| APIs | `backend/operations_client_portal.py` + `/api/client/*` routes in `app.py` |
| Migration | `dev-db/011_client_portal.sql` |

Sessions use cookies (not localStorage). Company identity is taken from the
server session and `user_company_links`, never from browser-supplied company IDs.

## Run locally

1. Apply `011_client_portal.sql` to disposable `smt_revision8_test` (see APPLY txt).
2. Set `CLIENT_TOKEN` (≥32 chars) or rely on local `STAFF_TOKEN` fallback.
3. Start Flask as usual from the app root.
4. Open `http://127.0.0.1:5000/client/`.
5. Owner provisions a client login:

```http
POST /api/clients/<client_user_id>/login-account
{ "password": "at-least-8-chars" }
```

Client must already exist (`role=client`) and be linked to exactly one company.

## Authentication flow

1. `POST /api/client/login` with email + password.
2. Server verifies hash as owner, issues token, sets httpOnly cookie.
3. Subsequent `/api/client/*` calls resolve `user_id` from the cookie.
4. `POST /api/client/logout` clears the cookie.
5. Tokens expire after 12 hours.

## Authorization / isolation

- Database role `smt_client` via `app_begin`.
- Bookings, invoices, payments, and `client_duty_status` filtered by
  `client_can_company(...)`.
- Clients cannot assign drivers/vehicles, issue/void invoices, or change company links.
- Booking requests use `origin='client_request'` and remain `unassigned` until supervisors act.

## API endpoints

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/api/client/login` | public | Sets cookie |
| POST | `/api/client/logout` | cookie | Clears cookie |
| GET | `/api/client/session` | client | Profile + company |
| GET | `/api/client/dashboard` | client | Balances from `invoice_balances` |
| GET/POST | `/api/client/bookings` | client | List / create request |
| GET/PATCH | `/api/client/bookings/<id>` | client | Detail / edit unassigned request |
| POST | `/api/client/bookings/<id>/cancel` | client | Cancel unassigned request |
| GET | `/api/client/trips` | client | `client_duty_status` |
| GET | `/api/client/invoices` | client | Issued, non-void only |
| GET | `/api/client/invoices/<id>` | client | Lines + balances |
| GET | `/api/client/payments` | client | Includes reversed marker |
| GET/PATCH | `/api/client/profile` | client | `full_name`, `phone` only |
| GET | `/api/client/support` | client | Verified public contact details |
| POST | `/api/clients/<id>/login-account` | owner | Provision password |

## Environment

- `CLIENT_TOKEN` — signing secret (≥32 chars)
- `SMT_DEV_DATABASE_URL` / disposable test override as for other local APIs
- `PUBLIC_SITE_URL` — optional; support card also hardcodes verified contact.html values

## Tests

`tests/test_client_portal.py` against disposable `*_test` only (requires 011).

## Known limitations

- No live GPS tracking (not authorized / not wired).
- Clients cannot pay online; payments are read-only accounting records.
- Draft and voided invoices are hidden.
- Only unassigned `client_request` bookings are editable/cancellable by clients.
- Password reset is not implemented (no existing client reset flow).
