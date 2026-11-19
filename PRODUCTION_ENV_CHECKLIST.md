# Production environment-variable checklist

Date: 18 November 2026. Read-only. No code, environment file, hosting setting, or git commit was changed. No secret values were read or written.

This checklist is for the process that `start.sh` starts: WhatsApp bridge, OCR worker, and gunicorn `backend.app:app`. The Node service in `rac/backend` is not that process.

## Where the variables have to be set

**Verified.** The container entrypoint is `start.sh`. It inherits the process environment. Flask also calls `load_dotenv` on `.env` files next to the app. Those files are gitignored and are not copied as secrets by the Dockerfile. A value that exists only on a developer PC is not on the server.

**Verified.** The root `Dockerfile` says AIC App Hosting clones this GitHub repo and builds that file. `start.sh` calls the same container an AIC container. The deploy log that rebuilt this image used that Dockerfile (`ARG APP=...`).

**Verified, not proof of the live dashboard.** `fly.toml` names an app `smt-website` and has no `[env]` block. `render.yaml` names a Render service and has no env block. `STAFF_AND_OD.md` tells an operator to paste Google keys on Render or AIC. A public response from `www.shreemaruthitravels.com` included `Server: Caddy` and `Server: gunicorn`.

**Not found.** No deploy file names Hostinger.

**Needs confirmation.** Which dashboard currently injects the environment for the live container. Do not guess. Set the names below in the secret store of the host that actually runs this image. A git push does not set them. Confirm only that each name is present and non-empty. Do not display the values.

The unused `docker-compose.yml` stack is not this checklist. Its database and JWT names belong to `rac/backend`, which production `start.sh` does not start.

---

## 1. Secrets this cleanup depends on

### `STAFF_TOKEN`

- **Purpose.** Signs the `smt_staff` cookie and the Google OAuth `state` value. Read in `backend/staff_auth.py` when `_SERIALIZER` is created.
- **Fallback today.** If the variable is empty, the code uses a constant compiled into `staff_auth.py`. Anyone with the source can forge a staff cookie.
- **Required for the cleanup.** Yes. The cleanup refuses to boot when it is missing. If the host already has a long value, keep it.
- **Changing it.** Invalidates every current staff cookie and every in-flight Google sign-in. Staff must open `/admin` and sign in with Google again. It does not unlink WhatsApp, Zoho, or OCR by itself.

### `RAC_JWT_SECRET`

- **Purpose.** Signs the dispatch bearer token returned by `GET /api/v1/auth/staff`. Read in `backend/rac_api.py` for `TOKEN`.
- **Fallback today.** If empty, the signer uses `STAFF_TOKEN`. If that is also empty, it uses a different constant in `rac_api.py`. One leaked fallback then signs both the cookie and the dispatch token.
- **Required for the cleanup.** Yes. It must be set, and it must be different from `STAFF_TOKEN`. Do not leave the fallback chain in place.
- **Changing it.** Invalidates bearer tokens already stored by the dispatch page. The page can still use a valid staff cookie to ask for a new token. If `STAFF_TOKEN` is unchanged, Google login sessions stay valid. If both change, staff sign in again.

### `RAC_INGEST_KEY`

- **Purpose.** Shared secret for `POST /api/v1/bookings/ingest` and `GET /api/v1/bookings/ingest/lookup`. The OCR worker does not have a staff cookie. `publisher.py` sends it as `X-Ingest-Key` under the name `WEBSITE_API_KEY`.
- **Fallback today.** No hardcoded key. If `RAC_INGEST_KEY`, `WEBSITE_API_KEY`, and `OCR_INGEST_KEY` are all empty, key auth fails. `start.sh` copies whichever one of those three is set onto the empty ones at startup. A loopback request can still pass today even with no key. The public check on 18 November 2026 did not find that bypass reachable from the internet.
- **Required for the cleanup.** Yes, before the loopback bypass is removed. One value is enough. `start.sh` will copy it.
- **Changing it.** Does not log staff out. OCR publish fails with 401 until the container is restarted so the worker and gunicorn see the same new value. In-flight uploads during the restart fail and can be uploaded again.

