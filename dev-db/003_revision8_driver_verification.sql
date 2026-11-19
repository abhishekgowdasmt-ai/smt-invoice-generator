-- Revision 8 proposal, review 2: driver verification.
-- DESIGN ONLY. Do not run until REVISION_8_DRIVER_VERIFICATION.md is approved.
-- Does not change Revision 7 files, RAC assignments, bookings, JSON, or SQLite.
-- Later local apply, as a superuser, against the existing local smt_dev database:
--   psql "host=127.0.0.1 dbname=smt_dev" -v ON_ERROR_STOP=1 -f dev-db/003_revision8_driver_verification.sql
\set ON_ERROR_STOP on
BEGIN;

-- Existing rows keep their current active value. The default only marks them unverified.
ALTER TABLE drivers
    ADD COLUMN verification_status text NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified', 'verified', 'rejected'));

ALTER TABLE drivers
    ADD CONSTRAINT drivers_rejected_stay_inactive
        CHECK (verification_status <> 'rejected' OR active = false);

CREATE INDEX drivers_verification_status ON drivers (verification_status);

COMMENT ON COLUMN drivers.verification_status IS
    'Owner verification decision. Independent of active. Existing rows become unverified and keep their previous active value. New rows are forced to unverified.';

-- Metadata only. No file path and no file bytes.
CREATE TABLE driver_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id uuid NOT NULL REFERENCES drivers(id) ON DELETE RESTRICT,
    doc_type text NOT NULL,
    doc_number text NOT NULL,
    expiry_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT driver_documents_type_not_blank CHECK (btrim(doc_type) <> ''),
    CONSTRAINT driver_documents_number_not_blank CHECK (btrim(doc_number) <> '')
);

CREATE INDEX driver_documents_driver ON driver_documents (driver_id, doc_type);

COMMENT ON TABLE driver_documents IS
    'Licence and other document metadata. A repeated number does not merge drivers. No file is stored.';

-- Append-only. Submission events and review decisions are different event_kind values.
-- A later rejection does not delete an earlier verification row.
CREATE TABLE driver_verification_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id uuid NOT NULL REFERENCES drivers(id) ON DELETE RESTRICT,
    actor_user_id uuid NOT NULL REFERENCES users(id),
    event_kind text NOT NULL CHECK (event_kind IN ('submission', 'review')),
    event_name text NOT NULL,
    reason text NOT NULL,
    from_status text NOT NULL CHECK (from_status IN ('unverified', 'verified', 'rejected')),
    to_status text NOT NULL CHECK (to_status IN ('unverified', 'verified', 'rejected')),
    active_after boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT driver_verification_reason_not_blank CHECK (btrim(reason) <> ''),
    CONSTRAINT driver_verification_event_name_matches_kind CHECK (
        (event_kind = 'submission' AND event_name IN ('submitted', 'resubmitted'))
        OR (event_kind = 'review' AND event_name IN ('verified', 'rejected'))
    )
);

CREATE INDEX driver_verification_events_driver
    ON driver_verification_events (driver_id, created_at);
CREATE INDEX driver_verification_events_actor
    ON driver_verification_events (actor_user_id, created_at);

COMMENT ON TABLE driver_verification_events IS
    'submitted and resubmitted are submission events. verified and rejected are review decisions. Rows are never updated or deleted.';

-- Operational suspension and restoration. Not a verification event.
-- A row is written only when active actually changes and verification_status does not.
CREATE TABLE driver_active_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id uuid NOT NULL REFERENCES drivers(id) ON DELETE RESTRICT,
    actor_user_id uuid NOT NULL REFERENCES users(id),
    verification_status text NOT NULL
        CHECK (verification_status IN ('unverified', 'verified', 'rejected')),
    active_before boolean NOT NULL,
    active_after boolean NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT driver_active_changes_reason_not_blank CHECK (btrim(reason) <> ''),
    CONSTRAINT driver_active_changes_value_changed CHECK (active_before IS DISTINCT FROM active_after)
);

CREATE INDEX driver_active_changes_driver
    ON driver_active_changes (driver_id, created_at);
CREATE INDEX driver_active_changes_actor
    ON driver_active_changes (actor_user_id, created_at);

COMMENT ON TABLE driver_active_changes IS
    'Append-only audit of owner suspension and restoration. verification_status is a snapshot and is not changed by these rows.';

