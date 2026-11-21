-- Forward migration. Driver Android app support:
-- password column grants, company/document/payout visibility for smt_driver,
-- duty_readings INSERT for drivers, in-app driver_notifications.
-- Apply as a superuser, with ON_ERROR_STOP, to one disposable local _test
-- database first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

-- Owner may read/write password hashes for explicit driver account provisioning.
GRANT SELECT (password_hash) ON users TO smt_owner;
GRANT UPDATE (password_hash) ON users TO smt_owner;

-- One login phone per driver user (staff/owner emails are unaffected).
CREATE UNIQUE INDEX IF NOT EXISTS users_driver_phone_uq
    ON users (phone)
    WHERE role = 'driver' AND phone IS NOT NULL;

-- Booking reference and remarks for assigned duties.
GRANT SELECT (source_booking_id, remarks) ON bookings TO smt_driver;

-- Drivers may see their own verification status and document metadata.
GRANT SELECT (verification_status) ON drivers TO smt_driver;
GRANT SELECT (id, driver_id, doc_type, doc_number, expiry_date, created_at)
    ON driver_documents TO smt_driver;

DROP POLICY IF EXISTS driver_documents_driver_read ON driver_documents;
CREATE POLICY driver_documents_driver_read ON driver_documents
    FOR SELECT TO smt_driver
    USING (driver_id = current_driver_id());

-- Company name on assigned duties.
GRANT SELECT (id, name) ON companies TO smt_driver;
DROP POLICY IF EXISTS companies_driver_read ON companies;
CREATE POLICY companies_driver_read ON companies
    FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1
            FROM bookings b
            JOIN booking_assignments a ON a.booking_id = b.id
            WHERE b.company_id = companies.id
              AND a.driver_id = current_driver_id()
        )
    );

-- Payout reference/created_at for driver history (read-only).
GRANT SELECT (reference, created_at) ON driver_payouts TO smt_driver;

-- Drivers may create and update kilometre readings for their accepted duties.
GRANT INSERT ON duty_readings TO smt_driver;
DROP POLICY IF EXISTS readings_driver_insert ON duty_readings;
CREATE POLICY readings_driver_insert ON duty_readings
    FOR INSERT TO smt_driver
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.booking_id = booking_id
              AND a.driver_id = current_driver_id()
              AND a.status = 'accepted'
        )
    );

-- In-app notifications for the authenticated driver (no push secrets here).
CREATE TABLE IF NOT EXISTS driver_notifications (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    driver_id uuid NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    booking_id uuid REFERENCES bookings(id) ON DELETE SET NULL,
    assignment_id uuid REFERENCES booking_assignments(id) ON DELETE SET NULL,
    kind text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT driver_notifications_kind_not_blank CHECK (btrim(kind) <> ''),
    CONSTRAINT driver_notifications_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT driver_notifications_body_not_blank CHECK (btrim(body) <> '')
);

CREATE INDEX IF NOT EXISTS driver_notifications_driver_created
    ON driver_notifications (driver_id, created_at DESC);
CREATE INDEX IF NOT EXISTS driver_notifications_unread
    ON driver_notifications (driver_id)
    WHERE read_at IS NULL;

ALTER TABLE driver_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_notifications FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS driver_notifications_driver_select ON driver_notifications;
CREATE POLICY driver_notifications_driver_select ON driver_notifications
    FOR SELECT TO smt_driver
    USING (driver_id = current_driver_id());

DROP POLICY IF EXISTS driver_notifications_driver_update ON driver_notifications;
CREATE POLICY driver_notifications_driver_update ON driver_notifications
    FOR UPDATE TO smt_driver
    USING (driver_id = current_driver_id())
    WITH CHECK (driver_id = current_driver_id());

DROP POLICY IF EXISTS driver_notifications_staff ON driver_notifications;
CREATE POLICY driver_notifications_staff ON driver_notifications
    FOR ALL TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM drivers d
            JOIN driver_branches db ON db.driver_id = d.id
            WHERE d.id = driver_notifications.driver_id
              AND staff_can_branch(db.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM drivers d
            JOIN driver_branches db ON db.driver_id = d.id
            WHERE d.id = driver_notifications.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

DROP POLICY IF EXISTS driver_notifications_definer_insert ON driver_notifications;
CREATE POLICY driver_notifications_definer_insert ON driver_notifications
    FOR INSERT TO smt_definer
    WITH CHECK (true);

GRANT SELECT, UPDATE (read_at) ON driver_notifications TO smt_driver;
GRANT SELECT, INSERT, UPDATE, DELETE ON driver_notifications TO smt_owner, smt_staff;
GRANT INSERT ON driver_notifications TO smt_definer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smt_owner, smt_staff, smt_driver, smt_definer;

CREATE OR REPLACE FUNCTION notify_driver_assignment()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    booking_ref text;
    trip_day text;
    notice_kind text;
    notice_title text;
    notice_body text;
    reason_text text;
BEGIN
    reason_text := lower(COALESCE(NEW.rejection_reason, ''));

    IF TG_OP = 'INSERT' AND NEW.status = 'assigned' THEN
        notice_kind := 'assignment';
        notice_title := 'New duty assigned';
        notice_body := 'A new duty was assigned to you. Open the app to review and respond.';
    ELSIF TG_OP = 'UPDATE'
          AND OLD.status IS DISTINCT FROM NEW.status
          AND NEW.status = 'superseded'
          AND reason_text LIKE '%reassign%' THEN
        notice_kind := 'reassignment';
        notice_title := 'Duty reassigned';
        notice_body := 'A duty was taken off you and given to another driver.';
    ELSIF TG_OP = 'UPDATE'
          AND OLD.status IS DISTINCT FROM NEW.status
          AND NEW.status IN ('superseded', 'withdrawn')
          AND reason_text LIKE '%cancel%' THEN
        notice_kind := 'cancellation';
        notice_title := 'Booking cancelled';
        notice_body := 'A booking linked to your duty was cancelled.';
    ELSIF TG_OP = 'UPDATE'
          AND OLD.status IS DISTINCT FROM NEW.status
          AND NEW.status IN ('superseded', 'withdrawn') THEN
        notice_kind := 'release';
        notice_title := 'Duty released';
        notice_body := 'A duty was released from you.';
    ELSE
        RETURN NEW;
    END IF;

    SELECT COALESCE(b.source_booking_id, b.id::text), COALESCE(b.trip_date::text, '')
    INTO booking_ref, trip_day
    FROM bookings b
    WHERE b.id = NEW.booking_id;

    IF booking_ref IS NOT NULL THEN
        notice_body := notice_body || ' Reference: ' || booking_ref || '.';
    END IF;
    IF trip_day <> '' THEN
        notice_body := notice_body || ' Trip date: ' || trip_day || '.';
    END IF;

    INSERT INTO driver_notifications (
        driver_id, booking_id, assignment_id, kind, title, body
    ) VALUES (
        NEW.driver_id, NEW.booking_id, NEW.id, notice_kind, notice_title, notice_body
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS booking_assignments_driver_notify ON booking_assignments;
CREATE TRIGGER booking_assignments_driver_notify
    AFTER INSERT OR UPDATE OF status, rejection_reason ON booking_assignments
    FOR EACH ROW
    EXECUTE FUNCTION notify_driver_assignment();

COMMENT ON TABLE driver_notifications IS
    'In-app driver notifications. Push providers are optional and configured outside this table.';

COMMIT;
