# Security cleanup plan

Date: 18 November 2026. This document is a plan only. No application file, hosting setting, or git commit was changed to produce it.

It covers the security items in `PROJECT_AUDIT.md` that can be fixed without removing Google login, OCR, or WhatsApp. Database migration, GPS, invoice PDFs, and splitting the OD ledger are out of this stage.

No secret values are written here.

## Production impact, before any edit

These are the only changes in this plan that can change a live login or a live upload.

| Change | Who notices | If the host is not prepared |
| --- | --- | --- |
| Refuse to boot when `STAFF_TOKEN` is missing | Every staff Google session | The site does not start, or, if the check is only a warning, forged cookies remain possible |
| Set a new `STAFF_TOKEN` on the host | Every currently signed-in staff member | They must sign in with Google again. Old cookies stop working. This is expected. |
| Set a new `RAC_JWT_SECRET` | Dispatch screens that stored a bearer token | The React app asks `/auth/staff` again and gets a new token. Google login itself still works. |
| Remove the RAC email/password check | The dispatch password form | Anonymous visitors already cannot pass `protect_rac_api`. Staff who use Google are unchanged. |
| Remove the loopback ingest bypass | Booking OCR publish and lookup only | If no ingest key is configured, those two routes return HTTP 503. The website, Google login, dispatch, and Excel upload still start. |
| Leave Google routes and the staff allowlist alone | Nobody | Required. Do not edit those functions in this stage. |

OCR screenshot reading and the WhatsApp bridge process are not part of the code edits below.

---

## 1. Exact files and functions

### Must change when implementation is approved

| File | Symbol | Why |
| --- | --- | --- |
| `shree-maruthi-travels-main/shree-maruthi-travels-main/backend/rac_api.py` | Module constants `RAC_EMAIL`, `RAC_PASSWORD`, `TOKEN` | Email and password fall back to values committed in source. The dispatch token signer falls back to a constant, then to `STAFF_TOKEN`. |
| same file | `login()` | `POST /api/v1/auth/login` still accepts that email and password. |
| same file | `staff_session()` | Builds the dispatch user from `RAC_USER`, which is tied to the password account. After removal it must copy the Google staff identity only. |
| same file | `_auth_user()` | Accepts a bearer token signed by `TOKEN`, then falls back to the staff cookie. Keep the cookie path. |
| same file | `_ingest_key_ok()` | Key check is correct. Keep it. |
| same file | `require_rac_or_ingest()` | Second copy of the loopback bypass, on `POST /bookings/ingest` and `GET /bookings/ingest/lookup`. |
| `shree-maruthi-travels-main/shree-maruthi-travels-main/backend/staff_auth.py` | `STAFF_TOKEN`, `_SERIALIZER`, `read_token()`, `issue_token()` | Cookie signer falls back to a constant when `STAFF_TOKEN` is empty. |
| `shree-maruthi-travels-main/shree-maruthi-travels-main/backend/app.py` | `protect_rac_api()` | First copy of the loopback bypass, for every path under `/api/v1/bookings/ingest`. |
| same file | `_is_loopback()` | Used by ingest, by `admin_local_login()`, and by `admin_me()`. Do not delete it. Local staff login on a developer machine still needs it. |
| `shree-maruthi-travels-main/shree-maruthi-travels-main/rac/frontend/src/App.jsx` | `LoginPage`, `login()` | The form still posts an email and password and pre-fills the local admin email. |
| `shree-maruthi-travels-main/shree-maruthi-travels-main/.env.example` | comment on `RAC_PASSWORD` | The example currently shows a sample password. Replace that comment with “password login is disabled”. Do not put a sample secret in the file. |

### Change only so the unused Node stack cannot be started with a known password

These files are not in the production image built by `start.sh`. Editing them does not change the live site. They still need the same cleanup so a later `docker compose up` does not recreate the hole.

