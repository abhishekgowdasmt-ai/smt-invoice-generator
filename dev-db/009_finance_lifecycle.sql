-- Forward migration. Extends the Revision 7 financial tables for supervisor
-- invoice lifecycle, soft payment reversal, payout uniqueness, and expenses.
-- Does not change RLS force flags, invoice_line_guard payment ceilings, or
-- company/booking composite keys.
-- Apply as a superuser, with ON_ERROR_STOP, to one disposable local _test
-- database first. Do not apply to smt_dev or production without approval.
\set ON_ERROR_STOP on
BEGIN;

-- Invoice due dates and void history (issued invoices are not deleted).
ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS due_date date,
    ADD COLUMN IF NOT EXISTS voided_at timestamptz,
    ADD COLUMN IF NOT EXISTS void_reason text,
    ADD COLUMN IF NOT EXISTS notes text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_void_reason_chk;
ALTER TABLE invoices
    ADD CONSTRAINT invoices_void_reason_chk CHECK (
        (voided_at IS NULL AND void_reason IS NULL)
        OR (voided_at IS NOT NULL AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
    );

-- Soft reverse keeps the payment row; balances ignore reversed rows.
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS reversed_at timestamptz,
    ADD COLUMN IF NOT EXISTS reversal_reason text;

ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_reversal_reason_chk;
ALTER TABLE payments
    ADD CONSTRAINT payments_reversal_reason_chk CHECK (
        (reversed_at IS NULL AND reversal_reason IS NULL)
        OR (reversed_at IS NOT NULL AND reversal_reason IS NOT NULL AND btrim(reversal_reason) <> '')
    );

CREATE OR REPLACE FUNCTION assert_invoice_covered(
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
    FROM payments
    WHERE invoice_id = p_invoice AND reversed_at IS NULL;
    IF paid + p_payment_delta > line_total + p_line_delta THEN
        RAISE EXCEPTION 'Payments would exceed the invoice lines';
    END IF;
END;
$$;

CREATE OR REPLACE VIEW invoice_balances
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
    WHERE reversed_at IS NULL
    GROUP BY invoice_id
) pays ON pays.invoice_id = i.id;

-- Driver payout status and one active payout per booking.
UPDATE driver_payouts
SET status = lower(btrim(status))
WHERE status IS NOT NULL;

UPDATE driver_payouts
SET status = 'pending'
WHERE status IS NULL OR status NOT IN ('pending', 'paid', 'cancelled');

ALTER TABLE driver_payouts DROP CONSTRAINT IF EXISTS driver_payouts_status_chk;
ALTER TABLE driver_payouts
    ADD CONSTRAINT driver_payouts_status_chk
    CHECK (status IN ('pending', 'paid', 'cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS one_active_payout_per_booking
    ON driver_payouts (booking_id)
    WHERE status IN ('pending', 'paid');

ALTER TABLE driver_payouts
    ADD COLUMN IF NOT EXISTS reference text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE driver_payouts DROP CONSTRAINT IF EXISTS driver_payouts_reference_not_blank;
ALTER TABLE driver_payouts
    ADD CONSTRAINT driver_payouts_reference_not_blank CHECK (
        reference IS NULL OR btrim(reference) <> ''
    );

-- Branch expenses (no statutory tax fields; amounts are INR only).
CREATE TABLE IF NOT EXISTS expenses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id uuid NOT NULL REFERENCES branches(id),
    company_id uuid REFERENCES companies(id),
    category text NOT NULL,
    description text NOT NULL,
    currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    amount numeric(12, 2) NOT NULL CHECK (amount > 0),
    expense_date date NOT NULL,
    document_ref text,
    status text NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'approved', 'paid', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT expenses_category_not_blank CHECK (btrim(category) <> ''),
    CONSTRAINT expenses_description_not_blank CHECK (btrim(description) <> ''),
    CONSTRAINT expenses_document_ref_not_blank CHECK (
        document_ref IS NULL OR btrim(document_ref) <> ''
    ),
    CONSTRAINT expense_company_branch_fk
        FOREIGN KEY (company_id, branch_id)
        REFERENCES company_branches (company_id, branch_id)
);

CREATE INDEX IF NOT EXISTS expenses_branch_date ON expenses (branch_id, expense_date);
CREATE INDEX IF NOT EXISTS expenses_company_date ON expenses (company_id, expense_date);
CREATE INDEX IF NOT EXISTS expenses_status ON expenses (status);

ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS expenses_staff ON expenses;
CREATE POLICY expenses_staff ON expenses FOR ALL TO smt_owner, smt_staff
    USING (staff_can_branch(branch_id))
    WITH CHECK (staff_can_branch(branch_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON expenses TO smt_owner, smt_staff;

COMMIT;
