-- Forward migration (depends on 012 and 013).
--
-- Problem: assignments_driver_update USING only allows status = 'assigned'.
-- On PostgreSQL 16 with FORCE RLS, SELECT ... FOR UPDATE consults UPDATE
-- policies. After a driver accepts, status is 'accepted', so FOR UPDATE
-- returns no row. That breaks driver start, completion locking, and
-- idempotent accept (all use FOR UPDATE on booking_assignments).
--
-- Fix: widen USING to open duties only (assigned, accepted) for the current
-- driver. Keep WITH CHECK unchanged so drivers may still only transition to
-- accepted or rejected. Triggers (assignment_guard) continue to enforce
-- permitted transitions. Rejected, withdrawn, superseded, and completed rows
-- remain unlockable and non-updatable via this policy.
--
-- Owner/staff policies are not modified. No new table grants.
--
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

DROP POLICY IF EXISTS assignments_driver_update ON booking_assignments;
CREATE POLICY assignments_driver_update ON booking_assignments
    FOR UPDATE TO smt_driver
    USING (
        driver_id = current_driver_id()
        AND status IN ('assigned', 'accepted')
    )
    WITH CHECK (
        driver_id = current_driver_id()
        AND status IN ('accepted', 'rejected')
    );

COMMENT ON POLICY assignments_driver_update ON booking_assignments IS
    'Drivers may lock/update only their open duties (assigned|accepted). WITH CHECK limits resulting status to accepted|rejected; historical statuses stay excluded.';

COMMIT;
