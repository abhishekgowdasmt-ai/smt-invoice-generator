-- SMT development schema, taken from POSTGRESQL_SCHEMA_PLAN.md Revision 7.
-- Run with psql as a local superuser, connected to an empty database named smt_dev.
-- Requires PostgreSQL 15 or newer. Does not create the database, set a password,
-- load staging rows, or create promote_staged_booking.
\set ON_ERROR_STOP on
BEGIN;

CREATE FUNCTION null_if_blank(value text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(btrim(value), '')
$$;

CREATE FUNCTION app_uid() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

CREATE TABLE branches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    city text NOT NULL,
    timezone text NOT NULL DEFAULT 'Asia/Kolkata',
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role text NOT NULL CHECK (role IN ('owner', 'staff', 'driver', 'client')),
    full_name text NOT NULL,
    email text,
    phone text,
    password_hash text,
    google_sub text,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_not_blank CHECK (email IS NULL OR btrim(email) <> ''),
    CONSTRAINT users_phone_not_blank CHECK (phone IS NULL OR btrim(phone) <> ''),
    CONSTRAINT users_google_not_blank CHECK (google_sub IS NULL OR btrim(google_sub) <> '')
);

CREATE UNIQUE INDEX users_email_uq ON users (lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX users_google_uq ON users (google_sub) WHERE google_sub IS NOT NULL;

CREATE TABLE user_branch_access (
    user_id uuid NOT NULL REFERENCES users(id),
    branch_id uuid NOT NULL REFERENCES branches(id),
    PRIMARY KEY (user_id, branch_id)
);

CREATE TABLE companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    contact_person text,
    contact_email text,
    contact_phone text,
    address text,
    legacy_source text,
    legacy_id text,
    CONSTRAINT companies_legacy_pair CHECK (
        (legacy_source IS NULL AND legacy_id IS NULL)
        OR (legacy_source IS NOT NULL AND legacy_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX companies_legacy_uq
    ON companies (legacy_source, legacy_id)
    WHERE legacy_id IS NOT NULL;

CREATE TABLE company_branches (
    company_id uuid NOT NULL REFERENCES companies(id),
    branch_id uuid NOT NULL REFERENCES branches(id),
    PRIMARY KEY (company_id, branch_id)
);
CREATE INDEX company_branches_branch ON company_branches (branch_id);

CREATE TABLE user_company_links (
    user_id uuid NOT NULL REFERENCES users(id),
    company_id uuid NOT NULL REFERENCES companies(id),
    PRIMARY KEY (user_id, company_id)
);
CREATE INDEX user_company_links_company ON user_company_links (company_id);

CREATE TABLE drivers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id),
    primary_branch_id uuid NOT NULL REFERENCES branches(id),
    display_name text NOT NULL,
    phone text,
    whatsapp_number text,
    alternate_number text,
    license_number text,
    license_expiry date,
    home_area text,
    active boolean NOT NULL DEFAULT true,
    notes text,
    legacy_source text,
    legacy_driver_id text,
    legacy_sqlite_id integer,
    branch_inferred boolean NOT NULL DEFAULT false
);

CREATE UNIQUE INDEX drivers_user_uq ON drivers (user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX drivers_legacy_uq
    ON drivers (legacy_source, legacy_driver_id)
    WHERE legacy_driver_id IS NOT NULL;
CREATE UNIQUE INDEX drivers_sqlite_uq
    ON drivers (legacy_sqlite_id)
    WHERE legacy_sqlite_id IS NOT NULL;
CREATE INDEX drivers_primary_branch ON drivers (primary_branch_id);

CREATE TABLE driver_branches (
    driver_id uuid NOT NULL REFERENCES drivers(id),
    branch_id uuid NOT NULL REFERENCES branches(id),
    PRIMARY KEY (driver_id, branch_id)
);
CREATE INDEX driver_branches_branch ON driver_branches (branch_id);

CREATE TABLE vehicles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id uuid NOT NULL REFERENCES branches(id),
    registration_number text,
    model text,
    capacity integer,
    fuel_type text,
    is_ev boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    usual_driver_id uuid REFERENCES drivers(id),
    legacy_source text,
    legacy_id text,
    identity_status text NOT NULL DEFAULT 'clean'
        CHECK (identity_status IN ('clean', 'conflict')),
    branch_inferred boolean NOT NULL DEFAULT false,
    CONSTRAINT registration_not_blank CHECK (
        registration_number IS NULL OR btrim(registration_number) <> ''
    )
);

CREATE UNIQUE INDEX vehicles_registration_clean
    ON vehicles (registration_number)
    WHERE registration_number IS NOT NULL AND identity_status = 'clean';
CREATE INDEX vehicles_branch ON vehicles (branch_id);
CREATE INDEX vehicles_usual_driver ON vehicles (usual_driver_id);

CREATE TABLE vehicle_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id uuid NOT NULL REFERENCES vehicles(id),
    doc_type text NOT NULL,
    doc_number text NOT NULL,
    expiry_date date,
    legacy_sqlite_id integer
);

CREATE UNIQUE INDEX vehicle_documents_legacy_uq
    ON vehicle_documents (legacy_sqlite_id)
    WHERE legacy_sqlite_id IS NOT NULL;
CREATE INDEX vehicle_documents_vehicle ON vehicle_documents (vehicle_id);

CREATE TABLE company_vehicles (
    company_id uuid NOT NULL REFERENCES companies(id),
    vehicle_id uuid NOT NULL REFERENCES vehicles(id),
    PRIMARY KEY (company_id, vehicle_id)
);
CREATE INDEX company_vehicles_vehicle ON company_vehicles (vehicle_id);

CREATE TABLE company_drivers (
    company_id uuid NOT NULL REFERENCES companies(id),
    driver_id uuid NOT NULL REFERENCES drivers(id),
    PRIMARY KEY (company_id, driver_id)
);
CREATE INDEX company_drivers_driver ON company_drivers (driver_id);

CREATE TABLE enquiries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id uuid REFERENCES branches(id),
    company_id uuid REFERENCES companies(id),
    contact_name text NOT NULL,
    email text,
    phone text,
    company_name text,
    service_type text NOT NULL,
    employee_count integer,
    details text,
    status text NOT NULL CHECK (status IN (
        'pending', 'in_progress', 'accepted', 'declined', 'completed'
    )),
    legacy_sqlite_id integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX enquiries_legacy_uq
    ON enquiries (legacy_sqlite_id)
    WHERE legacy_sqlite_id IS NOT NULL;
CREATE INDEX enquiries_branch ON enquiries (branch_id);
CREATE INDEX enquiries_company ON enquiries (company_id);

CREATE TABLE ets_contracts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id),
    branch_id uuid NOT NULL REFERENCES branches(id),
    route_name text NOT NULL,
    planned_start text,
    route_text text,
    cab_type text,
    days_of_week smallint[] NOT NULL,
    shift_start time NOT NULL,
    shift_end time,
    active_from date NOT NULL,
    active_until date,
    status text NOT NULL CHECK (status IN ('draft', 'active', 'paused', 'ended')),
    CONSTRAINT ets_days_known CHECK (
        days_of_week <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]
        AND cardinality(days_of_week) > 0
    ),
    CONSTRAINT ets_dates CHECK (active_until IS NULL OR active_until >= active_from),
    CONSTRAINT ets_company_branch_fk
        FOREIGN KEY (company_id, branch_id)
        REFERENCES company_branches (company_id, branch_id),
    UNIQUE (id, company_id, branch_id)
);

CREATE INDEX ets_contracts_company ON ets_contracts (company_id, status);
CREATE INDEX ets_contracts_branch ON ets_contracts (branch_id);

CREATE TABLE import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_batch_id text,
    file_name text,
    file_size integer,
    uploaded_by text,
    total_rows integer,
    success_rows integer,
    failed_rows integer,
    import_status text,
    error_summary jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX import_batches_legacy_uq
    ON import_batches (legacy_batch_id)
    WHERE legacy_batch_id IS NOT NULL;

CREATE TABLE bookings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id uuid NOT NULL REFERENCES branches(id),
    company_id uuid REFERENCES companies(id),
    contract_id uuid REFERENCES ets_contracts(id),
    enquiry_id uuid REFERENCES enquiries(id),
    import_batch_id uuid REFERENCES import_batches(id),
    origin text NOT NULL CHECK (origin IN ('rac', 'ets_occurrence', 'retail')),
    legacy_source text,
    legacy_booking_id text,
    source_booking_id text,
    identity_status text NOT NULL DEFAULT 'clean' CHECK (identity_status IN (
        'clean', 'conflict', 'missing_code'
    )),
    trip_date date,
    pickup_time time,
    end_time time,
    duty_type text,
    cab_type text,
    planned_start text,
    route_text text,
    employee_name text,
    source_name text,
    source_mobile text,
    source_vehicle_no text,
    status text NOT NULL CHECK (status IN (
        'unassigned', 'assigned', 'accepted', 'started', 'completed', 'cancelled'
    )),
    remarks text,
    ingest_source text,
    ingest_message_id text,
    ingest_confidence numeric(5, 2),
    branch_inferred boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT booking_code_not_blank CHECK (
        source_booking_id IS NULL OR btrim(source_booking_id) <> ''
    ),
    CONSTRAINT legacy_booking_not_blank CHECK (
        legacy_booking_id IS NULL OR btrim(legacy_booking_id) <> ''
    ),
    CONSTRAINT ets_booking_has_contract CHECK (
        origin <> 'ets_occurrence'
        OR (contract_id IS NOT NULL AND company_id IS NOT NULL)
    ),
    CONSTRAINT booking_company_branch_fk
        FOREIGN KEY (company_id, branch_id)
        REFERENCES company_branches (company_id, branch_id),
    CONSTRAINT booking_matches_contract_fk
        FOREIGN KEY (contract_id, company_id, branch_id)
        REFERENCES ets_contracts (id, company_id, branch_id)
);

CREATE UNIQUE INDEX bookings_legacy_uq
    ON bookings (legacy_source, legacy_booking_id)
    WHERE legacy_booking_id IS NOT NULL;
CREATE UNIQUE INDEX bookings_clean_source_code
    ON bookings (branch_id, source_booking_id, trip_date)
    WHERE source_booking_id IS NOT NULL AND identity_status = 'clean';
CREATE UNIQUE INDEX bookings_contract_day
    ON bookings (contract_id, trip_date)
    WHERE contract_id IS NOT NULL;
CREATE UNIQUE INDEX bookings_one_enquiry
    ON bookings (enquiry_id)
    WHERE enquiry_id IS NOT NULL;
CREATE INDEX bookings_branch_date ON bookings (branch_id, trip_date);
CREATE INDEX bookings_company_date ON bookings (company_id, trip_date);
CREATE INDEX bookings_status ON bookings (branch_id, status);
CREATE INDEX bookings_import_batch ON bookings (import_batch_id);

CREATE FUNCTION generate_ets_occurrences(
    p_contract uuid,
    p_from date,
    p_to date
) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    inserted integer;
BEGIN
    INSERT INTO bookings (
        id, branch_id, company_id, contract_id, origin, trip_date,
        pickup_time, end_time, cab_type, planned_start, route_text, status
    )
    SELECT
        gen_random_uuid(), c.branch_id, c.company_id, c.id, 'ets_occurrence',
        d::date, c.shift_start, c.shift_end, c.cab_type, c.planned_start,
        c.route_text, 'unassigned'
    FROM ets_contracts c
    JOIN generate_series(p_from, p_to, interval '1 day') AS d
        ON EXTRACT(ISODOW FROM d)::smallint = ANY (c.days_of_week)
    WHERE c.id = p_contract
      AND c.status = 'active'
      AND d::date >= c.active_from
      AND (c.active_until IS NULL OR d::date <= c.active_until)
    ON CONFLICT (contract_id, trip_date) WHERE contract_id IS NOT NULL DO NOTHING;

    GET DIAGNOSTICS inserted = ROW_COUNT;
    RETURN inserted;