| File | Symbol |
| --- | --- |
| `rac/backend/src/server.js` | startup block that creates `admin@dispatch.local` |
| `rac/backend/db/seed.js` | same seed |
| `docker-compose.yml` | `POSTGRES_PASSWORD`, `DATABASE_URL`, `JWT_SECRET` defaults |
| `rac/README.md`, `rac/REACT_PAGES_SUMMARY.md`, `rac/frontend/PAGES.md`, `rac/.github/copilot-instructions.md` | docs that print the password |

### Do not change in this stage

| File | Why it stays |
| --- | --- |
| `staff_auth.google_authorize_url`, `google_exchange`, `issue_token` body, `role_for`, `staff_emails`, `od_emails` | This is the live Google login. |
| `app.py` `admin_google_login`, `admin_google_callback`, `_set_staff_cookie`, `admin_local_login` | Google and the localhost-only staff form. |
| `start.sh` | Already points OCR at `http://127.0.0.1:$PORT/api/v1` and copies a single ingest key across `RAC_INGEST_KEY`, `WEBSITE_API_KEY`, and `OCR_INGEST_KEY`. |
| `tools/wa_booking_ingest/publisher.py` `_headers()` | Already sends `X-Ingest-Key` from `WEBSITE_API_KEY`. |
| `tools/wa_booking_ingest/ocr_provider.py` | Screenshot reading. |
| `backend/wa_bridge/server.js` | WhatsApp send and QR. |
| `backend/zoho_sheet.py`, `backend/zoho_workdrive.py` | Zoho. |
| `Dockerfile` | No new secrets belong in the image. |

`app.py` line 47 already wraps the app in Werkzeug `ProxyFix` with `x_for=1`, `x_proto=1`, and `x_host=1`. That matters for the loopback check. See section 4.

---

## 2. Remove the default RAC email and password

Current behaviour, verified in source:

- `RAC_EMAIL` and `RAC_PASSWORD` are read from the environment and, when unset, replaced with values committed in `rac_api.py`.
- `login()` returns 200 and a dispatch token when both match.
- `protect_rac_api()` runs first and returns 401 when there is no staff cookie. So an anonymous visitor does not reach `login()` today. The password is still a second credential for anyone who is already staff, and it is public because it is in the repository.

Implementation, after approval:

1. Delete `RAC_PASSWORD` and stop reading `RAC_PASSWORD`.
2. Change `login()` to the same response as `admin_login()`: HTTP 410 and a message that dispatch uses the SMT Google sign-in. Do not check a password.
3. Change `staff_session()` so the user object comes only from `staff_auth.current_staff()`. Do not copy `RAC_USER`. If there is no staff cookie, return 401. `protect_rac_api()` already enforces that. The function should not have its own fallback identity.
4. In `App.jsx`, remove the email and password form. The unauthenticated screen should say to open `/admin` and sign in with Google. Keep `AuthProvider`: when a staff cookie exists, `GET /api/v1/auth/staff` still stores the returned token.
5. In the Node seed and `server.js`, do not create a user when a password is not provided by the environment. Do not commit a fallback password. If the password variable is empty, skip the seed and log that no admin was created.
6. In `docker-compose.yml`, stop writing a database password and a JWT secret in the file. Read them from the shell environment and fail the compose file’s comments with “set these outside git”.
7. Delete the password from the four Markdown files listed above. Do not replace it with another sample.

What this does not do: it does not change `/admin/google/login` or the allowlist.

---

## 3. Require environment-provided signing secrets

Two signers exist.

| Signer | File | Environment name | Used for |
| --- | --- | --- | --- |
| Staff cookie | `staff_auth.py` `_SERIALIZER` | `STAFF_TOKEN` | `smt_staff` cookie, Google OAuth `state` |
| Dispatch bearer token | `rac_api.py` `TOKEN` | `RAC_JWT_SECRET` | Token returned by `/api/v1/auth/staff` and sent as `Authorization: Bearer` |