-- Invoker trigger. Coerces new rows and blocks illegal status or active changes.
-- It is not SECURITY DEFINER: current_user must stay the session role so a
-- direct update cannot look like smt_definer.
CREATE FUNCTION drivers_verification_guard() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog AS $$
DECLARE
    v_event_id text;
    v_events_used text;
    v_change_id text;
    v_changes_used text;
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.verification_status := 'unverified';
        NEW.active := false;
        RETURN NEW;
    END IF;

    IF NEW.verification_status IS DISTINCT FROM OLD.verification_status THEN
        IF current_user IS DISTINCT FROM 'smt_definer' THEN
            RAISE EXCEPTION 'Driver verification changes only through review_driver or resubmit_driver';
        END IF;
        IF NOT (
            (OLD.verification_status = 'unverified' AND NEW.verification_status IN ('verified', 'rejected'))
            OR (OLD.verification_status = 'verified' AND NEW.verification_status = 'rejected')
            OR (OLD.verification_status = 'rejected' AND NEW.verification_status = 'unverified')
        ) THEN
            RAISE EXCEPTION 'Invalid driver verification transition from % to %',
                OLD.verification_status, NEW.verification_status;
        END IF;
        IF NEW.verification_status = 'verified' AND NEW.active IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Approval sets the driver active';
        END IF;
        IF NEW.verification_status IN ('rejected', 'unverified') AND NEW.active IS DISTINCT FROM false THEN
            RAISE EXCEPTION 'Rejection and resubmission leave the driver inactive';
        END IF;
        v_event_id := nullif(current_setting('app.driver_verification_event_id', true), '');
        v_events_used := coalesce(current_setting('app.driver_verification_events_used', true), '');
        IF v_event_id IS NULL
           OR (v_events_used <> '' AND v_event_id = ANY (string_to_array(v_events_used, ','))) THEN
            RAISE EXCEPTION 'A verification change requires a new event for this update';
        END IF;
        IF NOT EXISTS (
            SELECT 1
            FROM public.driver_verification_events r
            WHERE r.id = v_event_id::uuid
              AND r.driver_id = NEW.id
              AND r.from_status = OLD.verification_status
              AND r.to_status = NEW.verification_status
              AND r.active_after = NEW.active
              AND r.actor_user_id = public.app_uid()
              AND r.created_at >= transaction_timestamp()
              AND (
                    (r.event_kind = 'review' AND r.event_name = NEW.verification_status)
                    OR (r.event_kind = 'submission' AND r.event_name = 'resubmitted'
                        AND NEW.verification_status = 'unverified')
                  )
        ) THEN
            RAISE EXCEPTION 'A verification change requires an event recorded in this transaction';
        END IF;
        PERFORM set_config(
            'app.driver_verification_events_used',
            CASE WHEN v_events_used = '' THEN v_event_id ELSE v_events_used || ',' || v_event_id END,
            true
        );
        PERFORM set_config('app.driver_verification_event_id', '', true);
    END IF;

    IF NEW.active IS DISTINCT FROM OLD.active
       AND NEW.verification_status IS NOT DISTINCT FROM OLD.verification_status THEN
        IF current_user IS DISTINCT FROM 'smt_definer' THEN
            RAISE EXCEPTION 'Suspension and restoration go through set_driver_active';
        END IF;
        IF public.app_uid() IS NULL OR NOT public.app_is_owner() THEN
            RAISE EXCEPTION 'Only an owner can change whether a driver is active';
        END IF;
        IF NEW.verification_status IS DISTINCT FROM 'verified' THEN
            RAISE EXCEPTION 'Only a verified driver can be suspended or restored';
        END IF;
        v_change_id := nullif(current_setting('app.driver_active_change_id', true), '');
        v_changes_used := coalesce(current_setting('app.driver_active_changes_used', true), '');
        IF v_change_id IS NULL
           OR (v_changes_used <> '' AND v_change_id = ANY (string_to_array(v_changes_used, ','))) THEN
            RAISE EXCEPTION 'An earlier active-change row cannot authorize another update';
        END IF;
        IF NOT EXISTS (
            SELECT 1
            FROM public.driver_active_changes c
            WHERE c.id = v_change_id::uuid
              AND c.driver_id = NEW.id
              AND c.actor_user_id = public.app_uid()
              AND c.verification_status = NEW.verification_status
              AND c.active_before = OLD.active
              AND c.active_after = NEW.active
              AND c.created_at >= transaction_timestamp()
        ) THEN
            RAISE EXCEPTION 'An active change requires a matching audit row in this transaction';
        END IF;
        PERFORM set_config(
            'app.driver_active_changes_used',
            CASE WHEN v_changes_used = '' THEN v_change_id ELSE v_changes_used || ',' || v_change_id END,
            true
        );
        PERFORM set_config('app.driver_active_change_id', '', true);
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER drivers_verification_guard_trg
    BEFORE INSERT OR UPDATE ON drivers
    FOR EACH ROW EXECUTE FUNCTION drivers_verification_guard();