END;
$$;

CREATE TABLE booking_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES bookings(id),
    driver_id uuid NOT NULL REFERENCES drivers(id),
    vehicle_id uuid REFERENCES vehicles(id),
    assigned_by uuid REFERENCES users(id),
    status text NOT NULL CHECK (status IN (
        'assigned', 'accepted', 'rejected', 'withdrawn', 'superseded', 'completed'
    )),
    notes text,
    rejection_reason text,
    whatsapp_status text,
    legacy_assignment_id text,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    decided_by uuid REFERENCES users(id),
    CONSTRAINT assignment_legacy_not_blank CHECK (
        legacy_assignment_id IS NULL OR btrim(legacy_assignment_id) <> ''
    ),
    CONSTRAINT rejection_has_reason CHECK (
        status <> 'rejected' OR btrim(rejection_reason) <> ''
    )
);

CREATE UNIQUE INDEX assignments_legacy_uq
    ON booking_assignments (legacy_assignment_id)
    WHERE legacy_assignment_id IS NOT NULL;
CREATE UNIQUE INDEX one_open_assignment_per_booking
    ON booking_assignments (booking_id)
    WHERE status IN ('assigned', 'accepted');
CREATE INDEX assignments_driver_time ON booking_assignments (driver_id, assigned_at);
CREATE INDEX assignments_vehicle ON booking_assignments (vehicle_id);
CREATE INDEX assignments_assigned_by ON booking_assignments (assigned_by);
CREATE INDEX assignments_decided_by ON booking_assignments (decided_by);

CREATE TABLE assignment_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id uuid NOT NULL REFERENCES booking_assignments(id),
    old_status text,
    new_status text NOT NULL,
    actor_user_id uuid REFERENCES users(id),
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX assignment_events_assignment
    ON assignment_events (assignment_id, created_at);
CREATE INDEX assignment_events_actor ON assignment_events (actor_user_id, created_at);

CREATE TABLE trip_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id uuid REFERENCES booking_assignments(id),
    driver_id uuid REFERENCES drivers(id),
    session_origin text NOT NULL CHECK (session_origin IN ('duty', 'website_demo')),
    status text NOT NULL CHECK (status IN ('active', 'closed', 'cancelled')),
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    started_by uuid REFERENCES users(id),
    CONSTRAINT duty_session_shape CHECK (
        (session_origin = 'duty' AND assignment_id IS NOT NULL AND driver_id IS NOT NULL)
        OR (session_origin = 'website_demo' AND assignment_id IS NULL)
    ),
    CONSTRAINT session_times CHECK (
        (status = 'active' AND ended_at IS NULL)
        OR (status IN ('closed', 'cancelled') AND ended_at IS NOT NULL AND ended_at >= started_at)
    )
);

CREATE UNIQUE INDEX one_active_session_per_driver
    ON trip_sessions (driver_id)
    WHERE status = 'active' AND driver_id IS NOT NULL;
CREATE UNIQUE INDEX one_active_session_per_assignment
    ON trip_sessions (assignment_id)
    WHERE status = 'active' AND assignment_id IS NOT NULL;
CREATE INDEX trip_sessions_driver ON trip_sessions (driver_id, started_at);
CREATE INDEX trip_sessions_started_by ON trip_sessions (started_by);

CREATE TABLE gps_positions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_session_id uuid NOT NULL REFERENCES trip_sessions(id),
    recorded_at timestamptz NOT NULL,
    latitude numeric(9, 6) NOT NULL,
    longitude numeric(9, 6) NOT NULL,
    accuracy_m numeric(8, 2),
    CONSTRAINT gps_latitude CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT gps_longitude CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX gps_by_session_time ON gps_positions (trip_session_id, recorded_at);

CREATE TABLE trip_passengers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_session_id uuid REFERENCES trip_sessions(id),
    passenger_name text NOT NULL,
    stop_name text,
    status text,
    legacy_sqlite_id integer
);

CREATE UNIQUE INDEX trip_passengers_legacy_uq
    ON trip_passengers (legacy_sqlite_id)
    WHERE legacy_sqlite_id IS NOT NULL;
CREATE INDEX trip_passengers_session ON trip_passengers (trip_session_id);

CREATE TABLE safety_alerts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_session_id uuid REFERENCES trip_sessions(id),
    alert_type text NOT NULL,
    details text NOT NULL,
    status text,
    legacy_sqlite_id integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX safety_alerts_legacy_uq
    ON safety_alerts (legacy_sqlite_id)
    WHERE legacy_sqlite_id IS NOT NULL;
CREATE INDEX safety_alerts_session ON safety_alerts (trip_session_id);

CREATE TABLE booking_charges (
    booking_id uuid PRIMARY KEY REFERENCES bookings(id),
    currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    customer_amount numeric(12, 2),
    toll numeric(12, 2),
    parking numeric(12, 2),
    CONSTRAINT charges_nonnegative CHECK (
        (customer_amount IS NULL OR customer_amount >= 0)
        AND (toll IS NULL OR toll >= 0)
        AND (parking IS NULL OR parking >= 0)
    )
);

CREATE TABLE duty_readings (
    booking_id uuid PRIMARY KEY REFERENCES bookings(id),
    start_km numeric(10, 1),
    end_km numeric(10, 1),
    total_km numeric(10, 1),
    driver_hours numeric(8, 2),
    driver_km numeric(10, 1)
);

CREATE TABLE invoices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id uuid NOT NULL REFERENCES branches(id),
    company_id uuid NOT NULL REFERENCES companies(id),
    currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    invoice_number text NOT NULL,
    period_start date,
    period_end date,
    issued_at timestamptz,
    CONSTRAINT invoice_company_branch_fk
        FOREIGN KEY (company_id, branch_id)
        REFERENCES company_branches (company_id, branch_id)
);

CREATE UNIQUE INDEX invoices_number_uq ON invoices (invoice_number);
CREATE INDEX invoices_company ON invoices (company_id, issued_at);
CREATE INDEX invoices_branch ON invoices (branch_id);

CREATE TABLE invoice_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id uuid NOT NULL REFERENCES invoices(id),
    booking_id uuid REFERENCES bookings(id),
    description text NOT NULL,
    amount numeric(12, 2) NOT NULL CHECK (amount >= 0)
);

CREATE UNIQUE INDEX one_invoice_line_per_booking
    ON invoice_lines (booking_id)
    WHERE booking_id IS NOT NULL;
CREATE INDEX invoice_lines_invoice ON invoice_lines (invoice_id);

CREATE TABLE payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id uuid NOT NULL REFERENCES invoices(id),
    currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    amount numeric(12, 2) NOT NULL CHECK (amount > 0),
    paid_on date NOT NULL,
    method text,
    reference text,
    import_key text,
    CONSTRAINT payment_reference_not_blank CHECK (
        reference IS NULL OR btrim(reference) <> ''
    ),
    CONSTRAINT payment_import_not_blank CHECK (
        import_key IS NULL OR btrim(import_key) <> ''
    )
);

CREATE UNIQUE INDEX payments_import_key_uq
    ON payments (import_key)
    WHERE import_key IS NOT NULL;
CREATE UNIQUE INDEX payments_reference_uq
    ON payments (invoice_id, reference)
    WHERE reference IS NOT NULL;
CREATE INDEX payments_invoice ON payments (invoice_id, paid_on);

CREATE TABLE driver_payouts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES bookings(id),
    driver_id uuid NOT NULL REFERENCES drivers(id),
    currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    status text NOT NULL,
    amount numeric(12, 2) CHECK (amount IS NULL OR amount >= 0),
    paid_at timestamptz,
    notes text
);

CREATE INDEX driver_payouts_booking ON driver_payouts (booking_id);
CREATE INDEX driver_payouts_driver ON driver_payouts (driver_id, paid_at);

CREATE VIEW invoice_balances
WITH (security_invoker = true) AS
SELECT
    i.id AS invoice_id,
    i.branch_id,
    i.company_id,
    i.invoice_number,
    COALESCE(lines.total_amount, 0) AS total_amount,
    COALESCE(pays.paid_amount, 0) AS paid_amount,
    COALESCE(lines.total_amount, 0) - COALESCE(pays.paid_amount, 0) AS outstanding_amount
FROM invoices i
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS total_amount
    FROM invoice_lines
    GROUP BY invoice_id
) lines ON lines.invoice_id = i.id
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS paid_amount
    FROM payments
    GROUP BY invoice_id
) pays ON pays.invoice_id = i.id;

CREATE TABLE chat_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_session_id text,
    company_id uuid REFERENCES companies(id),
    branch_id uuid REFERENCES branches(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_session_not_blank CHECK (
        legacy_session_id IS NULL OR btrim(legacy_session_id) <> ''
    )
);

CREATE UNIQUE INDEX chat_sessions_legacy_uq
    ON chat_sessions (legacy_session_id)
    WHERE legacy_session_id IS NOT NULL;
CREATE INDEX chat_sessions_company ON chat_sessions (company_id);

CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id uuid REFERENCES branches(id),
    company_id uuid REFERENCES companies(id),
    booking_id uuid REFERENCES bookings(id),
    assignment_id uuid REFERENCES booking_assignments(id),
    chat_session_id uuid REFERENCES chat_sessions(id),
    channel text NOT NULL CHECK (channel IN ('whatsapp', 'website_chat', 'sms')),
    direction text NOT NULL CHECK (direction IN ('out', 'in')),
    phone text,
    body text,
    send_status text,
    legacy_source text,
    legacy_message_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT message_legacy_not_blank CHECK (
        legacy_message_id IS NULL OR btrim(legacy_message_id) <> ''
    )
);

CREATE UNIQUE INDEX messages_legacy_uq
    ON messages (legacy_source, legacy_message_id)
    WHERE legacy_message_id IS NOT NULL;
CREATE INDEX messages_booking ON messages (booking_id, created_at);
CREATE INDEX messages_assignment ON messages (assignment_id);
CREATE INDEX messages_session ON messages (chat_session_id, created_at);
CREATE INDEX messages_branch ON messages (branch_id, created_at);
CREATE INDEX messages_company ON messages (company_id, created_at);

CREATE TABLE booking_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    booking_id uuid NOT NULL REFERENCES bookings(id),
    old_status text,
    new_status text NOT NULL,
    actor_user_id uuid REFERENCES users(id),
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX booking_events_booking ON booking_events (booking_id, created_at);
CREATE INDEX booking_events_actor ON booking_events (actor_user_id, created_at);

CREATE TABLE audit_logs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id uuid REFERENCES users(id),
    branch_id uuid REFERENCES branches(id),
    action text NOT NULL,
    entity_name text NOT NULL,
    entity_id text,
    summary text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_logs_entity ON audit_logs (entity_name, entity_id, created_at);
CREATE INDEX audit_logs_branch ON audit_logs (branch_id, created_at);
CREATE INDEX audit_logs_actor ON audit_logs (actor_user_id, created_at);

