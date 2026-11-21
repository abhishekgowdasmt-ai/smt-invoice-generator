-- Forward migration. Driver accept/reject runs assignment_guard as smt_driver.
-- That trigger locks the booking row with SELECT ... FOR UPDATE. On PostgreSQL 16,
-- FOR UPDATE requires UPDATE privilege on at least one column (same pattern as
-- 008_definer_assignment_guard_selects.sql for vehicles).
--
-- No bookings UPDATE policy is added for smt_driver, so RLS still denies actual
-- booking row updates from the driver role. This grant only enables the lock
-- needed for assignment transitions.
--
-- Apply as a superuser, with ON_ERROR_STOP, to one disposable local _test
-- database first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

GRANT UPDATE (status) ON bookings TO smt_driver;

COMMENT ON COLUMN bookings.status IS
    'Driver role has column UPDATE for FOR UPDATE locks in assignment_guard only; RLS still blocks driver booking updates.';

COMMIT;