Set only one of these three, unless you already have a reason to keep them different. They are the same secret in the current `start.sh`.

| Name | Who reads it |
| --- | --- |
| `RAC_INGEST_KEY` | Flask `protect_rac_api()` and `_ingest_key_ok()` |
| `WEBSITE_API_KEY` | OCR worker `config.py`, then the `X-Ingest-Key` header |
| `OCR_INGEST_KEY` | Flask, as another accepted key; also sent by Flask when it calls the OCR worker |

---

## 2. Google login

Both must be set or `google_configured()` is false and `/admin/google/login` returns 503. There is no fallback client id or secret in code.

| Name | Purpose | Fallback | Changing it |
| --- | --- | --- | --- |
| `GOOGLE_CLIENT_ID` | OAuth client. Sent to Google from `google_authorize_url` and `google_exchange`. | None | Login breaks until the Google Cloud client and the host value match. Existing staff cookies stay valid until they expire or `STAFF_TOKEN` changes. |
| `GOOGLE_CLIENT_SECRET` | Exchanges the Google code for the user email. | None | Same. A wrong secret makes new sign-ins fail. It does not revoke cookies already issued. |

Allowlists, not signing secrets. If the host variable is empty, the code uses the emails written in `staff_auth.py`.

| Name | Purpose | Changing it |
| --- | --- | --- |
| `STAFF_EMAILS` | Who may sign in | Removing an address blocks that person on the next request. Adding one does not log others out. |
| `OD_EMAILS` | Who may open the OD workspace | Same, for the OD role only |
| `STAFF_EXTRA_EMAILS` | Extra staff, unioned with `STAFF_EMAILS` | Same |

Do not rotate the Google client as part of the signing-secret cleanup.

---

## 3. Zoho

Used by the live Flask process for inquiries, RAC sheet mirror, and WorkDrive. Not used by the WhatsApp bridge.

| Name | Purpose | Fallback |
| --- | --- | --- |
| `ZOHO_CLIENT_ID` | OAuth client for Sheet and WorkDrive | None. Empty disables the API call. |
| `ZOHO_CLIENT_SECRET` | OAuth client secret | None |
| `ZOHO_REFRESH_TOKEN` | Sheet refresh token | If empty, `zoho_sheet.py` reads `backend/.zoho_refresh_token` from the container disk. That file is gitignored. A new container without the file and without the variable loses Sheet. |
| `ZOHO_SPREADSHEET_ID` | Which workbook | A constant in `zoho_sheet.py` if unset |
| `WORKDRIVE_REFRESH_TOKEN` | WorkDrive refresh token | If empty, `zoho_workdrive.py` reads `backend/.workdrive_refresh_token` from disk. Same durability rule as the Sheet file. |
| `WORKDRIVE_FOLDER_ID` | WorkDrive folder | A constant in `zoho_workdrive.py` if unset |
| `ZOHO_REDIRECT_URI` | Optional OAuth redirect | Empty uses the code’s own default path |
| `ZOHO_INQUIRY_SHEET` | Optional worksheet name | Empty uses the code’s default sheet name |

The OCR worker also accepts `ZOHO_WORKDRIVE_REFRESH_TOKEN`, `ZOHO_WORKDRIVE_CLIENT_ID`, and `ZOHO_WORKDRIVE_CLIENT_SECRET`, and falls back to `WORKDRIVE_REFRESH_TOKEN`, `ZOHO_CLIENT_ID`, and `ZOHO_CLIENT_SECRET`. WorkDrive polling stays off unless `ZOHO_WORKDRIVE_ENABLED` is true. `start.sh` defaults that to off.

**Changing a Zoho secret.** The old refresh token stops working as soon as the process reads the new one. Sheet export and WorkDrive file listing fail until the new token is valid. Bookings already in `rac_data.json` stay. Staff cookies and WhatsApp are unaffected. Do not rotate Zoho tokens in the security-cleanup deploy.

---

## 4. WhatsApp bridge

The live bridge is `backend/wa_bridge/server.js`, started by `start.sh`. It has no API key.