CREATE FUNCTION reject_history_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER booking_events_lock
    BEFORE UPDATE OR DELETE ON booking_events
    FOR EACH ROW EXECUTE FUNCTION reject_history_change();
CREATE TRIGGER assignment_events_lock
    BEFORE UPDATE OR DELETE ON assignment_events
    FOR EACH ROW EXECUTE FUNCTION reject_history_change();
CREATE TRIGGER audit_logs_lock
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION reject_history_change();

CREATE FUNCTION bookings_blank_and_code() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.legacy_booking_id := null_if_blank(NEW.legacy_booking_id);
    NEW.source_booking_id := null_if_blank(NEW.source_booking_id);
    NEW.legacy_source := null_if_blank(NEW.legacy_source);
    IF NEW.origin = 'rac'
       AND NEW.source_booking_id IS NULL
       AND NEW.identity_status = 'clean' THEN
        NEW.identity_status := 'missing_code';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER bookings_blank_and_code_trg
    BEFORE INSERT OR UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION bookings_blank_and_code();

CREATE FUNCTION bookings_status_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'unassigned' THEN
            RAISE EXCEPTION 'A new booking starts as unassigned';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF NOT (
        (OLD.status = 'unassigned' AND NEW.status IN ('assigned', 'cancelled'))
        OR (OLD.status = 'assigned' AND NEW.status IN ('accepted', 'unassigned', 'cancelled'))
        OR (OLD.status = 'accepted' AND NEW.status IN ('started', 'cancelled'))
        OR (OLD.status = 'started' AND NEW.status IN ('completed', 'cancelled'))
    ) THEN
        RAISE EXCEPTION 'Invalid booking transition from % to %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER bookings_status_guard_trg
    BEFORE UPDATE OR INSERT ON bookings
    FOR EACH ROW EXECUTE FUNCTION bookings_status_guard();

CREATE FUNCTION bookings_write_event_and_close() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    close_reason text;
    active_duty integer;
    cancelled_duty integer;
BEGIN
    IF TG_TABLE_SCHEMA IS DISTINCT FROM 'public'
       OR TG_TABLE_NAME IS DISTINCT FROM 'bookings' THEN
        RAISE EXCEPTION 'bookings_write_event_and_close runs only on public.bookings';
    END IF;
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.booking_events (booking_id, old_status, new_status, actor_user_id)
        VALUES (NEW.id, NULL, NEW.status, public.app_uid());
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO public.booking_events (booking_id, old_status, new_status, actor_user_id)
        VALUES (NEW.id, OLD.status, NEW.status, public.app_uid());
    END IF;
    -- No custom setting is read here. A driver close has already changed the
    -- session, so the reason comes from that row. A staff change still sees
    -- an active session and uses the booking reason.
    IF TG_OP = 'UPDATE'
       AND NEW.status IN ('completed', 'cancelled')
       AND NEW.status IS DISTINCT FROM OLD.status THEN
        PERFORM 1
        FROM public.trip_sessions s
        JOIN public.booking_assignments a ON a.id = s.assignment_id
        WHERE a.booking_id = NEW.id
          AND s.session_origin = 'duty'
        FOR UPDATE OF s;
        SELECT count(*) FILTER (WHERE s.status = 'active'),
               count(*) FILTER (WHERE s.status = 'cancelled')
        INTO active_duty, cancelled_duty
        FROM public.trip_sessions s
        JOIN public.booking_assignments a ON a.id = s.assignment_id
        WHERE a.booking_id = NEW.id
          AND s.session_origin = 'duty';
        IF NEW.status = 'completed' THEN
            close_reason := 'Trip completed';
        ELSIF cancelled_duty > 0 AND active_duty = 0 THEN
            close_reason := 'Trip cancelled';
        ELSE
            close_reason := 'Booking cancelled';
        END IF;
        UPDATE public.trip_sessions s
        SET status = CASE WHEN NEW.status = 'cancelled' THEN 'cancelled' ELSE 'closed' END,
            ended_at = COALESCE(s.ended_at, now())
        FROM public.booking_assignments a
        WHERE a.booking_id = NEW.id
          AND s.assignment_id = a.id
          AND s.status = 'active';
        PERFORM 1
        FROM public.booking_assignments
        WHERE booking_id = NEW.id
          AND status IN ('assigned', 'accepted')
        FOR UPDATE;
        IF NEW.status = 'cancelled' THEN
            UPDATE public.booking_assignments
            SET status = 'superseded',
                rejection_reason = close_reason,
                decided_at = now(),
                decided_by = public.app_uid()
            WHERE booking_id = NEW.id
              AND status IN ('assigned', 'accepted');
        ELSE
            UPDATE public.booking_assignments
            SET status = 'completed',
                rejection_reason = close_reason,
                decided_at = now(),
                decided_by = public.app_uid()
            WHERE booking_id = NEW.id
              AND status = 'accepted';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER bookings_write_event_and_close_trg
    AFTER INSERT OR UPDATE OF status ON bookings
    FOR EACH ROW EXECUTE FUNCTION bookings_write_event_and_close();

CREATE FUNCTION assignment_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    booking_branch uuid;
    booking_company uuid;
    booking_status text;
    vehicle_branch uuid;
BEGIN
    NEW.legacy_assignment_id := null_if_blank(NEW.legacy_assignment_id);
    NEW.rejection_reason := null_if_blank(NEW.rejection_reason);

    IF TG_OP = 'UPDATE' THEN
        IF NEW.booking_id IS DISTINCT FROM OLD.booking_id
           OR NEW.driver_id IS DISTINCT FROM OLD.driver_id
           OR NEW.assigned_by IS DISTINCT FROM OLD.assigned_by
           OR NEW.assigned_at IS DISTINCT FROM OLD.assigned_at
           OR NEW.legacy_assignment_id IS DISTINCT FROM OLD.legacy_assignment_id THEN
            RAISE EXCEPTION 'Assignment identity columns are immutable';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status
           AND NOT (
                (OLD.status = 'assigned' AND NEW.status IN ('accepted', 'rejected', 'withdrawn', 'superseded'))
                OR (OLD.status = 'accepted' AND NEW.status IN ('rejected', 'withdrawn', 'superseded'))
                OR (
                    OLD.status = 'accepted'
                    AND NEW.status = 'completed'
                    AND current_user = 'smt_definer'
                )
           ) THEN
            RAISE EXCEPTION 'Invalid assignment transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    IF TG_OP = 'INSERT' AND NEW.status <> 'assigned' THEN
        RAISE EXCEPTION 'A new assignment starts as assigned';
    END IF;

    SELECT b.branch_id, b.company_id, b.status
    INTO booking_branch, booking_company, booking_status
    FROM bookings b
    WHERE b.id = NEW.booking_id
    FOR UPDATE;

    -- assignment_guard is not security definer, so current_user is whoever
    -- issued the UPDATE. That is smt_definer only when bookings_write_event_and_close
    -- issues it, and that function returns before any write unless it is
    -- attached to public.bookings. Depth is not the proof.
    IF booking_status IN ('completed', 'cancelled')
       AND NOT (
            current_user = 'smt_definer'
            AND TG_OP = 'UPDATE'
            AND (
                (booking_status = 'completed'
                 AND OLD.status = 'accepted'
                 AND NEW.status = 'completed')
                OR (booking_status = 'cancelled'
                    AND OLD.status IN ('assigned', 'accepted')
                    AND NEW.status = 'superseded')
            )
       ) THEN
        RAISE EXCEPTION 'This booking is already finished';
    END IF;
    IF NEW.status IN ('rejected', 'withdrawn', 'superseded')
       AND booking_status IN ('started', 'completed') THEN
        RAISE EXCEPTION 'A started trip is cancelled from the booking, not by closing the attempt';
    END IF;

    PERFORM 1 FROM drivers WHERE id = NEW.driver_id FOR UPDATE;
    IF NOT EXISTS (
        SELECT 1 FROM driver_branches db
        WHERE db.driver_id = NEW.driver_id AND db.branch_id = booking_branch
    ) THEN
        RAISE EXCEPTION 'Driver is not enabled for this branch';
    END IF;
    IF booking_company IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM company_drivers cd
        WHERE cd.company_id = booking_company AND cd.driver_id = NEW.driver_id
    ) THEN
        RAISE EXCEPTION 'Driver is not authorised for this company';
    END IF;

    IF NEW.vehicle_id IS NOT NULL THEN
        SELECT branch_id INTO vehicle_branch
        FROM vehicles
        WHERE id = NEW.vehicle_id
        FOR UPDATE;
        IF vehicle_branch IS DISTINCT FROM booking_branch THEN
            RAISE EXCEPTION 'Vehicle is garaged at another branch';
        END IF;
        IF booking_company IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM company_vehicles cv
            WHERE cv.company_id = booking_company AND cv.vehicle_id = NEW.vehicle_id
        ) THEN
            RAISE EXCEPTION 'Vehicle is not authorised for this company';
        END IF;
    END IF;

    IF NEW.status IN ('rejected', 'withdrawn', 'superseded', 'completed') THEN
        IF NEW.decided_at IS NULL THEN
            NEW.decided_at := now();
        END IF;
        IF NEW.decided_by IS NULL THEN
            NEW.decided_by := app_uid();
        END IF;
        IF NEW.decided_by IS NULL THEN
            RAISE EXCEPTION 'This decision needs an actor';
        END IF;
        IF NEW.status = 'rejected' AND NEW.rejection_reason IS NULL THEN
            RAISE EXCEPTION 'Rejection needs a reason';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER assignment_guard_trg
    BEFORE INSERT OR UPDATE ON booking_assignments
    FOR EACH ROW EXECUTE FUNCTION assignment_guard();

CREATE FUNCTION assignment_after() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    open_count integer;
BEGIN
    IF TG_TABLE_SCHEMA IS DISTINCT FROM 'public'
       OR TG_TABLE_NAME IS DISTINCT FROM 'booking_assignments' THEN
        RAISE EXCEPTION 'assignment_after runs only on public.booking_assignments';
    END IF;
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.assignment_events (assignment_id, old_status, new_status, actor_user_id, reason)
        VALUES (
            NEW.id, NULL, NEW.status,
            COALESCE(NEW.decided_by, NEW.assigned_by, public.app_uid()),
            NEW.rejection_reason
        );
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO public.assignment_events (assignment_id, old_status, new_status, actor_user_id, reason)
        VALUES (
            NEW.id, OLD.status, NEW.status,
            COALESCE(NEW.decided_by, NEW.assigned_by, public.app_uid()),
            NEW.rejection_reason
        );
    END IF;

    -- There is no migration return. If this trigger runs, the booking
    -- update below still matches only assigned or accepted.
    IF NEW.status = 'assigned' THEN
        UPDATE public.bookings SET status = 'assigned'
        WHERE id = NEW.booking_id AND status = 'unassigned';
    ELSIF NEW.status = 'accepted' THEN
        UPDATE public.bookings SET status = 'accepted'
        WHERE id = NEW.booking_id AND status = 'assigned';
    ELSIF NEW.status IN ('rejected', 'withdrawn', 'superseded') THEN
        PERFORM 1 FROM public.trip_sessions
        WHERE assignment_id = NEW.id AND status = 'active'
        FOR UPDATE;
        UPDATE public.trip_sessions
        SET status = 'cancelled', ended_at = COALESCE(ended_at, now())
        WHERE assignment_id = NEW.id AND status = 'active';

        SELECT count(*) INTO open_count
        FROM public.booking_assignments
        WHERE booking_id = NEW.booking_id
          AND status IN ('assigned', 'accepted');
        IF open_count = 0 THEN
            UPDATE public.bookings SET status = 'unassigned'
            WHERE id = NEW.booking_id AND status IN ('assigned', 'accepted');
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER assignment_after_trg
    AFTER INSERT OR UPDATE OF status ON booking_assignments
    FOR EACH ROW EXECUTE FUNCTION assignment_after();

