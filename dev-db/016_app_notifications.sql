-- Forward migration (depends on 010 driver_notifications + 011 client portal).
--
-- Adds:
--   1) Optional event_key on driver_notifications for idempotent inserts
--   2) client_notifications (company-scoped via client_can_company)
--   3) staff_notifications (branch-scoped via staff_can_branch)
--
-- Does not expose driver_notifications to clients.
-- Does not weaken existing RLS or UPDATE grants.
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

ALTER TABLE driver_notifications
    ADD COLUMN IF NOT EXISTS event_key text;

CREATE UNIQUE INDEX IF NOT EXISTS driver_notifications_event_key_uq
    ON driver_notifications (event_key)
    WHERE event_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS client_notifications (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    booking_id uuid REFERENCES bookings(id) ON DELETE SET NULL,
    invoice_id uuid REFERENCES invoices(id) ON DELETE SET NULL,
    kind text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    event_key text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT client_notifications_kind_not_blank CHECK (btrim(kind) <> ''),
    CONSTRAINT client_notifications_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT client_notifications_body_not_blank CHECK (btrim(body) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS client_notifications_event_key_uq
    ON client_notifications (event_key)
    WHERE event_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS client_notifications_company_created
    ON client_notifications (company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS client_notifications_unread
    ON client_notifications (company_id)
    WHERE read_at IS NULL;

ALTER TABLE client_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_notifications FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS client_notifications_client_select ON client_notifications;
CREATE POLICY client_notifications_client_select ON client_notifications
    FOR SELECT TO smt_client
    USING (client_can_company(company_id));

DROP POLICY IF EXISTS client_notifications_client_update ON client_notifications;
CREATE POLICY client_notifications_client_update ON client_notifications
    FOR UPDATE TO smt_client
    USING (client_can_company(company_id))
    WITH CHECK (client_can_company(company_id));

DROP POLICY IF EXISTS client_notifications_staff ON client_notifications;
CREATE POLICY client_notifications_staff ON client_notifications
    FOR ALL TO smt_owner, smt_staff
    USING (
        app_is_owner()
        OR EXISTS (
            SELECT 1 FROM company_branches cb
            WHERE cb.company_id = client_notifications.company_id
              AND staff_can_branch(cb.branch_id)
        )
    )
    WITH CHECK (
        app_is_owner()
        OR EXISTS (
            SELECT 1 FROM company_branches cb
            WHERE cb.company_id = client_notifications.company_id
              AND staff_can_branch(cb.branch_id)
        )
    );

DROP POLICY IF EXISTS client_notifications_definer_insert ON client_notifications;
CREATE POLICY client_notifications_definer_insert ON client_notifications
    FOR INSERT TO smt_definer
    WITH CHECK (true);

GRANT SELECT, UPDATE (read_at) ON client_notifications TO smt_client;
GRANT SELECT, INSERT, UPDATE ON client_notifications TO smt_owner, smt_staff;
GRANT INSERT ON client_notifications TO smt_definer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smt_owner, smt_staff, smt_client, smt_definer;

CREATE TABLE IF NOT EXISTS staff_notifications (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id uuid REFERENCES branches(id) ON DELETE SET NULL,
    company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
    booking_id uuid REFERENCES bookings(id) ON DELETE SET NULL,
    driver_id uuid REFERENCES drivers(id) ON DELETE SET NULL,
    invoice_id uuid REFERENCES invoices(id) ON DELETE SET NULL,
    kind text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    event_key text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT staff_notifications_kind_not_blank CHECK (btrim(kind) <> ''),
    CONSTRAINT staff_notifications_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT staff_notifications_body_not_blank CHECK (btrim(body) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS staff_notifications_event_key_uq
    ON staff_notifications (event_key)
    WHERE event_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS staff_notifications_created
    ON staff_notifications (created_at DESC);
CREATE INDEX IF NOT EXISTS staff_notifications_unread
    ON staff_notifications (created_at DESC)
    WHERE read_at IS NULL;

ALTER TABLE staff_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_notifications FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS staff_notifications_staff_select ON staff_notifications;
CREATE POLICY staff_notifications_staff_select ON staff_notifications
    FOR SELECT TO smt_owner, smt_staff
    USING (
        app_is_owner()
        OR branch_id IS NULL
        OR staff_can_branch(branch_id)
    );

DROP POLICY IF EXISTS staff_notifications_staff_update ON staff_notifications;
CREATE POLICY staff_notifications_staff_update ON staff_notifications
    FOR UPDATE TO smt_owner, smt_staff
    USING (
        app_is_owner()
        OR branch_id IS NULL
        OR staff_can_branch(branch_id)
    )
    WITH CHECK (
        app_is_owner()
        OR branch_id IS NULL
        OR staff_can_branch(branch_id)
    );

DROP POLICY IF EXISTS staff_notifications_staff_insert ON staff_notifications;
CREATE POLICY staff_notifications_staff_insert ON staff_notifications
    FOR INSERT TO smt_owner, smt_staff, smt_definer
    WITH CHECK (
        app_is_owner()
        OR branch_id IS NULL
        OR staff_can_branch(branch_id)
        OR current_user = 'smt_definer'
    );

GRANT SELECT, UPDATE (read_at), INSERT ON staff_notifications TO smt_owner, smt_staff;
GRANT INSERT ON staff_notifications TO smt_definer;

CREATE OR REPLACE FUNCTION post_client_notification(
    p_company_id uuid,
    p_kind text,
    p_title text,
    p_body text,
    p_event_key text DEFAULT NULL,
    p_booking_id uuid DEFAULT NULL,
    p_invoice_id uuid DEFAULT NULL,
    p_user_id uuid DEFAULT NULL
) RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    new_id bigint;
BEGIN
    INSERT INTO client_notifications (
        company_id, user_id, booking_id, invoice_id, kind, title, body, event_key
    )
    VALUES (
        p_company_id, p_user_id, p_booking_id, p_invoice_id,
        p_kind, p_title, p_body, p_event_key
    )
    ON CONFLICT DO NOTHING
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$;

ALTER FUNCTION post_client_notification(uuid, text, text, text, text, uuid, uuid, uuid)
    OWNER TO smt_definer;
GRANT EXECUTE ON FUNCTION post_client_notification(uuid, text, text, text, text, uuid, uuid, uuid)
    TO smt_owner, smt_staff, smt_client, smt_definer;

CREATE OR REPLACE FUNCTION post_staff_notification(
    p_kind text,
    p_title text,
    p_body text,
    p_event_key text DEFAULT NULL,
    p_branch_id uuid DEFAULT NULL,
    p_company_id uuid DEFAULT NULL,
    p_booking_id uuid DEFAULT NULL,
    p_driver_id uuid DEFAULT NULL,
    p_invoice_id uuid DEFAULT NULL
) RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    new_id bigint;
BEGIN
    INSERT INTO staff_notifications (
        branch_id, company_id, booking_id, driver_id, invoice_id,
        kind, title, body, event_key
    )
    VALUES (
        p_branch_id, p_company_id, p_booking_id, p_driver_id, p_invoice_id,
        p_kind, p_title, p_body, p_event_key
    )
    ON CONFLICT DO NOTHING
    RETURNING id INTO new_id;
    RETURN new_id;
END;
$$;

ALTER FUNCTION post_staff_notification(text, text, text, text, uuid, uuid, uuid, uuid, uuid)
    OWNER TO smt_definer;
GRANT EXECUTE ON FUNCTION post_staff_notification(text, text, text, text, uuid, uuid, uuid, uuid, uuid)
    TO smt_owner, smt_staff, smt_client, smt_driver, smt_definer;

COMMENT ON TABLE client_notifications IS
    'In-app client portal alerts. Filtered by client_can_company. Not driver_notifications.';
COMMENT ON TABLE staff_notifications IS
    'In-app supervisor alerts for high-signal ops/finance events. Branch-scoped via RLS.';

COMMIT;
