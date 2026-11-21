-- Forward migration. bookings_write_event_and_close runs as smt_definer and
-- updates booking_assignments on completed/cancelled bookings. That fires
-- assignment_guard, which reads driver_branches, company_drivers,
-- company_vehicles and locks the driver/vehicle rows. smt_definer already has
-- limited driver column rights from Revision 8; these SELECT grants close the
-- gap without widening RLS or owner/staff privileges.
-- Does not change trigger bodies, RLS policies, or status transition rules.
-- Apply as a superuser, with ON_ERROR_STOP, to one local database.
\set ON_ERROR_STOP on
BEGIN;

GRANT SELECT ON driver_branches TO smt_definer;
GRANT SELECT ON company_drivers TO smt_definer;
GRANT SELECT ON company_vehicles TO smt_definer;
GRANT SELECT (id, branch_id, status) ON vehicles TO smt_definer;
-- PostgreSQL 16 SELECT ... FOR UPDATE needs UPDATE on at least one column.
GRANT UPDATE (status) ON vehicles TO smt_definer;

COMMIT;