CREATE FUNCTION session_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    assignment_driver uuid;
    assignment_status text;
    booking_status text;
BEGIN
    IF NEW.session_origin = 'duty' THEN
        SELECT b.status
        INTO booking_status
        FROM bookings b
        JOIN booking_assignments a ON a.booking_id = b.id
        WHERE a.id = NEW.assignment_id
        FOR UPDATE OF b;
        SELECT a.driver_id, a.status
        INTO assignment_driver, assignment_status
        FROM booking_assignments a
        WHERE a.id = NEW.assignment_id
        FOR UPDATE;
        PERFORM 1 FROM drivers WHERE id = NEW.driver_id FOR UPDATE;
        IF NEW.driver_id IS DISTINCT FROM assignment_driver THEN
            RAISE EXCEPTION 'Session driver must be the assigned driver';
        END IF;
        IF NEW.status = 'active' THEN
            IF assignment_status <> 'accepted' OR booking_status NOT IN ('accepted', 'started') THEN
                RAISE EXCEPTION 'A trip starts only after the driver accepts';
            END IF;
            IF EXISTS (
                SELECT 1 FROM trip_sessions s
                WHERE s.driver_id = NEW.driver_id
                  AND s.status = 'active'
                  AND s.id IS DISTINCT FROM NEW.id
            ) THEN
                RAISE EXCEPTION 'This driver already has an active trip';
            END IF;
        END IF;
    END IF;
    IF NEW.status = 'active' AND NEW.session_origin <> 'duty' THEN
        RAISE EXCEPTION 'Only a duty session can be active';
    END IF;
    IF NEW.status IN ('closed', 'cancelled') AND NEW.ended_at IS NULL THEN
        NEW.ended_at := now();
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER session_guard_trg
    BEFORE INSERT OR UPDATE ON trip_sessions
    FOR EACH ROW EXECUTE FUNCTION session_guard();

CREATE FUNCTION session_after() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_TABLE_SCHEMA IS DISTINCT FROM 'public'
       OR TG_TABLE_NAME IS DISTINCT FROM 'trip_sessions' THEN
        RAISE EXCEPTION 'session_after runs only on public.trip_sessions';
    END IF;
    -- No role setting and no depth test. A nested call from the booking
    -- trigger matches zero rows once the booking is already terminal.
    IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM NEW.status THEN
        RETURN NEW;
    END IF;
    IF NEW.status = 'active' THEN
        UPDATE public.bookings b
        SET status = 'started'
        FROM public.booking_assignments a
        WHERE a.id = NEW.assignment_id
          AND b.id = a.booking_id
          AND b.status = 'accepted';
    ELSIF NEW.status = 'closed' THEN
        UPDATE public.bookings b
        SET status = 'completed'
        FROM public.booking_assignments a
        WHERE a.id = NEW.assignment_id
          AND b.id = a.booking_id
          AND b.status = 'started';
    ELSIF NEW.status = 'cancelled' THEN
        UPDATE public.bookings b
        SET status = 'cancelled'
        FROM public.booking_assignments a
        WHERE a.id = NEW.assignment_id
          AND b.id = a.booking_id
          AND b.status = 'started';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER session_after_trg
    AFTER INSERT OR UPDATE OF status ON trip_sessions
    FOR EACH ROW EXECUTE FUNCTION session_after();

CREATE FUNCTION gps_only_active() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    session_status text;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'GPS rows are append-only';
    END IF;
    SELECT status INTO session_status
    FROM trip_sessions
    WHERE id = NEW.trip_session_id
    FOR UPDATE;
    IF session_status IS DISTINCT FROM 'active' THEN
        RAISE EXCEPTION 'GPS is stored only while the trip session is active';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER gps_only_active_trg
    BEFORE INSERT OR UPDATE ON gps_positions
    FOR EACH ROW EXECUTE FUNCTION gps_only_active();

CREATE TRIGGER gps_no_delete
    BEFORE DELETE ON gps_positions
    FOR EACH ROW EXECUTE FUNCTION reject_history_change();

CREATE FUNCTION company_vehicle_same_branch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM vehicles v
        JOIN company_branches cb
          ON cb.branch_id = v.branch_id
         AND cb.company_id = NEW.company_id
        WHERE v.id = NEW.vehicle_id
    ) THEN
        RAISE EXCEPTION 'Company is not enabled at this vehicle branch';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER company_vehicle_same_branch_trg
    BEFORE INSERT OR UPDATE ON company_vehicles
    FOR EACH ROW EXECUTE FUNCTION company_vehicle_same_branch();

CREATE FUNCTION company_driver_same_branch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM driver_branches db
        JOIN company_branches cb
          ON cb.branch_id = db.branch_id
         AND cb.company_id = NEW.company_id
        WHERE db.driver_id = NEW.driver_id
    ) THEN
        RAISE EXCEPTION 'Company is not enabled at this driver branch';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER company_driver_same_branch_trg
    BEFORE INSERT OR UPDATE ON company_drivers
    FOR EACH ROW EXECUTE FUNCTION company_driver_same_branch();

CREATE FUNCTION lock_invoices(first_id uuid, second_id uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    low uuid;
    high uuid;
BEGIN
    IF first_id IS NULL AND second_id IS NULL THEN
        RETURN;
    END IF;
    IF second_id IS NULL OR first_id = second_id THEN
        PERFORM 1 FROM invoices WHERE id = first_id FOR UPDATE;
        RETURN;
    END IF;
    IF first_id IS NULL THEN
        PERFORM 1 FROM invoices WHERE id = second_id FOR UPDATE;
        RETURN;
    END IF;
    IF first_id < second_id THEN
        low := first_id;
        high := second_id;
    ELSE
        low := second_id;
        high := first_id;
    END IF;
    PERFORM 1 FROM invoices WHERE id = low FOR UPDATE;
    PERFORM 1 FROM invoices WHERE id = high FOR UPDATE;
END;
$$;

CREATE FUNCTION assert_invoice_covered(
    p_invoice uuid,
    p_line_delta numeric,
    p_payment_delta numeric
) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    line_total numeric(12, 2);
    paid numeric(12, 2);
    invoice_currency char(3);
BEGIN
    SELECT currency INTO invoice_currency FROM invoices WHERE id = p_invoice;
    IF invoice_currency IS DISTINCT FROM 'INR' THEN
        RAISE EXCEPTION 'Invoice currency must be INR';
    END IF;
    SELECT COALESCE(SUM(amount), 0) INTO line_total
    FROM invoice_lines WHERE invoice_id = p_invoice;
    SELECT COALESCE(SUM(amount), 0) INTO paid
    FROM payments WHERE invoice_id = p_invoice;
    IF paid + p_payment_delta > line_total + p_line_delta THEN
        RAISE EXCEPTION 'Payments would exceed the invoice lines';
    END IF;
END;
$$;

CREATE FUNCTION invoice_line_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    booking_company uuid;
    invoice_company uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM lock_invoices(OLD.invoice_id, NULL);
        PERFORM assert_invoice_covered(OLD.invoice_id, -OLD.amount, 0);
        RETURN OLD;
    END IF;
    PERFORM lock_invoices(NEW.invoice_id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.invoice_id ELSE NULL END);
    IF NEW.booking_id IS NOT NULL THEN
        SELECT company_id INTO invoice_company FROM invoices WHERE id = NEW.invoice_id;
        SELECT company_id INTO booking_company FROM bookings WHERE id = NEW.booking_id;
        IF booking_company IS NULL OR booking_company IS DISTINCT FROM invoice_company THEN
            RAISE EXCEPTION 'Invoice line company must match the booking company';
        END IF;
    END IF;
    IF TG_OP = 'INSERT' THEN
        PERFORM assert_invoice_covered(NEW.invoice_id, NEW.amount, 0);
    ELSIF OLD.invoice_id = NEW.invoice_id THEN
        PERFORM assert_invoice_covered(NEW.invoice_id, NEW.amount - OLD.amount, 0);
    ELSE
        PERFORM assert_invoice_covered(OLD.invoice_id, -OLD.amount, 0);
        PERFORM assert_invoice_covered(NEW.invoice_id, NEW.amount, 0);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER invoice_line_guard_trg
    BEFORE INSERT OR UPDATE OR DELETE ON invoice_lines
    FOR EACH ROW EXECUTE FUNCTION invoice_line_guard();

CREATE FUNCTION payment_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    invoice_currency char(3);
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM lock_invoices(OLD.invoice_id, NULL);
        PERFORM assert_invoice_covered(OLD.invoice_id, 0, -OLD.amount);
        RETURN OLD;
    END IF;
    IF NEW.currency IS DISTINCT FROM 'INR' THEN
        RAISE EXCEPTION 'Payment currency must be INR';
    END IF;
    PERFORM lock_invoices(NEW.invoice_id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.invoice_id ELSE NULL END);
    SELECT currency INTO invoice_currency FROM invoices WHERE id = NEW.invoice_id;
    IF invoice_currency IS DISTINCT FROM NEW.currency THEN
        RAISE EXCEPTION 'Payment currency must match the invoice';
    END IF;
    IF TG_OP = 'INSERT' THEN
        PERFORM assert_invoice_covered(NEW.invoice_id, 0, NEW.amount);
    ELSIF OLD.invoice_id = NEW.invoice_id THEN
        PERFORM assert_invoice_covered(NEW.invoice_id, 0, NEW.amount - OLD.amount);
    ELSE
        PERFORM assert_invoice_covered(OLD.invoice_id, 0, -OLD.amount);
        PERFORM assert_invoice_covered(NEW.invoice_id, 0, NEW.amount);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER payment_guard_trg
    BEFORE INSERT OR UPDATE OR DELETE ON payments
    FOR EACH ROW EXECUTE FUNCTION payment_guard();

CREATE FUNCTION user_link_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    linked_role text;
BEGIN
    IF TG_TABLE_NAME = 'user_branch_access' THEN
        SELECT role INTO linked_role FROM users WHERE id = NEW.user_id;
        IF linked_role NOT IN ('owner', 'staff') THEN
            RAISE EXCEPTION 'Only owner and staff have branch access';
        END IF;
    ELSIF TG_TABLE_NAME = 'user_company_links' THEN
        SELECT role INTO linked_role FROM users WHERE id = NEW.user_id;
        IF linked_role <> 'client' THEN
            RAISE EXCEPTION 'Only a client user links to a company';
        END IF;
    ELSIF TG_TABLE_NAME = 'drivers' THEN
        IF NEW.user_id IS NOT NULL THEN
            SELECT role INTO linked_role FROM users WHERE id = NEW.user_id;
            IF linked_role IS DISTINCT FROM 'driver' THEN
                RAISE EXCEPTION 'Driver login must be a driver user';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER user_branch_role_trg
    BEFORE INSERT OR UPDATE ON user_branch_access
    FOR EACH ROW EXECUTE FUNCTION user_link_guard();
CREATE TRIGGER user_company_role_trg
    BEFORE INSERT OR UPDATE ON user_company_links
    FOR EACH ROW EXECUTE FUNCTION user_link_guard();
CREATE TRIGGER driver_user_role_trg
    BEFORE INSERT OR UPDATE OF user_id ON drivers
    FOR EACH ROW EXECUTE FUNCTION user_link_guard();

CREATE FUNCTION protect_company_branch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE'
       OR NEW.company_id IS DISTINCT FROM OLD.company_id
       OR NEW.branch_id IS DISTINCT FROM OLD.branch_id THEN
        IF EXISTS (
            SELECT 1 FROM ets_contracts c
            WHERE c.company_id = OLD.company_id AND c.branch_id = OLD.branch_id
        ) OR EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.company_id = OLD.company_id AND b.branch_id = OLD.branch_id
        ) OR EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.company_id = OLD.company_id AND i.branch_id = OLD.branch_id
        ) OR EXISTS (
            SELECT 1
            FROM company_vehicles cv
            JOIN vehicles v ON v.id = cv.vehicle_id
            WHERE cv.company_id = OLD.company_id AND v.branch_id = OLD.branch_id
        ) OR EXISTS (
            SELECT 1
            FROM company_drivers cd
            JOIN driver_branches db ON db.driver_id = cd.driver_id
            WHERE cd.company_id = OLD.company_id AND db.branch_id = OLD.branch_id
        ) THEN
            RAISE EXCEPTION 'This company branch is still used by a contract, booking, invoice, vehicle, or driver';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER protect_company_branch_trg
    BEFORE UPDATE OR DELETE ON company_branches
    FOR EACH ROW EXECUTE FUNCTION protect_company_branch();

