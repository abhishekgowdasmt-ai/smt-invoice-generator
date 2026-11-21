-- Forward migration. Client web portal support:
-- client_request booking origin, client INSERT/UPDATE policies for requests,
-- self-service profile updates, issued-invoice visibility helpers.
-- Apply as a superuser, with ON_ERROR_STOP, to one disposable local _test
-- database first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

-- Password hash grants (idempotent if 010 already applied).
GRANT SELECT (password_hash) ON users TO smt_owner;
GRANT UPDATE (password_hash) ON users TO smt_owner;

-- Client-visible booking columns used by the portal.
GRANT SELECT (source_booking_id, source_mobile, remarks) ON bookings TO smt_client;

-- Branch directory (branches has no RLS force; limit via company_branches joins in SQL).
GRANT SELECT (id, code, name) ON branches TO smt_client;

-- Invoice lifecycle columns added in 009 (idempotent grants).
GRANT SELECT (due_date, voided_at, notes, created_at) ON invoices TO smt_client;
GRANT SELECT (reversed_at) ON payments TO smt_client;

-- Allow client portal booking requests without inventing a parallel lifecycle.
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_origin_check;
ALTER TABLE bookings
    ADD CONSTRAINT bookings_origin_check
    CHECK (origin IN ('rac', 'ets_occurrence', 'retail', 'client_request'));

COMMENT ON CONSTRAINT bookings_origin_check ON bookings IS
    'client_request rows stay unassigned until supervisors assign drivers.';

-- Clients may create unassigned requests for their linked company only.
GRANT INSERT (
    id, branch_id, company_id, origin, source_booking_id, trip_date, pickup_time,
    end_time, duty_type, cab_type, planned_start, route_text, employee_name,
    source_name, source_mobile, status, remarks, created_at
) ON bookings TO smt_client;

GRANT UPDATE (
    trip_date, pickup_time, end_time, duty_type, cab_type, planned_start,
    route_text, employee_name, source_name, source_mobile, remarks, status
) ON bookings TO smt_client;

DROP POLICY IF EXISTS bookings_client_insert ON bookings;
CREATE POLICY bookings_client_insert ON bookings
    FOR INSERT TO smt_client
    WITH CHECK (
        company_id IS NOT NULL
        AND client_can_company(company_id)
        AND origin = 'client_request'
        AND status = 'unassigned'
    );

DROP POLICY IF EXISTS bookings_client_update ON bookings;
CREATE POLICY bookings_client_update ON bookings
    FOR UPDATE TO smt_client
    USING (
        company_id IS NOT NULL
        AND client_can_company(company_id)
        AND origin = 'client_request'
        AND status = 'unassigned'
    )
    WITH CHECK (
        company_id IS NOT NULL
        AND client_can_company(company_id)
        AND origin = 'client_request'
        AND status IN ('unassigned', 'cancelled')
    );

-- Safe self-service profile fields (not company links or role).
GRANT UPDATE (full_name, phone) ON users TO smt_client;
DROP POLICY IF EXISTS users_client_self_update ON users;
CREATE POLICY users_client_self_update ON users
    FOR UPDATE TO smt_client
    USING (id = app_uid() AND role = 'client')
    WITH CHECK (id = app_uid() AND role = 'client');

-- One login email per client user when email is present (already unique globally).
-- Issued invoices only: clients already SELECT invoices; app filters drafts/voids.

COMMIT;