Today each one uses a hardcoded string when the variable is empty. `TOKEN` will also use `STAFF_TOKEN` if `RAC_JWT_SECRET` is empty, so one leaked value signs both.

Implementation, after approval:

1. Add one function in `staff_auth.py`, for example `require_secret(name)`, that reads the variable, strips it, and raises `RuntimeError` if it is missing or shorter than 32 characters. Do not log the value.
2. Call it for `STAFF_TOKEN` when the serializer is created.
3. Call it for `RAC_JWT_SECRET` when `TOKEN` is created. Do not fall back to `STAFF_TOKEN`. The two secrets stay different so a dispatch token cannot be reused as a staff cookie.
4. Keep `read_token()` rejecting a cookie that is exactly the raw secret string. That check stays.
5. Do not put a generated secret in `Dockerfile`, `start.sh`, or `.env.example`. The host must provide it.
6. Local development: the existing gitignored `.env` may define both names. The app already loads that file. Developers without the names will get a startup error that names the variable and not a sample value.

Deploy order, because this logs people out:

1. On the host, confirm the names `STAFF_TOKEN` and `RAC_JWT_SECRET` are set. Confirm only that they are non-empty. Do not print them.
2. If either is empty, generate a new value on the host and save it in the host’s secret store.
3. Deploy the code that refuses to boot without them.
4. Tell staff to open `/admin` and sign in with Google once. Existing cookies and dispatch bearer tokens from before the new secret will not verify. That is the rollback cost as well.

If production already has a long `STAFF_TOKEN`, leave that value in place so current Google cookies keep working. Only the code fallback is removed. Same for `RAC_JWT_SECRET` if it is already set.

---

## 4. Verify the loopback ingest bypass before removing it

Two functions allow a request with no staff cookie and no ingest key when the Host header is `localhost`, `127.0.0.1`, or `::1` and `request.remote_addr` is `127.0.0.1` or `::1`:

- `app.py` `protect_rac_api()`
- `rac_api.py` `require_rac_or_ingest()`

`ProxyFix(..., x_for=1)` rewrites `remote_addr` from `X-Forwarded-For` when that header is present. A direct call from the OCR process to `127.0.0.1` does not send that header, so it still looks like loopback. A public request should look like the visitor’s address only if the platform proxy appends the real client and Flask trusts exactly that one proxy hop.

Do this measurement before changing the bypass. It does not require a code change.

1. From a machine that is not the server, call `GET /api/v1/bookings/ingest/lookup?source_booking_id=probe` on the public site with no `X-Ingest-Key` and no cookie. Expected today: HTTP 401. If it is 200, the bypass is already public and the bypass must be removed before anything else.
2. Repeat that public call with request headers `Host: 127.0.0.1` and `X-Forwarded-For: 127.0.0.1`. Expected: still 401, because the platform should replace or ignore a client-supplied forwarded-for. If this returns 200, `ProxyFix` is trusting the caller and the bypass is exploitable. Remove the bypass in the same change.
3. On the server, from inside the container, call the same path at `http://127.0.0.1:$PORT/api/v1/bookings/ingest/lookup` with header `X-Ingest-Key` set to the host’s `RAC_INGEST_KEY` (or `WEBSITE_API_KEY` if that is the one `start.sh` copied). Expected: not 401. A 404 or a JSON `found: false` means the key was accepted.
4. Repeat the inside call with no key. Expected today: success, because of the bypass. That is the behaviour this cleanup removes.

Code change, only after step 1 and step 2 are 401:

1. Delete the `_is_loopback()` branch inside `protect_rac_api()`. Keep the branch that accepts a matching `X-Ingest-Key`.
2. Delete the host-and-remote block at the start of `require_rac_or_ingest()`. Keep `_ingest_key_ok()` and the staff-cookie path.
3. Do not change `_is_loopback()` itself. `admin_local_login()` must still be limited to a developer machine when Google is not configured.
4. Do not exit `start.sh` when the ingest key is missing. The website must still boot. `start.sh` keeps copying a key onto the other names only when one of them is set. When none is set, ingest routes return HTTP 503 and there is no loopback bypass.
5. Do not log the key.