CREATE FUNCTION protect_company_driver() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM booking_assignments a
        JOIN bookings b ON b.id = a.booking_id
        WHERE a.driver_id = OLD.driver_id
          AND b.company_id = OLD.company_id
    ) THEN
        RAISE EXCEPTION 'This company driver is still used by an assignment';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER protect_company_driver_trg
    BEFORE DELETE ON company_drivers
    FOR EACH ROW EXECUTE FUNCTION protect_company_driver();

CREATE FUNCTION protect_company_vehicle() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM booking_assignments a
        JOIN bookings b ON b.id = a.booking_id
        WHERE a.vehicle_id = OLD.vehicle_id
          AND b.company_id = OLD.company_id
    ) THEN
        RAISE EXCEPTION 'This company vehicle is still used by an assignment';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER protect_company_vehicle_trg
    BEFORE DELETE ON company_vehicles
    FOR EACH ROW EXECUTE FUNCTION protect_company_vehicle();

CREATE FUNCTION protect_driver_branch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM booking_assignments a
        JOIN bookings b ON b.id = a.booking_id
        WHERE a.driver_id = OLD.driver_id
          AND b.branch_id = OLD.branch_id
    ) THEN
        RAISE EXCEPTION 'This driver branch is still used by an assignment';
    END IF;
    IF EXISTS (
        SELECT 1 FROM company_drivers cd
        WHERE cd.driver_id = OLD.driver_id
          AND NOT EXISTS (
                SELECT 1
                FROM driver_branches db
                JOIN company_branches cb
                  ON cb.branch_id = db.branch_id
                 AND cb.company_id = cd.company_id
                WHERE db.driver_id = OLD.driver_id
                  AND db.branch_id IS DISTINCT FROM OLD.branch_id
          )
    ) THEN
        RAISE EXCEPTION 'Removing this driver branch would leave a company driver without a shared branch';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER protect_driver_branch_trg
    BEFORE DELETE ON driver_branches
    FOR EACH ROW EXECUTE FUNCTION protect_driver_branch();

CREATE FUNCTION protect_vehicle_branch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.branch_id IS NOT DISTINCT FROM OLD.branch_id THEN
        RETURN NEW;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM company_vehicles cv
        WHERE cv.vehicle_id = OLD.id
          AND NOT EXISTS (
                SELECT 1 FROM company_branches cb
                WHERE cb.company_id = cv.company_id
                  AND cb.branch_id = NEW.branch_id
          )
    ) THEN
        RAISE EXCEPTION 'This vehicle branch change would invalidate a company allocation';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM booking_assignments a
        JOIN bookings b ON b.id = a.booking_id
        WHERE a.vehicle_id = OLD.id
          AND b.branch_id IS DISTINCT FROM NEW.branch_id
    ) THEN
        RAISE EXCEPTION 'This vehicle branch change would invalidate an assignment';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER protect_vehicle_branch_trg
    BEFORE UPDATE OF branch_id ON vehicles
    FOR EACH ROW EXECUTE FUNCTION protect_vehicle_branch();

CREATE FUNCTION message_links_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    booking_company uuid;
    booking_branch uuid;
    assignment_booking uuid;
    session_company uuid;
    session_branch uuid;
BEGIN
    IF NEW.booking_id IS NOT NULL THEN
        SELECT company_id, branch_id
        INTO booking_company, booking_branch
        FROM bookings
        WHERE id = NEW.booking_id;
        -- A supplied company or branch must equal the booking. NULL equals
        -- only NULL. A missing message value is filled from the booking.
        IF NEW.company_id IS DISTINCT FROM booking_company
           AND NEW.company_id IS NOT NULL THEN
            RAISE EXCEPTION 'Message company does not match the booking';
        END IF;
        IF NEW.branch_id IS DISTINCT FROM booking_branch
           AND NEW.branch_id IS NOT NULL THEN
            RAISE EXCEPTION 'Message branch does not match the booking';
        END IF;
        NEW.company_id := booking_company;
        NEW.branch_id := booking_branch;
    END IF;
    IF NEW.assignment_id IS NOT NULL THEN
        SELECT booking_id INTO assignment_booking
        FROM booking_assignments
        WHERE id = NEW.assignment_id;
        IF NEW.booking_id IS NULL OR assignment_booking IS DISTINCT FROM NEW.booking_id THEN
            RAISE EXCEPTION 'Message assignment does not belong to the booking';
        END IF;
    END IF;
    IF NEW.chat_session_id IS NOT NULL THEN
        SELECT company_id, branch_id
        INTO session_company, session_branch
        FROM chat_sessions
        WHERE id = NEW.chat_session_id;
        IF NEW.booking_id IS NOT NULL THEN
            -- Compare with IS DISTINCT FROM so NULL does not match a company.
            -- Never copy the session company onto a booking message.
            IF booking_company IS DISTINCT FROM session_company THEN
                RAISE EXCEPTION 'Chat session company does not match the booking';
            END IF;
            IF booking_branch IS DISTINCT FROM session_branch THEN
                RAISE EXCEPTION 'Chat session branch does not match the booking';
            END IF;
        ELSE
            IF NEW.company_id IS NOT NULL
               AND session_company IS NOT NULL
               AND NEW.company_id IS DISTINCT FROM session_company THEN
                RAISE EXCEPTION 'Message company does not match the chat session';
            END IF;
            IF NEW.branch_id IS NOT NULL
               AND session_branch IS NOT NULL
               AND NEW.branch_id IS DISTINCT FROM session_branch THEN
                RAISE EXCEPTION 'Message branch does not match the chat session';
            END IF;
            -- No booking. Fill only a missing value. Do not replace an
            -- explicit company or branch with NULL.
            IF NEW.company_id IS NULL THEN
                NEW.company_id := session_company;
            END IF;
            IF NEW.branch_id IS NULL THEN
                NEW.branch_id := session_branch;
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER message_links_guard_trg
    BEFORE INSERT OR UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION message_links_guard();

CREATE FUNCTION booking_place_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    assignment_row record;
BEGIN
    IF TG_OP = 'UPDATE'
       AND (NEW.branch_id IS DISTINCT FROM OLD.branch_id
            OR NEW.company_id IS DISTINCT FROM OLD.company_id
            OR NEW.contract_id IS DISTINCT FROM OLD.contract_id) THEN
        FOR assignment_row IN
            SELECT driver_id, vehicle_id
            FROM booking_assignments
            WHERE booking_id = NEW.id
        LOOP
            IF NOT EXISTS (
                SELECT 1 FROM driver_branches db
                WHERE db.driver_id = assignment_row.driver_id
                  AND db.branch_id = NEW.branch_id
            ) THEN
                RAISE EXCEPTION 'Moving this booking would leave a driver outside the branch';
            END IF;
            IF NEW.company_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM company_drivers cd
                WHERE cd.company_id = NEW.company_id
                  AND cd.driver_id = assignment_row.driver_id
            ) THEN
                RAISE EXCEPTION 'Moving this booking would leave a driver outside the company';
            END IF;
            IF assignment_row.vehicle_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM vehicles v
                    WHERE v.id = assignment_row.vehicle_id
                      AND v.branch_id = NEW.branch_id
                ) THEN
                    RAISE EXCEPTION 'Moving this booking would leave a vehicle outside the branch';
                END IF;
                IF NEW.company_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM company_vehicles cv
                    WHERE cv.company_id = NEW.company_id
                      AND cv.vehicle_id = assignment_row.vehicle_id
                ) THEN
                    RAISE EXCEPTION 'Moving this booking would leave a vehicle outside the company';
                END IF;
            END IF;
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER booking_place_guard_trg
    BEFORE UPDATE OF branch_id, company_id, contract_id ON bookings
    FOR EACH ROW EXECUTE FUNCTION booking_place_guard();

CREATE FUNCTION assert_booking_consistent() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target uuid;
    booking_status text;
    open_assigned integer;
    open_accepted integer;
    active_sessions integer;
BEGIN
    IF TG_TABLE_NAME = 'bookings' THEN
        IF TG_OP = 'DELETE' THEN
            target := OLD.id;
        ELSE
            target := NEW.id;
        END IF;
    ELSIF TG_TABLE_NAME = 'trip_sessions' THEN
        SELECT a.booking_id INTO target
        FROM booking_assignments a
        WHERE a.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.assignment_id ELSE NEW.assignment_id END;
    ELSIF TG_OP = 'DELETE' THEN
        target := OLD.booking_id;
    ELSE
        target := NEW.booking_id;
    END IF;
    IF target IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT status INTO booking_status FROM bookings WHERE id = target;
    SELECT count(*) FILTER (WHERE status = 'assigned'),
           count(*) FILTER (WHERE status = 'accepted')
    INTO open_assigned, open_accepted
    FROM booking_assignments
    WHERE booking_id = target;
    SELECT count(*) INTO active_sessions
    FROM trip_sessions s
    JOIN booking_assignments a ON a.id = s.assignment_id
    WHERE a.booking_id = target
      AND s.status = 'active';
    IF booking_status = 'unassigned'
       AND (open_assigned + open_accepted + active_sessions) > 0 THEN
        RAISE EXCEPTION 'An unassigned booking cannot have an open attempt or an active session';
    ELSIF booking_status = 'assigned'
          AND (open_assigned <> 1 OR open_accepted <> 0 OR active_sessions <> 0) THEN
        RAISE EXCEPTION 'An assigned booking must have one assigned attempt and no active session';
    ELSIF booking_status = 'accepted'
          AND (open_assigned <> 0 OR open_accepted <> 1 OR active_sessions <> 0) THEN
        RAISE EXCEPTION 'An accepted booking must have one accepted attempt and no active session';
    ELSIF booking_status = 'started'
          AND (open_assigned <> 0 OR open_accepted <> 1 OR active_sessions <> 1) THEN
        RAISE EXCEPTION 'A started booking must have one accepted attempt and one active session';
    ELSIF booking_status = 'completed'
          AND (open_assigned <> 0 OR open_accepted <> 0 OR active_sessions <> 0
               OR (
                    SELECT count(*) FROM booking_assignments
                    WHERE booking_id = target AND status = 'completed'
               ) <> 1
               OR EXISTS (
                    SELECT 1
                    FROM trip_sessions s
                    JOIN booking_assignments a ON a.id = s.assignment_id
                    WHERE a.booking_id = target
                      AND s.session_origin = 'duty'
                      AND s.status IS DISTINCT FROM 'closed'
               )) THEN
        RAISE EXCEPTION 'A completed booking must have one completed attempt and every duty session closed';
    ELSIF booking_status = 'cancelled'
          AND (open_assigned <> 0 OR open_accepted <> 0 OR active_sessions <> 0
               OR EXISTS (
                    SELECT 1
                    FROM trip_sessions s
                    JOIN booking_assignments a ON a.id = s.assignment_id
                    WHERE a.booking_id = target
                      AND s.session_origin = 'duty'
                      AND s.status = 'closed'
               )) THEN
        RAISE EXCEPTION 'A cancelled booking cannot have an open attempt, an active session, or a closed duty session';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER booking_consistency_from_assignment
    AFTER INSERT OR UPDATE OR DELETE ON booking_assignments
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_booking_consistent();

