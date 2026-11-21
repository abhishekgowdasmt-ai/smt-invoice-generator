-- Forward migration (depends on 012_driver_booking_lock_grant.sql).
--
-- Problem: After 012, smt_driver has UPDATE (status) on bookings, but bookings
-- has FORCE RLS and no UPDATE policy for smt_driver. On PostgreSQL 16,
-- SELECT ... FOR UPDATE also applies UPDATE policies; with none present the
-- lock query returns zero rows. assignment_guard then sees NULL booking_branch
-- and raises "Driver is not enabled for this branch".
--
-- The same guard also reads company_drivers / company_vehicles and may lock
-- vehicles. These policies enable only the locks and EXISTS checks required by
-- that invoker-side guard for the driver's open assignments
-- (status IN ('assigned', 'accepted')). Historical rejected / withdrawn /
-- superseded / completed assignments do not grant locks. Actual booking and
-- vehicle UPDATEs stay blocked via WITH CHECK (false). Owner/staff privileges
-- are unchanged.
--
-- Assignment status values (schema check): assigned, accepted, rejected,
-- withdrawn, superseded, completed. There is no assignment status 'cancelled'.
--
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

-- 1) Bookings: FOR UPDATE locks only for this driver's open assignments.
DROP POLICY IF EXISTS bookings_driver_for_update_lock ON bookings;
CREATE POLICY bookings_driver_for_update_lock ON bookings
    FOR UPDATE TO smt_driver
    USING (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            WHERE a.booking_id = bookings.id
              AND a.driver_id = current_driver_id()
              AND a.status IN ('assigned', 'accepted')
        )
    )
    WITH CHECK (false);

COMMENT ON POLICY bookings_driver_for_update_lock ON bookings IS
    'Lock-only for assignment_guard FOR UPDATE on open duties; WITH CHECK false blocks real booking updates.';

-- 2) company_drivers: needed by assignment_guard company authorisation check.
GRANT SELECT ON company_drivers TO smt_driver;
DROP POLICY IF EXISTS company_drivers_driver_read ON company_drivers;
CREATE POLICY company_drivers_driver_read ON company_drivers
    FOR SELECT TO smt_driver
    USING (driver_id = current_driver_id());

-- 3) Vehicles: FOR UPDATE only when linked on this driver's open assignment.
GRANT UPDATE (status) ON vehicles TO smt_driver;
DROP POLICY IF EXISTS vehicles_driver_for_update_lock ON vehicles;
CREATE POLICY vehicles_driver_for_update_lock ON vehicles
    FOR UPDATE TO smt_driver
    USING (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            WHERE a.vehicle_id = vehicles.id
              AND a.driver_id = current_driver_id()
              AND a.status IN ('assigned', 'accepted')
        )
    )
    WITH CHECK (false);

COMMENT ON POLICY vehicles_driver_for_update_lock ON vehicles IS
    'Lock-only for assignment_guard FOR UPDATE on open duties; WITH CHECK false blocks real vehicle updates.';

-- 4) company_vehicles: only the company of the driver's relevant open booking.
GRANT SELECT ON company_vehicles TO smt_driver;
DROP POLICY IF EXISTS company_vehicles_driver_read ON company_vehicles;
CREATE POLICY company_vehicles_driver_read ON company_vehicles
    FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            WHERE a.driver_id = current_driver_id()
              AND a.vehicle_id = company_vehicles.vehicle_id
              AND b.company_id = company_vehicles.company_id
              AND a.status IN ('assigned', 'accepted')
        )
    );

COMMIT;