---

## 5. Protect the existing Google staff login

Leave these exactly as they are:

- `GET /admin/google/login` and `GET /admin/google/callback`
- `staff_auth.google_configured`, `google_authorize_url`, `google_exchange`
- `issue_token`, `role_for`, the `STAFF_EMAILS` / `OD_EMAILS` / `STAFF_EXTRA_EMAILS` allowlist behaviour
- `POST /admin/local-login` and its rule: only when Google is not configured and `_is_loopback()` is true
- `POST /api/admin/login` staying HTTP 410
- Cookie flags in `_set_staff_cookie`: HttpOnly, SameSite Lax, Secure when the request is HTTPS

Also keep `GET /api/admin/me`. It is how the admin page knows who is signed in.

Do not put Google client id or client secret in the repository. They stay host environment variables.

The dispatch UI may keep calling `GET /api/v1/auth/staff` after Google login. That route should keep issuing a bearer token, signed with `RAC_JWT_SECRET`, for the email already in the staff cookie. It must not issue a token for the old password account.

Moving that bearer token out of `localStorage` is not part of this stage. It changes the dispatch session and can be done after this cleanup. Google login does not depend on `localStorage`.

---

## 6. Preserve OCR ingestion and WhatsApp

OCR publish path that must keep working:

1. Browser uploads a screenshot to `POST /api/v1/bookings/ocr-upload` with a staff cookie. `protect_rac_api()` allows it because the staff cookie is present. This route is not under `/bookings/ingest`, so the loopback change does not affect the upload.
2. Flask proxies to the OCR worker on `OCR_INGEST_URL` (default `http://127.0.0.1:8787`).
3. The worker reads the image, then calls `GET /api/v1/bookings/ingest/lookup` and `POST /api/v1/bookings/ingest` on `WEBSITE_API_URL`.
4. `publisher.py` sends `X-Ingest-Key`. `start.sh` sets `WEBSITE_API_URL` to the same container and copies the ingest key.

After the bypass is removed, step 4 is the only way those two ingest routes succeed. The worker does not have a staff cookie. That is why the host key must be confirmed before the bypass is deleted.

WhatsApp path that must keep working:

1. `start.sh` still starts `node backend/wa_bridge/server.js` on `127.0.0.1:3100`.
2. Assignment, reassignment, unassign, and cancel in `rac_api.py` still call that process. Do not edit those functions in this stage.
3. Do not open port 3100 on the public interface. Do not commit `backend/wa_bridge/auth/`.
4. The React page `/admin/dispatch/whatsapp-qr` still reads bridge status through the existing Flask route.

No change to Gemini, Tesseract, or OCR.space settings in this stage.

---

## 7. Environment variable names

Set on the host that runs the Flask image. Values stay in the host secret store.

| Name | Required for this cleanup | Purpose |
| --- | --- | --- |
| `STAFF_TOKEN` | Yes, before the signer change | Signs the staff cookie and the Google `state` value |
| `RAC_JWT_SECRET` | Yes, before the signer change | Signs the dispatch bearer token. Must be different from `STAFF_TOKEN` |
| `RAC_INGEST_KEY` | Required only to enable OCR publish. The site still boots without it. | Shared secret for OCR publish. `start.sh` copies it to the two names below if they are empty. If all three are empty, ingest returns HTTP 503. |
| `WEBSITE_API_KEY` | Set by `start.sh` from `RAC_INGEST_KEY` when empty | Header the OCR worker sends |
| `OCR_INGEST_KEY` | Set by `start.sh` from `RAC_INGEST_KEY` when empty | Accepted as an alias of the ingest key |
| `GOOGLE_CLIENT_ID` | Already required for Google login | Do not rotate it as part of this work |
| `GOOGLE_CLIENT_SECRET` | Already required for Google login | Do not rotate it as part of this work |
| `STAFF_EMAILS` | Keep the current allowlist | Empty would fall back to the emails in source. Leave the host value as it is |
| `OD_EMAILS` | Keep the current allowlist | Same |
| `GEMINI_API_KEY` | No change in this stage | OCR |
| `OCR_SPACE_API_KEY` | No change | OCR, optional |
| `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` | No change | Zoho Sheet |
| `WORKDRIVE_REFRESH_TOKEN` | No change | WorkDrive |

