# Cross-Application Workflows (Master Prompt 8)

## Status sync (authoritative PostgreSQL)

Client request → supervisor assign → driver accept/start/complete (or reject → reassign)
updates the same `bookings` / `booking_assignments` / `trip_sessions` rows. Clients read
permitted fields via `client_duty_status`. Supervisors use `/api/operations/*`.
Drivers use `/api/driver/duties/*`.

## Notification wiring

| Event | Client inbox | Staff inbox | Driver inbox |
|-------|--------------|-------------|--------------|
| Client booking request | Yes (016) | Yes | — |
| Supervisor assign/reassign | Yes (staff emit) | — | Trigger 010 |
| Driver accept/start/complete | Yes (post-commit, owner-mediated) | — | — |
| Driver reject | — | Yes (post-commit) | — |
| Client cancel (unassigned request) | Yes | — | — |

Driver role cannot `EXECUTE post_client_notification` (016 grants). After a successful
driver duty write, Flask posts client/staff alerts using the bootstrap owner actor and
the server-known `booking_id` only. Notification failure never rolls back the duty write.

## Client request retry

Identical unassigned `client_request` rows (same company, branch, date, pickup, passenger,
pickup time) submitted within **2 minutes** return the existing booking with
`already: true`. No new schema.

## Finance link

Driver-completed duties appear in `GET /api/finance/companies/<id>/billable-bookings`
when not already invoiced. Incomplete/cancelled requests do not.

## Tests

`tests/test_cross_app_workflows.py` on `smt_revision8_test` (requires 010–017 as used
by the disposable DB). Existing Prompt 5–7 suites remain regression coverage.

## No migration in Prompt 8

016/017 remain the notification schema baseline. A future optional migration could grant
drivers a constrained SECURITY DEFINER emit helper; not required for current wiring.

## Untouched

RAC JSON, SQLite admin, Zoho, Docker/startup, production/`smt_dev`.
