# SMT staff login and OD ledger

This is the working note for how Shree Maruthi Travels staff sign in, who can see what, and where secrets live.

PIN `5999` is removed. Staff open `/admin` and click **Continue with Google**.

## What we built

1. **Public website** — quotes, fleet, contact. No Google login.
2. **Staff portal** (`/admin`) — inquiries, cabs, RAC, invoices, trips. Four Gmails only.
3. **OD workspace** (`/admin/workspace`) — Bank of Baroda overdraft ledger (copied from repo `abhishekgowdasmt-ai/private-workspace` into folder `od_workspace/`). Two Gmails only.

## Who can sign in

Google Cloud test users and SMT allowlists must match.

| Gmail | Staff portal | OD ledger |
|---|---|---|
| `abhishekgowdasmt@gmail.com` | yes | yes |
| `shreemaruthitravels5999@gmail.com` | yes | yes |
| `veeruashwini01@gmail.com` | yes | no |
| `bhaskarbhaskarreddy9005@gmail.com` | yes | no |

Anyone else who uses Google is rejected (`login_error=not_allowed`).

Allowlists in code (`backend/staff_auth.py`) and env:

- `STAFF_EMAILS` — all four above
- `OD_EMAILS` — Abhishek + company Gmail
- Extra staff later: `STAFF_EXTRA_EMAILS`

## What we created in Google Cloud

Project: **SMT Portal** (`smt-portal-508712`)  
Console: [Google Auth Platform](https://console.cloud.google.com/auth/overview?project=smt-portal-508712)

| Item | Value |
|---|---|
| App name on the consent screen | Shree Maruthi Travels |
| User type | External (Testing) |
| Scopes | `openid`, `userinfo.email`, `userinfo.profile` |
| Client type | Web application |
| Client ID | `874227112119-0lvnfe0s989sd4vq1r27mvrracjbnl7k.apps.googleusercontent.com` |
| Client secret | **not stored in git** — only in local `.env` and the host env |

Redirect URIs (must match exactly):

- `http://localhost:5000/admin/google/callback`
- `https://www.shreemaruthitravels.com/admin/google/callback`

JavaScript origins:

- `http://localhost:5000`
- `https://www.shreemaruthitravels.com`

If the live host is still a Render/AIC hostname, add that origin and `/admin/google/callback` on the same Google client, or Google will show `redirect_uri_mismatch`.

An earlier client was created by mistake in project **attendance-app**. Delete that Web client in attendance-app so the old secret is unused.

Google OAuth for this login is **free**. Do not start a Google Cloud billing trial for it.

## Where secrets are saved

| Secret | Saved in | Never put in |
|---|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | local `.env` (gitignored) and Render/AIC env | GitHub, chat screenshots of `.env` |
| RAC Zoho (`ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, `ZOHO_SPREADSHEET_ID`) | same | GitHub |
| OD ledger Zoho (`LEDGER_ZOHO_*`) | same | GitHub |

Local file (this PC only):

`shree-maruthi-travels-main/shree-maruthi-travels-main/.env`

Template with empty values (safe to commit):

`shree-maruthi-travels-main/shree-maruthi-travels-main/.env.example`

Git ignores `.env`. Production copies of the same keys go on **Render → Environment** (and AIC later). The website will not Google-login on Render until those two `GOOGLE_*` keys are pasted there.

## Two different Zoho sheets

Do not paste the OD refresh token into `ZOHO_REFRESH_TOKEN`. That would break RAC.

| Use | Env prefix | Sheet id env |
|---|---|---|
| Website inquiries + RAC dispatch | `ZOHO_*` | `ZOHO_SPREADSHEET_ID` = `wx4flb9932735a31d4f8ba038c6ec4a69c850` |
| OD / BOB ledger | `LEDGER_ZOHO_*` | `LEDGER_ZOHO_RESOURCE_ID` |

Same Zoho API console client can be reused. Refresh tokens and sheet ids are different.

The old ledger passphrase (`LEDGER_PASSWORD`) is not used. Google + `OD_EMAILS` is the lock.

## How login works in the app

1. Staff open `/admin`.
2. Browser goes to `/admin/google/login`, then Google, then `/admin/google/callback`.
3. Server checks the Gmail against `STAFF_EMAILS`.
4. Cookie `smt_staff` is set (12 hours). Role is `od` or `staff`.
5. OD nav **OD workspace** is shown only if role is `od`.
6. `/admin/workspace` is the ledger UI. Veeru and Bhaskar are redirected away.

Code:

- `backend/staff_auth.py` — Google exchange + allowlists
- `backend/app.py` — `/admin/google/login`, `/admin/google/callback`, mounts ledger
- `od_workspace/` — ledger app
- `frontend/templates/admin.html` — Google button

## What you still add on Render (or AIC)

After deploy, add at least:

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

plus the existing RAC `ZOHO_*` keys, and the `LEDGER_ZOHO_*` keys from the AIC ledger screenshot (mapped to the `LEDGER_` names). Copy values from local `.env`. Leave `GOOGLE_CLIENT_SECRET` empty in git.

## Local test

```bat
cd shree-maruthi-travels-main\shree-maruthi-travels-main\backend
python app.py
```

Open http://localhost:5000/admin → Continue with Google → pick a test Gmail.
