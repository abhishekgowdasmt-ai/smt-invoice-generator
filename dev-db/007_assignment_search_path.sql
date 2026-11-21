-- Forward migration. Nested BEFORE triggers on bookings, assignments and
-- sessions resolve public tables and null_if_blank. The three SECURITY DEFINER
-- AFTER triggers previously set search_path = pg_catalog only, so those nested
-- calls failed with "relation bookings does not exist" or missing null_if_blank.
-- This matches the search_path used by other definer helpers in 001.
-- Does not change function bodies, RLS, grants, or status transition rules.
-- Apply as a superuser or the function owner, with ON_ERROR_STOP, to one local
-- database. Do not apply to production from this file.
\set ON_ERROR_STOP on
BEGIN;

ALTER FUNCTION public.bookings_write_event_and_close()
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.assignment_after()
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.session_after()
    SET search_path = pg_catalog, public;

COMMIT;
