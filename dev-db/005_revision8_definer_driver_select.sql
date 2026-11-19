-- Forward grant for a database where 003_revision8_driver_verification.sql
-- has already been applied. review_driver, resubmit_driver, and
-- set_driver_active read verification_status and active while locking the
-- driver row. Revision 7 grants smt_definer SELECT only on id and user_id.
-- The existing column UPDATE grant already satisfies SELECT ... FOR UPDATE.
-- This does not grant table-level privileges and does not change functions.
\set ON_ERROR_STOP on
BEGIN;

GRANT SELECT (verification_status, active) ON drivers TO smt_definer;

COMMIT;
