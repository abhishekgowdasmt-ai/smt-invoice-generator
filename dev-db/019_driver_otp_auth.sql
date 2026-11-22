-- Forward migration 019 — Driver OTP login and password reset.
--
-- Stores short-lived OTP challenges for driver phone auth.
-- OTP operations run as smt_owner via the app bootstrap owner path.
-- Does not weaken RLS on operational tables.
--
-- Apply as a superuser, with ON_ERROR_STOP, to disposable smt_revision8_test
-- first. Do not apply to smt_dev or production without separate approval.
\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE IF NOT EXISTS public.driver_auth_otps (
    id              bigserial PRIMARY KEY,
    phone           text NOT NULL,
    purpose         text NOT NULL
                    CHECK (purpose IN ('login', 'reset')),
    code_hash       text NOT NULL,
    attempts        integer NOT NULL DEFAULT 0
                    CHECK (attempts >= 0),
    expires_at      timestamptz NOT NULL,
    consumed_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT driver_auth_otps_phone_digits
        CHECK (phone ~ '^[0-9]{10}$')
);

CREATE INDEX IF NOT EXISTS driver_auth_otps_phone_purpose_idx
    ON public.driver_auth_otps (phone, purpose, created_at DESC);

CREATE INDEX IF NOT EXISTS driver_auth_otps_expires_idx
    ON public.driver_auth_otps (expires_at);

COMMENT ON TABLE public.driver_auth_otps IS
    'Short-lived hashed OTP challenges for driver login and password reset.';

ALTER TABLE public.driver_auth_otps ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS driver_auth_otps_owner_all ON public.driver_auth_otps;
CREATE POLICY driver_auth_otps_owner_all ON public.driver_auth_otps
    FOR ALL TO smt_owner
    USING (true)
    WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.driver_auth_otps TO smt_owner;
GRANT USAGE, SELECT ON SEQUENCE public.driver_auth_otps_id_seq TO smt_owner;

COMMIT;