| Name | Purpose | Fallback |
| --- | --- | --- |
| `WA_BRIDGE_PORT` | Listen port | `3100` |
| `WA_BRIDGE_URL` | Where Flask sends assignment texts | `http://127.0.0.1:3100` |
| `WA_AUTH_DIR` | Baileys session directory | `backend/wa_bridge/auth` |

The login is the files in that directory, not an environment variable. They are gitignored. The Dockerfile does not copy them.

**Changing these.** Changing `WA_BRIDGE_URL` without a matching bridge makes assignment messages fail. It does not log staff out. Replacing or wiping `WA_AUTH_DIR` unlinks WhatsApp. The next start shows a new QR. A rebuild that does not keep the container disk has the same effect. Whether the live host keeps that disk across deploys is **needs confirmation**. No volume is declared in `fly.toml` or the root `Dockerfile`.

There is no WhatsApp token to generate for this bridge.

The Node app’s Twilio and Gupshup variables are not read by this bridge. Ignore them for this deployment.

---

## 5. Other secrets the same process can see

Not part of the signing-secret change. Listed so they are not deleted by accident.

| Name | Purpose | Fallback | Changing it |
| --- | --- | --- | --- |
| `GEMINI_API_KEY` or `GOOGLE_AI_API_KEY` | OCR vision reader | Empty skips Gemini and uses OCR.space or Tesseract | New key is used on the next upload. Old quota stays on the old Google project. |
| `OCR_SPACE_API_KEY` | Optional OCR.space | Empty skips that provider | Same, next upload |
| `SMTP_PASSWORD`, `SMTP_USER`, `SMTP_SERVER`, `SMTP_PORT` | Inquiry email | Empty logs the inquiry instead of sending mail | Mail fails until the new password is accepted. Bookings are unaffected. |
| `LEDGER_ZOHO_CLIENT_ID`, `LEDGER_ZOHO_CLIENT_SECRET`, `LEDGER_ZOHO_REFRESH_TOKEN`, `LEDGER_SESSION_SECRET`, `LEDGER_PASSWORD` | OD workspace mounted inside the same Flask process | Ledger session secret falls back to a constant in `od_workspace` when unset | Can lock the OD workspace. Do not change them in this cleanup. |

`RAC_EMAIL` and `RAC_PASSWORD` exist today and fall back to values in `rac_api.py`. The cleanup removes that login. After it ships, delete those two names from the host so an old password cannot be switched back on. They are not required for Google login.

---

## 6. How to generate a secret without putting it in this report

Do this on the operator’s machine. Paste the result only into the host secret field. Do not commit it, do not put it in chat, and do not write it into `.env.example` or the Dockerfile.

Generate three different values: one for `STAFF_TOKEN`, one for `RAC_JWT_SECRET`, one for `RAC_INGEST_KEY`.

Use a cryptographic generator, at least 32 bytes:

- `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- or `openssl rand -base64 32`

Run it once per variable. Do not reuse one string for two names. Do not use a word, a date, or the fallback strings that are already in the source.

If the host already has a long `STAFF_TOKEN` or `RAC_JWT_SECRET`, do not generate a replacement. Keeping the current value avoids signing everyone out.

---

## 7. Readiness checklist

Mark present or missing in the live host’s secret store. Do not copy the values into the mark.

- [ ] `STAFF_TOKEN` is set and at least 32 bytes. If it is already set, leave the value.
- [ ] `RAC_JWT_SECRET` is set, at least 32 bytes, and different from `STAFF_TOKEN`.
- [ ] `RAC_INGEST_KEY` or `WEBSITE_API_KEY` is set. `start.sh` copies one onto the other at startup.
- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set and were not edited for this work.
- [ ] `STAFF_EMAILS` and `OD_EMAILS` are unchanged.
- [ ] Zoho and WorkDrive token names are unchanged.
- [ ] WhatsApp auth directory is not in git and is not deleted by this work.
- [ ] `GEMINI_API_KEY` is unchanged.
- [ ] `RAC_PASSWORD` will be removed from the host only after the password login code is removed.

Deploy the cleanup only after the first three marks are true. A missing `STAFF_TOKEN` or `RAC_JWT_SECRET` will stop the site from booting once the fallback code is gone. A missing ingest key will make Booking OCR publish return 401 once the loopback bypass is gone.