CREATE CONSTRAINT TRIGGER booking_consistency_from_session
    AFTER INSERT OR UPDATE OR DELETE ON trip_sessions
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_booking_consistent();

CREATE CONSTRAINT TRIGGER booking_consistency_from_booking
    AFTER UPDATE OF status ON bookings
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_booking_consistent();

CREATE ROLE smt_definer NOLOGIN NOSUPERUSER NOREPLICATION NOCREATEDB NOCREATEROLE BYPASSRLS;
CREATE ROLE smt_migrate NOLOGIN NOSUPERUSER NOREPLICATION NOCREATEDB NOCREATEROLE BYPASSRLS;
CREATE ROLE smt_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE smt_staff NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE smt_driver NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE smt_client NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE smt_app LOGIN NOSUPERUSER NOREPLICATION NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;

GRANT smt_owner, smt_staff, smt_driver, smt_client TO smt_app;
REVOKE smt_migrate FROM smt_app;
REVOKE smt_definer FROM smt_app;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO smt_app, smt_owner, smt_staff, smt_driver, smt_client, smt_definer, smt_migrate;

CREATE FUNCTION app_is_owner() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off AS $$
    SELECT EXISTS (
        SELECT 1 FROM users u
        WHERE u.id = app_uid() AND u.role = 'owner' AND u.status = 'active'
    )
$$;

CREATE FUNCTION staff_can_branch(target uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off AS $$
    SELECT EXISTS (
        SELECT 1 FROM users u
        WHERE u.id = app_uid() AND u.role = 'owner' AND u.status = 'active'
    )
    OR EXISTS (
        SELECT 1
        FROM user_branch_access a
        JOIN users u ON u.id = a.user_id
        WHERE a.user_id = app_uid()
          AND u.role = 'staff'
          AND u.status = 'active'
          AND a.branch_id = target
    )
$$;

CREATE FUNCTION client_can_company(target uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off AS $$
    SELECT EXISTS (
        SELECT 1
        FROM user_company_links l
        JOIN users u ON u.id = l.user_id
        WHERE l.user_id = app_uid()
          AND u.role = 'client'
          AND u.status = 'active'
          AND l.company_id = target
    )
$$;

CREATE FUNCTION current_driver_id() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off AS $$
    SELECT d.id
    FROM drivers d
    JOIN users u ON u.id = d.user_id
    WHERE d.user_id = app_uid() AND u.role = 'driver' AND u.status = 'active'
$$;

CREATE FUNCTION app_begin(p_user uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
SET row_security = off AS $$
    SELECT u.role
    FROM users u
    WHERE u.id = p_user AND u.status = 'active'
$$;

REVOKE ALL ON FUNCTION app_uid() FROM PUBLIC;
REVOKE ALL ON FUNCTION app_is_owner() FROM PUBLIC;
REVOKE ALL ON FUNCTION staff_can_branch(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION client_can_company(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION current_driver_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION app_begin(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_uid() TO smt_owner, smt_staff, smt_driver, smt_client, smt_definer;
GRANT EXECUTE ON FUNCTION app_is_owner() TO smt_owner, smt_staff, smt_driver, smt_client;
GRANT EXECUTE ON FUNCTION staff_can_branch(uuid) TO smt_owner, smt_staff, smt_driver, smt_client;
GRANT EXECUTE ON FUNCTION client_can_company(uuid) TO smt_owner, smt_staff, smt_driver, smt_client;
GRANT EXECUTE ON FUNCTION current_driver_id() TO smt_owner, smt_staff, smt_driver, smt_client;
GRANT EXECUTE ON FUNCTION app_begin(uuid) TO smt_app;

ALTER FUNCTION app_is_owner() OWNER TO smt_definer;
ALTER FUNCTION staff_can_branch(uuid) OWNER TO smt_definer;
ALTER FUNCTION client_can_company(uuid) OWNER TO smt_definer;
ALTER FUNCTION current_driver_id() OWNER TO smt_definer;
ALTER FUNCTION app_begin(uuid) OWNER TO smt_definer;
ALTER FUNCTION bookings_write_event_and_close() OWNER TO smt_definer;
ALTER FUNCTION assignment_after() OWNER TO smt_definer;
ALTER FUNCTION session_after() OWNER TO smt_definer;

REVOKE ALL ON FUNCTION bookings_write_event_and_close() FROM PUBLIC;
REVOKE ALL ON FUNCTION assignment_after() FROM PUBLIC;
REVOKE ALL ON FUNCTION session_after() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION bookings_write_event_and_close() TO smt_owner, smt_staff, smt_definer;
GRANT EXECUTE ON FUNCTION session_after() TO smt_owner, smt_staff, smt_driver, smt_definer;
GRANT EXECUTE ON FUNCTION assignment_after() TO smt_owner, smt_staff, smt_driver, smt_definer;

-- This table is created before the row-security statements below.
-- In the plan, those ALTER TABLE statements appear before this CREATE TABLE.
CREATE TABLE reconciliation_decisions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_name text NOT NULL,
    legacy_source text,
    legacy_id text,
    decision text NOT NULL CHECK (decision IN (
        'keep_conflict', 'mark_clean', 'merge', 'hold', 'branch_exception'
    )),
    decided_by text NOT NULL,
    note text,
    decided_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE user_branch_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_branch_access FORCE ROW LEVEL SECURITY;
ALTER TABLE user_company_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_company_links FORCE ROW LEVEL SECURITY;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies FORCE ROW LEVEL SECURITY;
ALTER TABLE company_branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_branches FORCE ROW LEVEL SECURITY;
ALTER TABLE company_vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_vehicles FORCE ROW LEVEL SECURITY;
ALTER TABLE company_drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_drivers FORCE ROW LEVEL SECURITY;
ALTER TABLE drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE drivers FORCE ROW LEVEL SECURITY;
ALTER TABLE driver_branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_branches FORCE ROW LEVEL SECURITY;
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles FORCE ROW LEVEL SECURITY;
ALTER TABLE vehicle_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicle_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE enquiries ENABLE ROW LEVEL SECURITY;
ALTER TABLE enquiries FORCE ROW LEVEL SECURITY;
ALTER TABLE ets_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ets_contracts FORCE ROW LEVEL SECURITY;
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_batches FORCE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings FORCE ROW LEVEL SECURITY;
ALTER TABLE booking_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking_assignments FORCE ROW LEVEL SECURITY;
ALTER TABLE assignment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignment_events FORCE ROW LEVEL SECURITY;
ALTER TABLE trip_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trip_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE gps_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE gps_positions FORCE ROW LEVEL SECURITY;
ALTER TABLE trip_passengers ENABLE ROW LEVEL SECURITY;
ALTER TABLE trip_passengers FORCE ROW LEVEL SECURITY;
ALTER TABLE safety_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety_alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE booking_charges ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking_charges FORCE ROW LEVEL SECURITY;
ALTER TABLE duty_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE duty_readings FORCE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
ALTER TABLE invoice_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;
ALTER TABLE driver_payouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_payouts FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE booking_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking_events FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_decisions FORCE ROW LEVEL SECURITY;

CREATE POLICY users_owner_read ON users FOR SELECT TO smt_owner
    USING (app_is_owner());
CREATE POLICY users_self_read ON users FOR SELECT TO smt_staff, smt_driver, smt_client
    USING (id = app_uid());
CREATE POLICY users_owner_write ON users FOR INSERT TO smt_owner
    WITH CHECK (app_is_owner());
CREATE POLICY users_owner_update ON users FOR UPDATE TO smt_owner
    USING (app_is_owner()) WITH CHECK (app_is_owner());

CREATE POLICY branch_access_read ON user_branch_access FOR SELECT TO smt_owner, smt_staff
    USING (user_id = app_uid() OR app_is_owner() OR staff_can_branch(branch_id));
CREATE POLICY branch_access_write ON user_branch_access FOR INSERT TO smt_owner
    WITH CHECK (app_is_owner());
CREATE POLICY branch_access_delete ON user_branch_access FOR DELETE TO smt_owner
    USING (app_is_owner());

CREATE POLICY company_link_read ON user_company_links FOR SELECT TO smt_owner, smt_client
    USING (user_id = app_uid() OR app_is_owner() OR client_can_company(company_id));
CREATE POLICY company_link_write ON user_company_links FOR INSERT TO smt_owner
    WITH CHECK (app_is_owner());
CREATE POLICY company_link_delete ON user_company_links FOR DELETE TO smt_owner
    USING (app_is_owner());

CREATE POLICY companies_read ON companies FOR SELECT TO smt_owner, smt_staff, smt_client
    USING (
        app_is_owner()
        OR client_can_company(id)
        OR EXISTS (
            SELECT 1 FROM company_branches cb
            WHERE cb.company_id = companies.id AND staff_can_branch(cb.branch_id)
        )
    );
CREATE POLICY companies_write ON companies FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        app_is_owner()
        OR staff_can_branch(NULLIF(current_setting('app.home_branch', true), '')::uuid)
    );
CREATE POLICY companies_update ON companies FOR UPDATE TO smt_owner, smt_staff
    USING (
        app_is_owner()
        OR EXISTS (
            SELECT 1 FROM company_branches cb
            WHERE cb.company_id = companies.id AND staff_can_branch(cb.branch_id)
        )
    )
    WITH CHECK (
        app_is_owner()
        OR EXISTS (
            SELECT 1 FROM company_branches cb
            WHERE cb.company_id = companies.id AND staff_can_branch(cb.branch_id)
        )
    );

CREATE POLICY company_branches_read ON company_branches FOR SELECT TO smt_owner, smt_staff, smt_client
    USING (staff_can_branch(branch_id) OR client_can_company(company_id));
CREATE POLICY company_branches_write ON company_branches FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (staff_can_branch(branch_id));
CREATE POLICY company_branches_delete ON company_branches FOR DELETE TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id));

CREATE POLICY company_vehicles_read ON company_vehicles FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM vehicles v
            WHERE v.id = company_vehicles.vehicle_id AND staff_can_branch(v.branch_id)
        )
    );
CREATE POLICY company_vehicles_write ON company_vehicles FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM vehicles v
            WHERE v.id = vehicle_id AND staff_can_branch(v.branch_id)
        )
    );
