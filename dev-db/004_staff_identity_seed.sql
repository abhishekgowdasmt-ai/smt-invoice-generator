-- Local development identities for the existing Google allowlists.
-- OD allowlist -> owner. Other staff allowlist -> staff.
-- No passwords, no invented Google subject identifiers, no branch grants.
-- A conflicting role aborts the transaction.

\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    conflict_count integer;
BEGIN
    SELECT count(*) INTO conflict_count
    FROM users
    WHERE (
            lower(email) IN (
                'abhishekgowdasmt@gmail.com',
                'shreemaruthitravels5999@gmail.com'
            )
            AND role <> 'owner'
        )
        OR (
            lower(email) = 'bhaskarbhaskarreddy9005@gmail.com'
            AND role <> 'staff'
        )
        OR (
            lower(email) = 'veeruashwini01@gmail.com'
            AND role <> 'staff'
        );
    IF conflict_count > 0 THEN
        RAISE EXCEPTION 'ROLE_CONFLICT';
    END IF;

    SELECT count(*) INTO conflict_count
    FROM (
        SELECT lower(email)
        FROM users
        WHERE lower(email) IN (
            'abhishekgowdasmt@gmail.com',
            'shreemaruthitravels5999@gmail.com',
            'veeruashwini01@gmail.com',
            'bhaskarbhaskarreddy9005@gmail.com'
        )
        GROUP BY lower(email)
        HAVING count(*) > 1
    ) duplicates;
    IF conflict_count > 0 THEN
        RAISE EXCEPTION 'DUPLICATE_IDENTITY';
    END IF;
END $$;

INSERT INTO users (role, full_name, email, status)
SELECT seed.role, seed.email, seed.email, 'active'
FROM (
    VALUES
        ('owner', 'abhishekgowdasmt@gmail.com'),
        ('owner', 'shreemaruthitravels5999@gmail.com'),
        ('staff', 'bhaskarbhaskarreddy9005@gmail.com')
) AS seed(role, email)
WHERE NOT EXISTS (
    SELECT 1 FROM users existing WHERE lower(existing.email) = lower(seed.email)
);

UPDATE users
SET status = 'active'
WHERE lower(email) IN (
    'abhishekgowdasmt@gmail.com',
    'shreemaruthitravels5999@gmail.com',
    'bhaskarbhaskarreddy9005@gmail.com'
)
AND status IS DISTINCT FROM 'active';

DELETE FROM user_branch_access
WHERE user_id IN (
    SELECT id FROM users WHERE lower(email) = 'veeruashwini01@gmail.com'
);

UPDATE users
SET status = 'disabled'
WHERE lower(email) = 'veeruashwini01@gmail.com'
  AND role = 'staff'
  AND status IS DISTINCT FROM 'disabled';

COMMIT;

SELECT role, lower(email) AS email, status,
       (password_hash IS NOT NULL) AS has_password,
       (google_sub IS NOT NULL) AS has_google_sub
FROM users
WHERE lower(email) IN (
    'abhishekgowdasmt@gmail.com',
    'shreemaruthitravels5999@gmail.com',
    'veeruashwini01@gmail.com',
    'bhaskarbhaskarreddy9005@gmail.com'
)
ORDER BY role, email;