Remove from the host after the password code is gone, so an old value cannot be turned back on by mistake:

- `RAC_PASSWORD`
- `RAC_EMAIL` if it is only the local admin address

`docker-compose.yml`, when that unused stack is edited, should require these names from the shell and should not contain values:

- `POSTGRES_PASSWORD`
- `JWT_SECRET`

---

## 8. Hosting configuration

Do this in the host’s secret UI. Do not put the values in git, in `Dockerfile`, or in `render.yaml`.

1. Record whether `STAFF_TOKEN`, `RAC_JWT_SECRET`, and `RAC_INGEST_KEY` are currently non-empty. Write down only yes or no.
2. If `STAFF_TOKEN` or `RAC_JWT_SECRET` is empty, create a new value in the host and save it before deploying the signer change. If they are already set, keep them so existing Google cookies survive.
3. `RAC_INGEST_KEY` may stay empty. The website still starts. OCR publish stays off until a key is set and the container is restarted. Do not block this deploy on that name.
4. Do not change `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, Zoho variables, or `GEMINI_API_KEY` in this stage.
5. After the code deploy, sign in at `/admin` with Google and open Booking OCR. Upload no screenshot until lookup from inside the container accepts the key.

Which product applies the secrets (AIC, Fly, or Render) is still unconfirmed. The names above are the same on all three. A git push does not apply them.

---

## 9. Automated tests

Add these before merging the behaviour change. Run the existing OCR tests in the same command so ingestion parsing does not regress.

New tests, using Flask’s test client and a temporary `STAFF_TOKEN` / `RAC_JWT_SECRET` set in the test process. Tests must not read `.env` and must not print secrets.

| Test | Expected |
| --- | --- |
| Importing `staff_auth` with `STAFF_TOKEN` unset | Startup error that names `STAFF_TOKEN` |
| Importing `rac_api` with `RAC_JWT_SECRET` unset | Startup error that names `RAC_JWT_SECRET` |
| `POST /api/v1/auth/login` with any body | HTTP 410, and the body does not contain a token |
| `GET /api/v1/auth/staff` with no cookie | HTTP 401 |
| `GET /api/v1/auth/staff` with a cookie from `issue_token` for an allowlisted email | HTTP 200 and a bearer token that `_auth_user()` accepts |
| Cookie signed with a different `STAFF_TOKEN` | `current_staff()` is `None` |
| With `STAFF_TOKEN` and `RAC_JWT_SECRET` set and no ingest key, `GET /` and `GET /api/admin/me` | The app starts. Home is not a boot failure. `/api/admin/me` without a cookie is HTTP 401. |
| Ingest lookup or publish with no ingest key configured, including loopback | HTTP 503, no booking created |
| Ingest lookup with a key configured but no `X-Ingest-Key`, including loopback | HTTP 401 |
| Same path with a matching `X-Ingest-Key` | Not 401 and not 503 |
| `POST /admin/local-login` when Google variables are set | HTTP 403, even from loopback |
| `POST /admin/local-login` when Google variables are empty and the request is not loopback | HTTP 403 |

Existing suites to run unchanged:

- `tools/wa_booking_ingest/tests/test_ocr_provider.py`
- `tools/wa_booking_ingest/tests/test_pipeline.py`
- `tools/wa_booking_ingest/tests/test_parser.py`
- `tools/wa_booking_ingest/tests/test_duplicates.py`

Manual check after deploy, one staff Google account:

- `/admin` shows the signed-in email.
- `/admin/dispatch/` opens without the password form.
- WhatsApp status page still loads.
- One OCR lookup from inside the container with the ingest key is not 401.

---

## 10. Rollback

Code rollback is `git revert` of the cleanup commit and a redeploy of that revert. Do not force-push.

Secret rollback:

- If `STAFF_TOKEN` was left at its previous host value, a code rollback restores the old fallback only for environments where the variable is empty. Production cookies keep working because the host value did not change.
- If a new `STAFF_TOKEN` was saved, restoring the old value after a rollback brings back the previous cookies. Restoring it is a host change, not a git change. Until it is restored, staff sign in with Google again.
- If the ingest bypass was removed and OCR starts failing with 401, either put the bypass code back with the revert, or set `RAC_INGEST_KEY` and restart. Restart is enough when the key is set, because `start.sh` copies it before the worker starts. Do not open ingest to the public as a temporary fix.

WhatsApp auth files and Zoho token files are not touched, so a rollback does not unlink WhatsApp and does not disconnect Zoho.

Stop the rollout if, after deploy, `/admin/google/login` returns 503 or a signed-in allowlisted account receives 401 on `/api/admin/me`. That means `STAFF_TOKEN` or the Google variables were disturbed. Put the previous host values back and redeploy the previous image.

---

## Phase 2 final implementation sequence

Public ingest check, 18 November 2026, is already done. `POST https://www.shreemaruthitravels.com/api/v1/bookings/ingest` with `{"bookings":[]}` and no key returned **401**. The same body with `Host: 127.0.0.1` and `X-Forwarded-For: 127.0.0.1` did not reach Flask. `X-Forwarded-For: 127.0.0.1` alone, and `X-Forwarded-Host: 127.0.0.1` plus `X-Forwarded-For: 127.0.0.1`, both returned **401**. The loopback bypass is not reachable from the public internet. It is still removed so a future proxy change cannot open it. A missing ingest key does not stop the container. Those ingest routes return HTTP 503 until a key is set. When a key is set, OCR keeps publishing with `X-Ingest-Key`.