CREATE POLICY company_vehicles_delete ON company_vehicles FOR DELETE TO smt_owner
    USING (app_is_owner());

CREATE POLICY company_drivers_read ON company_drivers FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = company_drivers.driver_id AND staff_can_branch(db.branch_id)
        )
    );
CREATE POLICY company_drivers_write ON company_drivers FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = driver_id AND staff_can_branch(db.branch_id)
        )
    );
CREATE POLICY company_drivers_delete ON company_drivers FOR DELETE TO smt_owner
    USING (app_is_owner());

CREATE POLICY drivers_staff_read ON drivers FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = drivers.id AND staff_can_branch(db.branch_id)
        )
    );
CREATE POLICY drivers_self_read ON drivers FOR SELECT TO smt_driver
    USING (id = current_driver_id());
CREATE POLICY drivers_staff_write ON drivers FOR ALL TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM driver_branches db
            WHERE db.driver_id = drivers.id AND staff_can_branch(db.branch_id)
        )
    )
    WITH CHECK (staff_can_branch(primary_branch_id));
CREATE POLICY drivers_self_update ON drivers FOR UPDATE TO smt_driver
    USING (id = current_driver_id())
    WITH CHECK (id = current_driver_id() AND user_id = app_uid());

CREATE POLICY driver_branches_read ON driver_branches FOR SELECT TO smt_owner, smt_staff, smt_driver
    USING (staff_can_branch(branch_id) OR driver_id = current_driver_id());
CREATE POLICY driver_branches_write ON driver_branches FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (staff_can_branch(branch_id));
CREATE POLICY driver_branches_delete ON driver_branches FOR DELETE TO smt_owner
    USING (app_is_owner());

CREATE POLICY vehicles_staff ON vehicles FOR ALL TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id))
    WITH CHECK (staff_can_branch(branch_id));
CREATE POLICY vehicles_driver_read ON vehicles FOR SELECT TO smt_driver
    USING (
        usual_driver_id = current_driver_id()
        OR id IN (
            SELECT a.vehicle_id FROM booking_assignments a
            WHERE a.driver_id = current_driver_id() AND a.vehicle_id IS NOT NULL
        )
    );

CREATE POLICY vehicle_documents_staff ON vehicle_documents FOR ALL TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM vehicles v
            WHERE v.id = vehicle_documents.vehicle_id AND staff_can_branch(v.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM vehicles v
            WHERE v.id = vehicle_id AND staff_can_branch(v.branch_id)
        )
    );

CREATE POLICY enquiries_read ON enquiries FOR SELECT TO smt_owner, smt_staff, smt_client
    USING (
        (branch_id IS NOT NULL AND staff_can_branch(branch_id))
        OR (company_id IS NOT NULL AND client_can_company(company_id))
    );
CREATE POLICY enquiries_write ON enquiries FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (branch_id IS NOT NULL AND staff_can_branch(branch_id));
CREATE POLICY enquiries_update ON enquiries FOR UPDATE TO smt_owner, smt_staff
    USING (branch_id IS NOT NULL AND staff_can_branch(branch_id))
    WITH CHECK (branch_id IS NOT NULL AND staff_can_branch(branch_id));

CREATE POLICY contracts_read ON ets_contracts FOR SELECT TO smt_owner, smt_staff, smt_client
    USING (staff_can_branch(branch_id) OR client_can_company(company_id));
CREATE POLICY contracts_write ON ets_contracts FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (staff_can_branch(branch_id));
CREATE POLICY contracts_update ON ets_contracts FOR UPDATE TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id))
    WITH CHECK (staff_can_branch(branch_id));

CREATE POLICY batches_read ON import_batches FOR SELECT TO smt_owner, smt_staff
    USING (
        app_is_owner()
        OR EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.import_batch_id = import_batches.id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY batches_write ON import_batches FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        app_is_owner()
        OR staff_can_branch(NULLIF(current_setting('app.home_branch', true), '')::uuid)
    );

CREATE POLICY bookings_staff_read ON bookings FOR SELECT TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id));
CREATE POLICY bookings_driver_read ON bookings FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.booking_id = bookings.id AND a.driver_id = current_driver_id()
        )
    );
CREATE POLICY bookings_client_read ON bookings FOR SELECT TO smt_client
    USING (company_id IS NOT NULL AND client_can_company(company_id));
CREATE POLICY bookings_staff_insert ON bookings FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (staff_can_branch(branch_id));
CREATE POLICY bookings_staff_update ON bookings FOR UPDATE TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id))
    WITH CHECK (staff_can_branch(branch_id));

CREATE POLICY assignments_staff_read ON booking_assignments FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_assignments.booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY assignments_driver_read ON booking_assignments FOR SELECT TO smt_driver
    USING (driver_id = current_driver_id());
CREATE POLICY assignments_staff_insert ON booking_assignments FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY assignments_staff_update ON booking_assignments FOR UPDATE TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_assignments.booking_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY assignments_driver_update ON booking_assignments FOR UPDATE TO smt_driver
    USING (driver_id = current_driver_id() AND status = 'assigned')
    WITH CHECK (driver_id = current_driver_id() AND status IN ('accepted', 'rejected'));

CREATE POLICY assignment_events_staff ON assignment_events FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            WHERE a.id = assignment_events.assignment_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY assignment_events_driver ON assignment_events FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.id = assignment_events.assignment_id AND a.driver_id = current_driver_id()
        )
    );

CREATE VIEW client_duty_status
WITH (security_invoker = false) AS
SELECT
    b.id AS booking_id,
    b.company_id,
    b.trip_date,
    b.pickup_time,
    b.cab_type,
    b.planned_start,
    b.route_text,
    b.employee_name,
    b.status AS duty_status,
    CASE
        WHEN a.status IN ('assigned', 'accepted', 'completed') THEN a.status
        ELSE NULL
    END AS assignment_status,
    CASE
        WHEN a.status IN ('assigned', 'accepted', 'completed') THEN d.display_name
        ELSE NULL
    END AS driver_name,
    CASE
        WHEN a.status IN ('assigned', 'accepted', 'completed') THEN d.phone
        ELSE NULL
    END AS driver_phone,
    CASE
        WHEN a.status IN ('assigned', 'accepted', 'completed') THEN v.registration_number
        ELSE NULL
    END AS vehicle_registration,
    CASE
        WHEN a.status IN ('assigned', 'accepted', 'completed') THEN v.model
        ELSE NULL
    END AS vehicle_model
FROM bookings b
LEFT JOIN booking_assignments a
    ON a.booking_id = b.id
   AND a.status IN ('assigned', 'accepted', 'completed')
LEFT JOIN drivers d ON d.id = a.driver_id
LEFT JOIN vehicles v ON v.id = a.vehicle_id
WHERE b.company_id IS NOT NULL
  AND client_can_company(b.company_id);

ALTER VIEW client_duty_status OWNER TO smt_definer;
ALTER VIEW client_duty_status SET (security_barrier = true);

CREATE POLICY sessions_staff ON trip_sessions FOR SELECT TO smt_owner, smt_staff
    USING (
        session_origin = 'website_demo' AND app_is_owner()
        OR EXISTS (
            SELECT 1
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            WHERE a.id = trip_sessions.assignment_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY sessions_driver_read ON trip_sessions FOR SELECT TO smt_driver
    USING (driver_id = current_driver_id());
CREATE POLICY sessions_driver_insert ON trip_sessions FOR INSERT TO smt_driver
    WITH CHECK (driver_id = current_driver_id() AND status = 'active' AND session_origin = 'duty');
CREATE POLICY sessions_driver_update ON trip_sessions FOR UPDATE TO smt_driver
    USING (driver_id = current_driver_id() AND status = 'active')
    WITH CHECK (driver_id = current_driver_id() AND status IN ('closed', 'cancelled'));
CREATE POLICY sessions_staff_write ON trip_sessions FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            WHERE a.id = assignment_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY sessions_staff_update ON trip_sessions FOR UPDATE TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            WHERE a.id = trip_sessions.assignment_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM booking_assignments a
            JOIN bookings b ON b.id = a.booking_id
            WHERE a.id = assignment_id AND staff_can_branch(b.branch_id)
        )
    );

CREATE POLICY gps_staff_read ON gps_positions FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1
            FROM trip_sessions s
            JOIN booking_assignments a ON a.id = s.assignment_id
            JOIN bookings b ON b.id = a.booking_id
            WHERE s.id = gps_positions.trip_session_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY gps_driver_read ON gps_positions FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM trip_sessions s
            WHERE s.id = gps_positions.trip_session_id AND s.driver_id = current_driver_id()
        )
    );
CREATE POLICY gps_driver_insert ON gps_positions FOR INSERT TO smt_driver
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM trip_sessions s
            WHERE s.id = trip_session_id
              AND s.status = 'active'
              AND s.driver_id = current_driver_id()
        )
    );

CREATE POLICY passengers_staff ON trip_passengers FOR ALL TO smt_owner, smt_staff
    USING (
        trip_session_id IS NULL AND app_is_owner()
        OR EXISTS (
            SELECT 1
            FROM trip_sessions s
            JOIN booking_assignments a ON a.id = s.assignment_id
            JOIN bookings b ON b.id = a.booking_id
            WHERE s.id = trip_passengers.trip_session_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM trip_sessions s
            JOIN booking_assignments a ON a.id = s.assignment_id
            JOIN bookings b ON b.id = a.booking_id
            WHERE s.id = trip_session_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY passengers_driver ON trip_passengers FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM trip_sessions s
            WHERE s.id = trip_passengers.trip_session_id AND s.driver_id = current_driver_id()
        )
    );
CREATE POLICY passengers_client ON trip_passengers FOR SELECT TO smt_client
    USING (
        EXISTS (
            SELECT 1
            FROM trip_sessions s
            JOIN booking_assignments a ON a.id = s.assignment_id
            JOIN bookings b ON b.id = a.booking_id
            WHERE s.id = trip_passengers.trip_session_id AND client_can_company(b.company_id)
        )
    );

CREATE POLICY alerts_staff ON safety_alerts FOR ALL TO smt_owner, smt_staff
    USING (
        trip_session_id IS NULL AND app_is_owner()
        OR EXISTS (
            SELECT 1
            FROM trip_sessions s
            JOIN booking_assignments a ON a.id = s.assignment_id
            JOIN bookings b ON b.id = a.booking_id
            WHERE s.id = safety_alerts.trip_session_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM trip_sessions s
            JOIN booking_assignments a ON a.id = s.assignment_id
            JOIN bookings b ON b.id = a.booking_id
            WHERE s.id = trip_session_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY alerts_driver ON safety_alerts FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM trip_sessions s
            WHERE s.id = safety_alerts.trip_session_id AND s.driver_id = current_driver_id()
        )
    );

CREATE POLICY charges_staff ON booking_charges FOR ALL TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_charges.booking_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY charges_client ON booking_charges FOR SELECT TO smt_client
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_charges.booking_id AND client_can_company(b.company_id)
        )
    );

CREATE POLICY readings_staff ON duty_readings FOR ALL TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = duty_readings.booking_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY readings_driver ON duty_readings FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.booking_id = duty_readings.booking_id AND a.driver_id = current_driver_id()
        )
    );
CREATE POLICY readings_driver_update ON duty_readings FOR UPDATE TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.booking_id = duty_readings.booking_id
              AND a.driver_id = current_driver_id()
              AND a.status = 'accepted'
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.booking_id = booking_id
              AND a.driver_id = current_driver_id()
              AND a.status = 'accepted'
        )
    );

