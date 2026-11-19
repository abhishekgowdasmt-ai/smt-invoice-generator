-- Forward migration. A clean source booking ID is unique across branches and trip dates.
-- Rows with identity_status conflict or missing_code stay outside the index.
-- Blank source booking IDs stay allowed.
-- Does not change row security, grants, triggers, or functions.
-- Apply as the table owner, with ON_ERROR_STOP, to one local database.
-- Aborts before replacing the index when duplicate clean source IDs already exist.
\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    duplicate_count integer;
BEGIN
    SELECT count(*) INTO duplicate_count
    FROM (
        SELECT source_booking_id
        FROM bookings
        WHERE source_booking_id IS NOT NULL
          AND identity_status = 'clean'
        GROUP BY source_booking_id
        HAVING count(*) > 1
    ) duplicates;
    IF duplicate_count > 0 THEN
        RAISE EXCEPTION 'clean source_booking_id values are duplicated; index was not replaced';
    END IF;
END $$;

DROP INDEX public.bookings_clean_source_code;

CREATE UNIQUE INDEX bookings_clean_source_code
    ON public.bookings (source_booking_id)
    WHERE source_booking_id IS NOT NULL
      AND identity_status = 'clean';

COMMIT;