No application code is edited until this sequence is explicitly approved. Host secrets are not generated or changed by the implementation step. If `STAFF_TOKEN`, `RAC_JWT_SECRET`, or `RAC_INGEST_KEY` is missing on the host, stop and report that name. Do not invent a value in git.

### Preserved, with no edits

- `staff_auth.google_authorize_url`, `google_exchange`, `issue_token`, `role_for`, `staff_emails`, `od_emails`
- `app.py` `admin_google_login`, `admin_google_callback`, `_set_staff_cookie`, `admin_local_login`, `_is_loopback`
- `STAFF_EMAILS`, `OD_EMAILS`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `backend/wa_bridge/server.js` and `backend/wa_bridge/auth/`
- `zoho_sheet.py`, `zoho_workdrive.py`
- `tools/wa_booking_ingest/ocr_provider.py`, parser, validator, and `publisher.py` header `X-Ingest-Key`
- Excel upload routes and dispatch assignment, reassign, unassign, and message routes in `rac_api.py`
- `rac_data.json`, SQLite files, and Zoho rows

### Step 1. Signing secrets

`backend/staff_auth.py`

- Replace the `STAFF_TOKEN = os.environ.get(...) or <constant>` line with a reader that strips `STAFF_TOKEN` and raises `RuntimeError` if it is missing or shorter than 32 characters. The error names the variable and does not include a sample value.
- Keep `_SERIALIZER = URLSafeTimedSerializer(STAFF_TOKEN, salt='smt-staff-v2')`.
- Keep `read_token()` rejecting a cookie that equals the raw secret.
- Do not change `issue_token()` or the allowlists.

`backend/rac_api.py`

- Build `TOKEN` only from `RAC_JWT_SECRET`, stripped, minimum 32 characters, or raise `RuntimeError`. Remove the fallback to `STAFF_TOKEN` and the hardcoded constant.
- Tests and local runs must set both names in the process environment before import. They must not read the developer `.env` into the test log.

