-- Forward migration (depends on 016_app_notifications.sql).
--
-- Problem: post_client_notification and post_staff_notification are SECURITY
-- DEFINER functions owned by smt_definer. Both run:
--   INSERT ... RETURNING id INTO new_id
-- PostgreSQL requires SELECT privilege on columns listed in RETURNING.
-- Migration 016 granted INSERT only to smt_definer, so RETURNING fails with:
--   permission denied for table <client|staff>_notifications
-- The Python savepoint then reports ok=True, inserted=False.
--
-- Separately, 016 ran GRANT USAGE ON ALL SEQUENCES after creating
-- client_notifications but before creating staff_notifications, so
-- staff_notifications_id_seq never received USAGE for smt_definer. IDENTITY
-- inserts into staff_notifications therefore cannot allocate ids as the
-- definer. client_notifications_id_seq already has USAGE and is unchanged.
--
-- Fix (minimum privileges only):
--   1) GRANT SELECT (id) on both notification tables TO smt_definer
--   2) GRANT USAGE on staff_notifications_id_seq TO smt_definer
--
-- Does not grant table-level SELECT.
-- Does not grant sequence privileges to smt_owner / smt_staff / smt_client.
-- Does not alter RLS policies (smt_definer already has rolbypassrls).
-- Does not change function bodies or ownership.
--
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

-- RETURNING id in post_*_notification requires column SELECT on id.
GRANT SELECT (id) ON client_notifications TO smt_definer;
GRANT SELECT (id) ON staff_notifications TO smt_definer;

-- IDENTITY nextval for staff inserts as smt_definer (missed by 016 timing).
GRANT USAGE ON SEQUENCE staff_notifications_id_seq TO smt_definer;

COMMIT;
