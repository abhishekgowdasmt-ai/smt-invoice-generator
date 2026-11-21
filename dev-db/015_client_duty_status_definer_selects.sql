-- Forward migration (depends on base schema + 005/008 definer column grants).
--
-- Problem: client_duty_status is owned by smt_definer with security_invoker=false
-- and security_barrier=true. Selecting the view as smt_client therefore runs as
-- smt_definer against the underlying tables. The view reads:
--   drivers.display_name, drivers.phone
--   vehicles.registration_number, vehicles.model
-- (plus drivers.id / vehicles.id already granted).
--
-- On databases built from Revision 7/8 grants, smt_definer only has
-- SELECT (id, user_id[, verification_status, active]) on drivers and
-- SELECT (id, branch_id, status) on vehicles. Missing display columns cause:
--   permission denied for table drivers
-- when GET /api/client/trips (or booking detail trip attach) selects the view.
--
-- Fix: grant smt_definer only those four missing column SELECTs. Do not grant
-- table-level SELECT. Do not grant these columns to smt_client or smt_driver
-- (clients already reach display fields only through the barrier view;
-- drivers already have their own existing column grants). No RLS, UPDATE,
-- or WITH CHECK changes.
--
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

GRANT SELECT (display_name, phone) ON drivers TO smt_definer;
GRANT SELECT (registration_number, model) ON vehicles TO smt_definer;

COMMIT;