Deploy risk: if the host value is already set, existing Google cookies keep working. If the host value is empty, the new process will not boot. That is safer than starting with a known signing key. Rollback is the previous image, which still has the fallback.

### Step 2. Remove the password login

`backend/rac_api.py`

- Delete `RAC_PASSWORD` and its environment read.
- `login()` returns HTTP 410 and the same style of message as `admin_login()`: dispatch uses the SMT Google sign-in. It does not read a password and does not return a token.
- `staff_session()` returns 401 when `staff_auth.current_staff()` is missing. When it is present, the user object uses that email and role. It does not copy the old password-account identity.
- `_auth_user()` stays: bearer token signed by `TOKEN`, then the staff cookie.

`rac/frontend/src/App.jsx`

- Remove `login()`’s `POST /auth/login` call and the email/password fields in `LoginPage`, including the pre-filled local admin email.
- Keep `AuthProvider`. A staff cookie still causes `GET /api/v1/auth/staff` to store the returned bearer token.
- The signed-out screen tells the operator to sign in at `/admin` with Google. No password is shown.

`rac/backend/src/server.js` and `rac/backend/db/seed.js`

- Delete the block that creates `admin@dispatch.local` with a password literal, and delete the log line that prints that password.
- If this unused process is started later, it must not invent an admin. Seeding an admin requires a password passed in from the environment at runtime, and that value is not committed.
- This process is not started by `start.sh`. The change does not affect the live site.

Docs and the unused script, so the password is not copied back:

- `rac/README.md`, `rac/REACT_PAGES_SUMMARY.md`, `rac/frontend/PAGES.md`, `rac/.github/copilot-instructions.md`, `rac/test-upload.js`
- `.env.example` comment that currently shows a sample `RAC_PASSWORD`. Replace it with a note that password login is removed. Do not write a replacement secret.

Deploy risk: the dispatch URL no longer shows a password form. Staff who are already signed in with Google still enter through `/auth/staff`. Anonymous visitors were already rejected by `protect_rac_api()`.

### Step 3. Remove the loopback ingest bypass without stopping the site

Approved adjustment: a missing ingest key must not stop gunicorn, the public site, Google login, or the dispatch UI. It only turns OCR publishing off.

`start.sh` does not exit when `RAC_INGEST_KEY`, `WEBSITE_API_KEY`, and `OCR_INGEST_KEY` are all empty. Keep the block that copies one of those names onto the others when at least one is set. Keep `WEBSITE_API_URL=http://127.0.0.1:$PORT/api/v1`. That address is not an auth bypass.

`backend/app.py` `protect_rac_api()` and `backend/rac_api.py` `require_rac_or_ingest()`

- Delete both loopback shortcuts. A loopback caller with no key is not authenticated.
- Do not delete `_is_loopback()`. `admin_local_login()` and `admin_me()` still use it.
- If none of the three ingest key names is set, `POST /api/v1/bookings/ingest` and `GET /api/v1/bookings/ingest/lookup` return HTTP 503 and a short message that OCR publishing is not configured. Do not insert a booking. Do not accept a staff cookie on those two routes as a substitute for the missing key.
- If a key is set, a matching `X-Ingest-Key` is allowed, as today. A missing or wrong key returns HTTP 401, including from loopback. `publisher.py` already sends that header from `WEBSITE_API_KEY`.
- Every other `/api/v1` route still uses the staff cookie. Excel upload, assignment, and WhatsApp send do not use the ingest key.

Deploy risk: with no ingest key, Booking OCR cannot publish and those two routes answer 503. The homepage, `/admin`, and `/admin/dispatch/` still load. With a key, publishing stays on `X-Ingest-Key`. Screenshot reading code is unchanged.

### Step 4. Tests to add and run

