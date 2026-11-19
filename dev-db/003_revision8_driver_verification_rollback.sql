-- Revision 8 pre-data rollback. DESIGN ONLY. Do not run until the forward
-- script was applied on local smt_dev and no real verification activity exists.
--
-- This script aborts when any submission, review, document, or active-change
-- row exists. It does not delete those rows. After real records exist, correct
-- the data forward. Do not drop the history tables to undo them.
\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    event_rows bigint;
    document_rows bigint;
    active_rows bigint;
BEGIN
    IF to_regclass('public.driver_verification_events') IS NULL
       OR to_regclass('public.driver_documents') IS NULL
       OR to_regclass('public.driver_active_changes') IS NULL THEN
        RAISE EXCEPTION 'Revision 8 tables are not installed';
    END IF;
    SELECT count(*) INTO event_rows FROM public.driver_verification_events;
    SELECT count(*) INTO document_rows FROM public.driver_documents;
    SELECT count(*) INTO active_rows FROM public.driver_active_changes;
    IF event_rows > 0 OR document_rows > 0 OR active_rows > 0 THEN
        RAISE EXCEPTION
            'Refusing rollback: % verification events, % document rows, and % active-change rows exist. Leave the history in place and correct it forward.',
            event_rows, document_rows, active_rows;
    END IF;
END $$;

DROP VIEW IF EXISTS driver_duplicate_warnings;
DROP FUNCTION IF EXISTS driver_phone_key(text);

DROP TRIGGER IF EXISTS driver_record_submission_trg ON drivers;
DROP FUNCTION IF EXISTS driver_record_submission();
DROP TRIGGER IF EXISTS drivers_verification_guard_trg ON drivers;
DROP FUNCTION IF EXISTS drivers_verification_guard();
DROP FUNCTION IF EXISTS review_driver(uuid, text, text);
DROP FUNCTION IF EXISTS resubmit_driver(uuid, text);
DROP FUNCTION IF EXISTS set_driver_active(uuid, boolean, text);

DROP TABLE IF EXISTS driver_active_changes;
DROP TABLE IF EXISTS driver_verification_events;
DROP TABLE IF EXISTS driver_documents;

ALTER TABLE drivers DROP CONSTRAINT IF EXISTS drivers_rejected_stay_inactive;
DROP INDEX IF EXISTS drivers_verification_status;
ALTER TABLE drivers DROP COLUMN IF EXISTS verification_status;

-- Revision 7 grants owner and staff table-level UPDATE on drivers. This script
-- does not repeat that form, because a table-level grant would also cover
-- columns added later. It restores UPDATE only on the columns defined for
-- drivers in dev-db/001_smt_dev_schema.sql, including active.
-- SELECT, INSERT, and DELETE were not revoked by Revision 8 and are left as
-- they stand. smt_driver keeps its column SELECT and UPDATE grants.
-- smt_definer keeps SELECT (id, user_id) only. Revision 8's UPDATE grant to
-- smt_definer is removed.
-- EXECUTE on app_is_owner() is not revoked from smt_definer. Revision 7
-- already leaves that privilege with the function owner, so the forward
-- GRANT does not add a privilege and revoking it would remove the owner's.
REVOKE UPDATE ON drivers FROM smt_owner, smt_staff, smt_definer;
GRANT UPDATE (
    id, user_id, primary_branch_id, display_name, phone, whatsapp_number,
    alternate_number, license_number, license_expiry, home_area, active, notes,
    legacy_source, legacy_driver_id, legacy_sqlite_id, branch_inferred
) ON drivers TO smt_owner, smt_staff;

COMMIT;