-- Records the creation submission after the coerced insert. Actor is app.user_id.
CREATE FUNCTION driver_record_submission() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog AS $$
BEGIN
    IF public.app_uid() IS NULL OR NOT public.app_is_owner() THEN
        RAISE EXCEPTION 'Only an owner can create a driver';
    END IF;
    INSERT INTO public.driver_verification_events (
        driver_id, actor_user_id, event_kind, event_name, reason,
        from_status, to_status, active_after
    ) VALUES (
        NEW.id, public.app_uid(), 'submission', 'submitted',
        'Driver record created.',
        'unverified', 'unverified', false
    );
    RETURN NULL;
END;
$$;

CREATE TRIGGER driver_record_submission_trg
    AFTER INSERT ON drivers
    FOR EACH ROW EXECUTE FUNCTION driver_record_submission();

CREATE TRIGGER driver_verification_events_lock
    BEFORE UPDATE OR DELETE ON driver_verification_events
    FOR EACH ROW EXECUTE FUNCTION reject_history_change();

-- Review decisions only. The reviewer id is app.user_id, never a function argument.
CREATE FUNCTION review_driver(p_driver uuid, p_decision text, p_reason text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog AS $$
DECLARE
    v_actor uuid;
    v_old text;
    v_reason text;
    v_active_after boolean;
    v_event uuid;
BEGIN
    v_actor := public.app_uid();
    IF v_actor IS NULL OR NOT public.app_is_owner() THEN
        RAISE EXCEPTION 'Only an owner can review a driver';
    END IF;
    v_reason := btrim(p_reason);
    IF v_reason IS NULL OR v_reason = '' THEN
        RAISE EXCEPTION 'A review reason is required';
    END IF;
    IF p_decision IS DISTINCT FROM 'verified' AND p_decision IS DISTINCT FROM 'rejected' THEN
        RAISE EXCEPTION 'Review decision must be verified or rejected';
    END IF;

    SELECT verification_status
      INTO v_old
    FROM public.drivers
    WHERE id = p_driver
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Driver not found';
    END IF;

    IF p_decision = 'verified' THEN
        IF v_old IS DISTINCT FROM 'unverified' THEN
            RAISE EXCEPTION 'A driver can be verified only from unverified. Resubmit a rejected driver first.';
        END IF;
        v_active_after := true;
    ELSE
        IF v_old = 'rejected' THEN
            RAISE EXCEPTION 'This driver is already rejected';
        END IF;
        v_active_after := false;
    END IF;

    INSERT INTO public.driver_verification_events (
        driver_id, actor_user_id, event_kind, event_name, reason,
        from_status, to_status, active_after
    ) VALUES (
        p_driver, v_actor, 'review', p_decision, v_reason,
        v_old, p_decision, v_active_after
    )
    RETURNING id INTO v_event;
    PERFORM set_config('app.driver_verification_event_id', v_event::text, true);

    UPDATE public.drivers
       SET verification_status = p_decision,
           active = v_active_after
     WHERE id = p_driver;
END;
$$;

-- Submission event. Does not approve the driver and does not delete the rejection row.
CREATE FUNCTION resubmit_driver(p_driver uuid, p_reason text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog AS $$
DECLARE
    v_actor uuid;
    v_old text;
    v_reason text;
    v_event uuid;
BEGIN
    v_actor := public.app_uid();
    IF v_actor IS NULL OR NOT public.app_is_owner() THEN
        RAISE EXCEPTION 'Only an owner can resubmit a driver';
    END IF;
    v_reason := btrim(p_reason);
    IF v_reason IS NULL OR v_reason = '' THEN
        RAISE EXCEPTION 'A resubmission reason is required';
    END IF;

    SELECT verification_status
      INTO v_old
    FROM public.drivers
    WHERE id = p_driver
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Driver not found';
    END IF;
    IF v_old IS DISTINCT FROM 'rejected' THEN
        RAISE EXCEPTION 'Only a rejected driver can be resubmitted';
    END IF;

    INSERT INTO public.driver_verification_events (
        driver_id, actor_user_id, event_kind, event_name, reason,
        from_status, to_status, active_after
    ) VALUES (
        p_driver, v_actor, 'submission', 'resubmitted', v_reason,
        'rejected', 'unverified', false
    )
    RETURNING id INTO v_event;
    PERFORM set_config('app.driver_verification_event_id', v_event::text, true);

    UPDATE public.drivers
       SET verification_status = 'unverified',
           active = false
     WHERE id = p_driver;
END;
$$;

-- Suspension and restoration. Does not change verification_status.
-- An unchanged active value writes nothing and updates nothing.
CREATE FUNCTION set_driver_active(p_driver uuid, p_active boolean, p_reason text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog AS $$
DECLARE
    v_actor uuid;
    v_status text;
    v_active boolean;
    v_reason text;
    v_change uuid;
BEGIN
    v_actor := public.app_uid();
    IF v_actor IS NULL OR NOT public.app_is_owner() THEN
        RAISE EXCEPTION 'Only an owner can suspend or restore a driver';
    END IF;
    IF p_active IS NULL THEN
        RAISE EXCEPTION 'Active must be true or false';
    END IF;
    v_reason := btrim(p_reason);
    IF v_reason IS NULL OR v_reason = '' THEN
        RAISE EXCEPTION 'A reason is required to suspend or restore a driver';
    END IF;

    SELECT verification_status, active
      INTO v_status, v_active
    FROM public.drivers
    WHERE id = p_driver
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Driver not found';
    END IF;
    IF v_status IS DISTINCT FROM 'verified' THEN
        RAISE EXCEPTION 'Only a verified driver can be suspended or restored';
    END IF;
    IF v_active IS NOT DISTINCT FROM p_active THEN
        RETURN;
    END IF;

    INSERT INTO public.driver_active_changes (
        driver_id, actor_user_id, verification_status,
        active_before, active_after, reason
    ) VALUES (
        p_driver, v_actor, v_status,
        v_active, p_active, v_reason
    )
    RETURNING id INTO v_change;
    PERFORM set_config('app.driver_active_change_id', v_change::text, true);

    UPDATE public.drivers
       SET active = p_active
     WHERE id = p_driver;
END;
$$;

REVOKE ALL ON FUNCTION review_driver(uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION resubmit_driver(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION set_driver_active(uuid, boolean, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION driver_record_submission() FROM PUBLIC;
REVOKE ALL ON FUNCTION drivers_verification_guard() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION review_driver(uuid, text, text) TO smt_owner;
GRANT EXECUTE ON FUNCTION resubmit_driver(uuid, text) TO smt_owner;
GRANT EXECUTE ON FUNCTION set_driver_active(uuid, boolean, text) TO smt_owner;
GRANT EXECUTE ON FUNCTION app_is_owner() TO smt_definer;
ALTER FUNCTION review_driver(uuid, text, text) OWNER TO smt_definer;
ALTER FUNCTION resubmit_driver(uuid, text) OWNER TO smt_definer;
ALTER FUNCTION set_driver_active(uuid, boolean, text) OWNER TO smt_definer;
ALTER FUNCTION driver_record_submission() OWNER TO smt_definer;

REVOKE UPDATE ON drivers FROM smt_owner, smt_staff;
GRANT UPDATE (
    user_id, primary_branch_id, display_name, phone, whatsapp_number,
    alternate_number, license_number, license_expiry, home_area, notes,
    legacy_source, legacy_driver_id, legacy_sqlite_id, branch_inferred
) ON drivers TO smt_owner, smt_staff;
GRANT UPDATE (verification_status, active) ON drivers TO smt_definer;
GRANT SELECT (verification_status, active) ON drivers TO smt_definer;
GRANT SELECT, INSERT ON driver_verification_events TO smt_definer;
GRANT SELECT, INSERT ON driver_active_changes TO smt_definer;

GRANT SELECT, INSERT, UPDATE, DELETE ON driver_documents TO smt_owner;
GRANT SELECT ON driver_documents TO smt_staff;
GRANT SELECT ON driver_verification_events TO smt_owner, smt_staff;
GRANT SELECT ON driver_active_changes TO smt_owner, smt_staff;

ALTER TABLE driver_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE driver_verification_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_verification_events FORCE ROW LEVEL SECURITY;
ALTER TABLE driver_active_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_active_changes FORCE ROW LEVEL SECURITY;

CREATE POLICY driver_documents_read ON driver_documents
    FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_documents.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

CREATE POLICY driver_documents_insert ON driver_documents
    FOR INSERT TO smt_owner
    WITH CHECK (
        app_is_owner()
        AND EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_documents.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

CREATE POLICY driver_documents_update ON driver_documents
    FOR UPDATE TO smt_owner
    USING (
        app_is_owner()
        AND EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_documents.driver_id
              AND staff_can_branch(db.branch_id)
        )
    )
    WITH CHECK (
        app_is_owner()
        AND EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_documents.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

CREATE POLICY driver_documents_delete ON driver_documents
    FOR DELETE TO smt_owner
    USING (
        app_is_owner()
        AND EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_documents.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

CREATE POLICY driver_verification_events_read ON driver_verification_events
    FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_verification_events.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

CREATE TRIGGER driver_active_changes_lock
    BEFORE UPDATE OR DELETE ON driver_active_changes
    FOR EACH ROW EXECUTE FUNCTION reject_history_change();

CREATE POLICY driver_active_changes_read ON driver_active_changes
    FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_active_changes.driver_id
              AND staff_can_branch(db.branch_id)
        )
    );

-- Explicit row permissions for the history writer.
-- Revision 7 gives smt_definer BYPASSRLS, so PostgreSQL does not consult these
-- policies for that role. row_security=off is not a bypass and is not set here.
-- The policies are the allow rule for a non-bypass execution: SELECT and INSERT
-- only, and only for a row whose actor is the current owner. There is no UPDATE
-- or DELETE policy. smt_owner, smt_staff, smt_driver, smt_client, and smt_migrate
-- are not named by these policies and have no insert or modification grant.
CREATE POLICY driver_verification_events_definer_read ON driver_verification_events
    FOR SELECT TO smt_definer
    USING (actor_user_id = app_uid() AND app_is_owner());

CREATE POLICY driver_verification_events_definer_insert ON driver_verification_events
    FOR INSERT TO smt_definer
    WITH CHECK (actor_user_id = app_uid() AND app_is_owner());

CREATE POLICY driver_active_changes_definer_read ON driver_active_changes
    FOR SELECT TO smt_definer
    USING (actor_user_id = app_uid() AND app_is_owner());

CREATE POLICY driver_active_changes_definer_insert ON driver_active_changes
    FOR INSERT TO smt_definer
    WITH CHECK (actor_user_id = app_uid() AND app_is_owner());

CREATE FUNCTION driver_phone_key(value text) RETURNS text
LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog AS $$
    SELECT CASE
        WHEN digits ~ '^91[0-9]{10}$' THEN substr(digits, 3)
        WHEN digits ~ '^0[0-9]{10}$' THEN substr(digits, 2)
        ELSE NULLIF(digits, '')
    END
    FROM (SELECT regexp_replace(coalesce(value, ''), '\D', '', 'g') AS digits) s
    WHERE length(regexp_replace(coalesce(value, ''), '\D', '', 'g')) >= 10
$$;

REVOKE ALL ON FUNCTION driver_phone_key(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION driver_phone_key(text) TO smt_owner;

CREATE VIEW driver_duplicate_warnings
WITH (security_invoker = true) AS
SELECT 'phone'::text AS match_kind,
       driver_phone_key(a.phone) AS match_value,
       a.id AS driver_id,
       b.id AS other_driver_id
FROM drivers a
JOIN drivers b
  ON a.id < b.id
 AND driver_phone_key(a.phone) IS NOT NULL
 AND driver_phone_key(a.phone) = driver_phone_key(b.phone)
UNION ALL
SELECT 'licence'::text,
       lower(btrim(a.license_number)),
       a.id,
       b.id
FROM drivers a
JOIN drivers b
  ON a.id < b.id
 AND NULLIF(btrim(a.license_number), '') IS NOT NULL
 AND lower(btrim(a.license_number)) = lower(btrim(b.license_number));

GRANT SELECT ON driver_duplicate_warnings TO smt_owner;

COMMIT;