No current test file asserts the password login or the loopback bypass. These new tests are part of the same change. Use Flask’s test client. Set `STAFF_TOKEN` and `RAC_JWT_SECRET` in the test process only. Do not print them and do not read `.env`.

| Test | Expected |
| --- | --- |
| Import `staff_auth` with `STAFF_TOKEN` unset | `RuntimeError` naming `STAFF_TOKEN` |
| Import `rac_api` with `RAC_JWT_SECRET` unset | `RuntimeError` naming `RAC_JWT_SECRET` |
| `POST /api/v1/auth/login` | HTTP 410, no token field |
| `GET /api/v1/auth/staff` with no cookie | HTTP 401 |
| `GET /api/v1/auth/staff` with a cookie from `issue_token` for an allowlisted email | HTTP 200, and `_auth_user()` accepts that bearer token |
| App test client with `STAFF_TOKEN` and `RAC_JWT_SECRET` set, and all three ingest key names unset | The client is created. `GET /` is not a 503 from a failed boot. |
| `GET /api/admin/me` with no cookie, ingest keys unset | HTTP 401, which shows the site is up |
| `GET /api/v1/dashboard/summary` with no cookie, ingest keys unset | HTTP 401 |
| `POST /api/v1/bookings/ingest` with `{"bookings":[]}`, no key, ingest keys unset, including Host `127.0.0.1` and remote `127.0.0.1` | HTTP 503, and no booking row is created |
| `GET /api/v1/bookings/ingest/lookup` in that same unset-key process, loopback and non-loopback | HTTP 503 |
| Same lookup after an ingest key is set, no `X-Ingest-Key`, loopback and non-loopback | HTTP 401 |
| Same lookup with a matching `X-Ingest-Key` | Not 401 and not 503 |
| `POST /api/v1/bookings/ingest` with `{"bookings":[]}` and a matching key | HTTP 400, and no booking row is created |
| `POST /admin/local-login` when Google variables are set | HTTP 403 |

Run unchanged after the edit:

- `tools/wa_booking_ingest/tests/test_ocr_provider.py`
- `tools/wa_booking_ingest/tests/test_pipeline.py`
- `tools/wa_booking_ingest/tests/test_parser.py`
- `tools/wa_booking_ingest/tests/test_duplicates.py`

The React form change has no automated browser test in this repo. After deploy, open `/admin/dispatch/` while signed out and confirm there is no password field.

### Step 5. Deploy and rollback

Deploy one commit after the tests pass. Do not change host secret values in that deploy. If `STAFF_TOKEN` or `RAC_JWT_SECRET` is missing, stop before deploy. A missing `RAC_INGEST_KEY` does not stop the deploy. The site comes up, and OCR publish stays at HTTP 503 until a key is added and the container is restarted.

After deploy:

- `/admin/google/login` still redirects to Google.
- A signed-in allowlisted account gets HTTP 200 from `/api/admin/me`.
- `/admin/dispatch/` has no password form and opens for that account.
- WhatsApp status still loads.
- `GET /` and `/admin` respond. They must not be down because the ingest key is empty.
- If an ingest key is configured, lookup from inside the container with `X-Ingest-Key` is not 401 and not 503. Do not print the key. Do not upload a real screenshot as the test.
- If no ingest key is configured, those two ingest routes return 503 and the rest of the site still answers.

Rollback is `git revert` of that commit and a redeploy. Do not force-push. If `STAFF_TOKEN` was left unchanged, current Google cookies work again on the old image. If OCR publish is 503, set `RAC_INGEST_KEY` and restart. Do not open ingest without a key, and do not treat loopback as authentication.

Stop if `/admin/google/login` returns 503 or `/api/admin/me` returns 401 for a known allowlisted session. Redeploy the previous image. Do not rotate Google, Zoho, or Gemini values to “fix” that.

### Approval gate

Implementation starts only after an explicit approval of this adjusted sequence. Steps 1, 2, and 3 ship together. Step 3 must not make container startup depend on `RAC_INGEST_KEY`.