CREATE POLICY invoices_staff ON invoices FOR SELECT TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id));
CREATE POLICY invoices_client ON invoices FOR SELECT TO smt_client
    USING (client_can_company(company_id));
CREATE POLICY invoices_staff_insert ON invoices FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (staff_can_branch(branch_id));
CREATE POLICY invoices_staff_update ON invoices FOR UPDATE TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id))
    WITH CHECK (staff_can_branch(branch_id));

CREATE POLICY lines_staff_read ON invoice_lines FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_lines.invoice_id AND staff_can_branch(i.branch_id)
        )
    );
CREATE POLICY lines_client_read ON invoice_lines FOR SELECT TO smt_client
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_lines.invoice_id AND client_can_company(i.company_id)
        )
    );
CREATE POLICY lines_staff_write ON invoice_lines FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_id AND staff_can_branch(i.branch_id)
        )
    );
CREATE POLICY lines_staff_update ON invoice_lines FOR UPDATE TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_lines.invoice_id AND staff_can_branch(i.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_id AND staff_can_branch(i.branch_id)
        )
    );
CREATE POLICY lines_staff_delete ON invoice_lines FOR DELETE TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_lines.invoice_id AND staff_can_branch(i.branch_id)
        )
    );

CREATE POLICY payments_staff_read ON payments FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = payments.invoice_id AND staff_can_branch(i.branch_id)
        )
    );
CREATE POLICY payments_client_read ON payments FOR SELECT TO smt_client
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = payments.invoice_id AND client_can_company(i.company_id)
        )
    );
CREATE POLICY payments_staff_insert ON payments FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_id AND staff_can_branch(i.branch_id)
        )
    );
CREATE POLICY payments_staff_update ON payments FOR UPDATE TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = payments.invoice_id AND staff_can_branch(i.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = invoice_id AND staff_can_branch(i.branch_id)
        )
    );
CREATE POLICY payments_staff_delete ON payments FOR DELETE TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM invoices i
            WHERE i.id = payments.invoice_id AND staff_can_branch(i.branch_id)
        )
    );

CREATE POLICY payouts_staff ON driver_payouts FOR ALL TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = driver_payouts.booking_id AND staff_can_branch(b.branch_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY payouts_driver ON driver_payouts FOR SELECT TO smt_driver
    USING (driver_id = current_driver_id());

CREATE POLICY chats_read ON chat_sessions FOR SELECT TO smt_owner, smt_staff, smt_client
    USING (
        (branch_id IS NOT NULL AND staff_can_branch(branch_id))
        OR (company_id IS NOT NULL AND client_can_company(company_id))
        OR (branch_id IS NULL AND company_id IS NULL AND app_is_owner())
    );
CREATE POLICY chats_write ON chat_sessions FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (branch_id IS NULL OR staff_can_branch(branch_id));

CREATE POLICY messages_staff_read ON messages FOR SELECT TO smt_owner, smt_staff
    USING (branch_id IS NOT NULL AND staff_can_branch(branch_id));
CREATE POLICY messages_driver_read ON messages FOR SELECT TO smt_driver
    USING (
        assignment_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.id = messages.assignment_id AND a.driver_id = current_driver_id()
        )
    );
CREATE POLICY messages_client_read ON messages FOR SELECT TO smt_client
    USING (company_id IS NOT NULL AND client_can_company(company_id));
CREATE POLICY messages_staff_insert ON messages FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (branch_id IS NOT NULL AND staff_can_branch(branch_id));

CREATE POLICY booking_events_staff ON booking_events FOR SELECT TO smt_owner, smt_staff
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_events.booking_id AND staff_can_branch(b.branch_id)
        )
    );
CREATE POLICY booking_events_driver ON booking_events FOR SELECT TO smt_driver
    USING (
        EXISTS (
            SELECT 1 FROM booking_assignments a
            WHERE a.booking_id = booking_events.booking_id AND a.driver_id = current_driver_id()
        )
    );
CREATE POLICY booking_events_client ON booking_events FOR SELECT TO smt_client
    USING (
        EXISTS (
            SELECT 1 FROM bookings b
            WHERE b.id = booking_events.booking_id AND client_can_company(b.company_id)
        )
    );

CREATE POLICY audit_read ON audit_logs FOR SELECT TO smt_owner, smt_staff
    USING (branch_id IS NOT NULL AND staff_can_branch(branch_id));
CREATE POLICY audit_insert ON audit_logs FOR INSERT TO smt_owner, smt_staff
    WITH CHECK (branch_id IS NOT NULL AND staff_can_branch(branch_id));

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM smt_driver;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM smt_client;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM smt_staff;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM smt_owner;

GRANT SELECT (id, role, full_name, email, phone, status, created_at)
    ON users TO smt_owner, smt_staff, smt_driver, smt_client;
GRANT INSERT, UPDATE (role, full_name, email, phone, status)
    ON users TO smt_owner;
REVOKE ALL ON TABLE users FROM smt_definer;
GRANT SELECT (id, role, status) ON users TO smt_definer;

GRANT SELECT ON user_branch_access TO smt_owner, smt_staff, smt_definer;
GRANT INSERT, DELETE ON user_branch_access TO smt_owner;
GRANT SELECT ON user_company_links TO smt_owner, smt_client, smt_definer;
GRANT INSERT, DELETE ON user_company_links TO smt_owner;

GRANT SELECT, INSERT, UPDATE ON companies TO smt_owner, smt_staff;
GRANT SELECT ON companies TO smt_client;
GRANT SELECT, INSERT, DELETE ON company_branches TO smt_owner, smt_staff;
GRANT SELECT ON company_branches TO smt_client;
GRANT SELECT, INSERT ON company_vehicles, company_drivers TO smt_owner, smt_staff;
GRANT DELETE ON company_vehicles, company_drivers TO smt_owner;

GRANT SELECT, INSERT, UPDATE, DELETE ON drivers TO smt_owner, smt_staff;
GRANT SELECT (
    id, user_id, primary_branch_id, display_name, phone, whatsapp_number,
    alternate_number, license_number, license_expiry, home_area, active
) ON drivers TO smt_driver;
GRANT UPDATE (phone, whatsapp_number, alternate_number, home_area)
    ON drivers TO smt_driver;
GRANT SELECT (id, user_id) ON drivers TO smt_definer;
GRANT SELECT, INSERT, DELETE ON driver_branches TO smt_owner, smt_staff;
GRANT SELECT ON driver_branches TO smt_driver;

GRANT SELECT, INSERT, UPDATE, DELETE ON vehicles, vehicle_documents TO smt_owner, smt_staff;
GRANT SELECT (id, branch_id, registration_number, model, capacity, fuel_type, is_ev, status, usual_driver_id)
    ON vehicles TO smt_driver;

GRANT SELECT, INSERT, UPDATE ON enquiries, ets_contracts TO smt_owner, smt_staff;
GRANT SELECT ON enquiries, ets_contracts TO smt_client;
GRANT SELECT, INSERT ON import_batches TO smt_owner, smt_staff;

GRANT SELECT, INSERT, UPDATE ON bookings TO smt_owner, smt_staff;
GRANT SELECT (
    id, branch_id, company_id, origin, trip_date, pickup_time, end_time,
    duty_type, cab_type, planned_start, route_text, employee_name,
    source_mobile, source_vehicle_no, status, created_at
) ON bookings TO smt_driver;
GRANT SELECT (
    id, branch_id, company_id, origin, trip_date, pickup_time, end_time,
    duty_type, cab_type, planned_start, route_text, employee_name, status, created_at
) ON bookings TO smt_client;

GRANT SELECT, INSERT, UPDATE ON booking_assignments TO smt_owner, smt_staff;
GRANT SELECT ON booking_assignments TO smt_driver;
GRANT UPDATE (status, rejection_reason, decided_at)
    ON booking_assignments TO smt_driver;
REVOKE ALL ON booking_assignments FROM smt_client;

GRANT SELECT ON client_duty_status TO smt_client;

GRANT SELECT ON assignment_events TO smt_owner, smt_staff, smt_driver;
GRANT SELECT ON booking_events TO smt_owner, smt_staff, smt_driver, smt_client;
REVOKE ALL ON assignment_events FROM smt_client;
GRANT INSERT ON assignment_events, booking_events TO smt_definer;
GRANT SELECT, UPDATE (status) ON bookings TO smt_definer;
GRANT SELECT, UPDATE (status, rejection_reason, decided_at, decided_by)
    ON booking_assignments TO smt_definer;
GRANT SELECT, UPDATE (status, ended_at) ON trip_sessions TO smt_definer;

GRANT SELECT, INSERT, UPDATE ON trip_sessions TO smt_owner, smt_staff, smt_driver;
GRANT SELECT ON gps_positions TO smt_owner, smt_staff, smt_driver;
GRANT INSERT ON gps_positions TO smt_driver;
GRANT SELECT, INSERT, UPDATE, DELETE ON trip_passengers, safety_alerts TO smt_owner, smt_staff;
GRANT SELECT ON trip_passengers, safety_alerts TO smt_driver;
GRANT SELECT ON trip_passengers TO smt_client;

GRANT SELECT, INSERT, UPDATE, DELETE ON booking_charges TO smt_owner, smt_staff;
GRANT SELECT ON booking_charges TO smt_client;
GRANT SELECT, INSERT, UPDATE, DELETE ON duty_readings TO smt_owner, smt_staff;
GRANT SELECT, UPDATE (start_km, end_km, total_km, driver_hours, driver_km)
    ON duty_readings TO smt_driver;

GRANT SELECT, INSERT, UPDATE ON invoices TO smt_owner, smt_staff;
GRANT SELECT ON invoices TO smt_client;
GRANT SELECT, INSERT, UPDATE, DELETE ON invoice_lines, payments TO smt_owner, smt_staff;
GRANT SELECT ON invoice_lines, payments TO smt_client;
GRANT SELECT ON invoice_balances TO smt_owner, smt_staff, smt_client;
GRANT SELECT, INSERT, UPDATE, DELETE ON driver_payouts TO smt_owner, smt_staff;
GRANT SELECT (id, booking_id, driver_id, status, amount, paid_at, currency)
    ON driver_payouts TO smt_driver;

GRANT SELECT, INSERT ON chat_sessions, messages TO smt_owner, smt_staff;
GRANT SELECT ON chat_sessions, messages TO smt_client;
GRANT SELECT ON messages TO smt_driver;
GRANT SELECT, INSERT ON audit_logs TO smt_owner, smt_staff;
GRANT SELECT ON branches TO smt_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smt_owner, smt_staff, smt_driver, smt_definer;

CREATE FUNCTION identity_status_guard()RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.identity_status IS DISTINCT FROM 'clean'
       AND NEW.identity_status = 'clean'
       AND NOT EXISTS (
            SELECT 1 FROM reconciliation_decisions d
            WHERE d.entity_name = 'bookings'
              AND d.legacy_source IS NOT DISTINCT FROM NEW.legacy_source
              AND d.legacy_id IS NOT DISTINCT FROM NEW.legacy_booking_id
              AND d.decision = 'mark_clean'
       ) THEN
        RAISE EXCEPTION 'A conflict or missing code cannot become clean without a reconciliation decision';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER identity_status_guard_trg
    BEFORE UPDATE OF identity_status ON bookings
    FOR EACH ROW EXECUTE FUNCTION identity_status_guard();

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smt_migrate;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smt_migrate;

COMMIT;
