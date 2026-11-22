# Production Readiness and Deployment Guide (Master Prompt 10)

**Status:** Preparation documentation only.  
**Not authorized:** production deploy, production DB migration, production config changes, GitHub push.

This document separates **verified development configuration**, **proposed production configuration**, and **items requiring owner approval**.

---

## 1. Production architecture (proposed)

| Layer | Component |
|-------|-----------|
| Edge | Reverse proxy / TLS terminator (existing host pattern: Caddy → gunicorn observed historically) |
| App | Container from root `Dockerfile` via `start.sh`: WhatsApp bridge, OCR worker, gunicorn `backend.app:app` |
| Data (current production) | SQLite + RAC JSON + Zoho integrations (must not be replaced without a separately approved migration plan) |
| Data (PostgreSQL target) | Shared register for Supervisor / Driver / Client portal features developed in this project |
| Clients | Supervisor Website (`/admin`), Client Portal (`/client/`), Flutter Android Driver App |

RAC JSON, SQLite supervisor paths, Zoho, and `/api/v1` remain intact and must not be merged with PostgreSQL records without an approved plan.

---

## 2. Required services

1. Application container (Flask/gunicorn + bridge + OCR per `start.sh`)
2. PostgreSQL (when PostgreSQL features are enabled in that environment)
3. Optional: WhatsApp bridge process, OCR worker (already started by `start.sh` when configured)
4. TLS / DNS for the public hostname

---

## 3. Environment variables (names only)

See also `PRODUCTION_ENV_CHECKLIST.md`. Critical names:

| Name | Area |
|------|------|
| `STAFF_TOKEN` | Staff cookie / OAuth state signing |
| `RAC_JWT_SECRET` | Dispatch bearer tokens |
| `RAC_INGEST_KEY` / `WEBSITE_API_KEY` / `OCR_INGEST_KEY` | Ingest auth (aligned by `start.sh`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Supervisor Google login |
| `SMT_DEV_DATABASE_URL` | Local/dev PostgreSQL DSN (production must use a production-scoped name/process; do not reuse disposable test DB) |
| `SMT_DEV_BOOTSTRAP_OWNER_ID` | Bootstrap owner UUID for local identity |
| SMTP_* | Enquiry mail (optional) |
| OCR / Gemini related keys | Booking OCR |

Do not place secrets in git. Do not rotate credentials during this milestone.

---

## 4. Database setup prerequisites

- PostgreSQL 16+ (as used in local disposable verification)
- Roles: `smt_app`, `smt_owner`, `smt_staff`, `smt_driver`, `smt_client`, `smt_definer` (+ migrate role as documented in schema plan)
- RLS enabled with existing policies
- Asia/Kolkata timezone expectations as in local verification

**Verified development:** disposable `smt_revision8_test` with migrations through **017** applied.  
**Proposed production:** apply the same ordered migrations to a dedicated production database only after backup + owner approval.

---

## 5. Migration order

Apply forward-only numbered migrations in order. Baseline for this project’s PostgreSQL features includes through **017** (app notifications grants).  

**Prepared, not applied:** `dev-db/018_client_cancel_consistency_definer.sql` — required to fix client cancel COMMIT privilege failure. **Owner approval required before any apply.**

Never apply disposable-test experiments to production without review.

---

## 6. Backup procedure (proposed)

1. Stop or quiesce writers if a consistent logical dump is required.
2. `pg_dump` the target database (custom or plain format) to encrypted storage.
3. Record migration head / schema version and application git SHA.
4. Verify dump file size and restore-test on a non-production host.

---

## 7. Restore procedure (proposed)

1. Create empty target database and roles.
2. Restore dump.
3. Confirm role memberships and RLS.
4. Point application DSN at restored DB only after smoke tests on a staging URL.

---

## 8. Deployment sequence (proposed — owner approval required)

1. Confirm secrets present in host secret store (names in §3).
2. Backup production data stores (SQLite/JSON and PostgreSQL if already in use).
3. Build container image from approved git SHA (no unapproved push from this workspace).
4. Deploy image; do not change production DSN to disposable test databases.
5. If PostgreSQL cutover is approved: apply migrations in order on the production DB only.
6. Run post-deployment smoke tests (§10).
7. Monitor logs for auth/DB errors.

**Manual approval checkpoints:** image promote, migration apply, DNS cutover, credential rotation (if any).

---

## 9. Rollback procedure (proposed)

1. Redeploy previous known-good image SHA.
2. If a migration was applied: restore from pre-migration dump (do not invent down-migrations unless separately authored and approved).
3. Re-verify login and one booking read path.
4. Communicate status to operators.

---

## 10. Post-deployment verification (smoke)

- `/admin` Google login (production) or documented staff path
- `/api/admin/me` authenticated
- `/client/` login for one company
- Driver app login against production API URL
- One booking list read; one report JSON read
- Confirm RAC `/api/v1` ingest still authorized
- Confirm logs show no credential leakage

---

## 11. Known limitations

1. Client booking soft-retry is not concurrency-safe (parallel POSTs can insert two rows).
2. Soft-retry returns HTTP 201 with `already: true`.
3. Driver→client notifications use owner-mediated posting.
4. No push notifications; clients/drivers/staff poll.
5. No WebSockets.
6. No scheduled background report/notification jobs.
7. Physical Android device testing not completed in Prompt 10.
8. **Client cancel of unassigned requests fails until migration 018 is approved and applied** (High).
9. Existing production SQLite/JSON/Zoho stack is not automatically replaced by PostgreSQL.

---

## 12. Manual approval checkpoints

| Checkpoint | Owner action |
|------------|--------------|
| Apply 018 on `smt_revision8_test` | Review SQL + APPLY note; approve |
| Apply 018 on `smt_dev` | Separate approval |
| Production PostgreSQL migrate / cutover | Separate plan + approval |
| Deploy new image | Approve SHA |
| GitHub push | Explicit request |
| Credential rotation | Explicit request |

---

## Distinction summary

| Verified development | Proposed production | Needs owner approval |
|----------------------|---------------------|----------------------|
| Disposable `smt_revision8_test` automated suites green | Hosted gunicorn + TLS | Any production change |
| Local Flask on 127.0.0.1 with process overlay to test DB | Production DSN + Google OAuth | Migration 018 apply |
| Debug APK built | Release signing / Play distribution | Store credentials / keys |
| Docs in this repo | Runbook execution | Deploy / push / rotate |
