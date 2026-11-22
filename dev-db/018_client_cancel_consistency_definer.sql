-- Forward migration 018 — Client portal cancel integrity.
--
-- Defect (Master Prompt 10 acceptance):
-- Client cancel of an unassigned client_request updates bookings.status to
-- 'cancelled'. The deferred constraint trigger booking_consistency_from_booking
-- runs assert_booking_consistent(), which SELECTs booking_assignments and
-- trip_sessions. smt_client has no SELECT on those tables, so COMMIT fails with
-- InsufficientPrivilege and the API returns 503 "Client portal is not available".
--
-- Fix:
-- Run assert_booking_consistent as SECURITY DEFINER owned by smt_definer with a
-- fixed search_path (same pattern as bookings_write_event_and_close / 007).
-- This does not grant clients broad SELECT on assignment tables and does not
-- change consistency rules.
--
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- only after owner approval. Do not apply to smt_dev or production without
-- separate approval.
\set ON_ERROR_STOP on
BEGIN;

ALTER FUNCTION public.assert_booking_consistent()
    OWNER TO smt_definer;

ALTER FUNCTION public.assert_booking_consistent()
    SECURITY DEFINER
    SET search_path = pg_catalog, public;

REVOKE ALL ON FUNCTION public.assert_booking_consistent() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.assert_booking_consistent()
    TO smt_owner, smt_staff, smt_driver, smt_client, smt_definer;

COMMENT ON FUNCTION public.assert_booking_consistent() IS
    'Deferred booking/assignment/session consistency. SECURITY DEFINER so client cancel and other permitted status updates can commit without SELECT grants on assignment tables.';

COMMIT;
