# Shree Maruthi Travels — Phase 1 project audit

Date: 18 November 2026. Scope: this repository only. No application code, deployment config, or data was changed for this audit.

Labels used below:

- **Verified** — read from this repository or from a live HTTP response header already observed.
- **Assumption** — a reasonable reading that the code does not prove.
- **Needs confirmation** — cannot be decided from this repository.

No secret values, tokens, or passwords are written here.

---

## 1. Existing project architecture

This is one Git repository with two different products living side by side, plus a private finance tool that is not part of transport operations.

**Verified.** The running website is a Python Flask application. It serves the public marketing site, the staff admin, and the RAC dispatch UI. The RAC React app is built into static files and served by Flask at `/admin/dispatch/`. Its API calls go to the same Flask process at `/api/v1`.

**Verified.** A second RAC backend exists at `rac/backend`. It is an Express and Sequelize service aimed at PostgreSQL. The production image built by the root `Dockerfile` does not start it. The React app’s production build sets `VITE_API_URL=/api/v1`, and Flask owns that prefix. The deployed dispatch screen is therefore designed to use the Flask RAC API, not the Node service.

**Verified.** OCR and the WhatsApp bridge are extra processes in the same container, started by `start.sh`. They are not separate deployed services.

**Verified.** `od_workspace` is a private overdraft ledger that stores its books in Zoho Sheet. It is not a transport module.

```text
Browser
  public site, staff admin     -> Flask (gunicorn) -> SQLite database.db
  /admin/dispatch React SPA    -> Flask /api/v1    -> rac_data.json + optional Zoho Sheet
  Booking OCR page             -> Flask proxy      -> OCR worker :8787 -> ingest SQLite
  WhatsApp link page           -> Flask            -> wa_bridge :3100 (Baileys, loopback)
```

There is no driver Android app and no client portal in this repository.

---

## 2. Repository structure

Git root: `smt-invoice-generator`. The application that deploys is nested twice:

`shree-maruthi-travels-main/shree-maruthi-travels-main/`

| Path | What it is | Status |
| --- | --- | --- |
| `backend/app.py` | Flask website, staff admin, SQLite, public APIs | Live |
| `backend/rac_api.py` | RAC blueprint mounted at `/api/v1` | Live |
| `backend/rac_store.py` | JSON file plus optional Zoho Sheet | Live RAC store |
| `backend/staff_auth.py` | Google staff cookie and allowlists | Live |
| `backend/zoho_sheet.py`, `backend/zoho_workdrive.py` | Zoho India OAuth | Live when configured |
| `backend/wa_bridge/` | Baileys WhatsApp linker, loopback only | Live in `start.sh` |
| `frontend/templates`, `frontend/static` | Public site and staff admin (Jinja) | Live |
| `rac/frontend` | React dispatch UI, Vite base `/admin/dispatch/` | Live after the image build |
| `rac/backend` | Express, Sequelize, PostgreSQL, Redis, Bull | Not in the production image |
| `tools/wa_booking_ingest` | OCR worker, SQLite, publisher into `/api/v1` | Live in `start.sh` |
| `tools/invoices`, `tools/trips` | Invoice HTML and trip-sheet PDF helpers | Used by staff admin routes |
| `od_workspace` | Private overdraft ledger | Present, not part of RAC |
| `Dockerfile`, `start.sh`, `fly.toml`, `render.yaml` | Deploy definitions | See section 8 |
| Repository root `*.pdf` | Customer invoice PDFs | Present in the tree |

Generated folders (`node_modules`, `dist`, Python caches, virtualenvs) were not treated as source.

**Needs confirmation.** The task mentioned a Flutter Android starter in a separate local folder. The only Flutter tree next to this repo is the Flutter SDK itself (`flutter_windows_3.50.0-stable`). No driver application `pubspec.yaml` was found outside that SDK.

---

## 3. Backend and frontend relationships

### Public website and staff admin

**Verified.** Flask renders Jinja pages: home, services, fleet, about, contact, and `/admin`. Staff admin covers inquiries, cabs, drivers, companies, trips, invoices, Zoho Sheet, and Zoho WorkDrive. Those records live in `backend/database.db`.

### RAC dispatch UI

**Verified.** `rac/frontend/src/App.jsx` uses `basename="/admin/dispatch"` and these screens:

- Dashboard, Excel upload, Booking OCR, bookings, booking detail
- Drivers, assignment, WhatsApp messages, insights, WhatsApp link

`rac/frontend/src/services/api.js` calls `/api/v1` unless `VITE_API_URL` overrides it. The Docker build sets `VITE_API_URL=/api/v1`.

### Which backend the deployed RAC frontend uses

**Verified.** Flask registers `rac_bp` at `/api/v1` in `backend/app.py`. The production container runs gunicorn on `backend.app:app`. The Node server in `rac/backend/src/server.js` also exposes `/api/v1/...`, but only when that process is started. `start.sh` does not start it.

`docker-compose.yml` is a different layout: it wires the website to `http://rac-backend:3000` and a Postgres service. That compose file is not what `start.sh` runs. Treating compose as production would point the UI at the wrong backend.

### Duplicate driver and booking models

**Verified.** Two driver lists exist and are not the same data:

- SQLite `drivers` for the public-site admin (integer ids, cab documents, companies).
- `rac_data.json` collection `drivers` for dispatch (string ids, WhatsApp number, assignment counts).

Bookings created by OCR or Excel upload go into the JSON store. They are not inserted into the SQLite `trips` table. A client portal or GPS feature built on only one of these stores would not see the other.

---

## 4. Existing API inventory

### Flask public and staff APIs

**Verified** from `backend/app.py`. Staff routes require the staff cookie. Examples:

- `POST /api/inquiries`, `GET /api/inquiries`, inquiry status
- `GET /api/stats`, `POST /api/chat`
- `GET/POST /api/places-autocomplete`
- Admin cabs, cab documents, drivers, companies, company cab assignments
- Admin trips, trip optimize, simulate tick, SOS and resolve SOS
- `POST /api/admin/login` returns HTTP 410. PIN login is removed.
- `POST /admin/local-login` only when Google is not configured and the request is loopback
- Google login at `/admin/google/login` and `/admin/google/callback`

### Flask RAC API (`/api/v1`)

**Verified** from `backend/rac_api.py`. All of these sit behind `protect_rac_api`.

| Area | Methods and paths |
| --- | --- |
| Session | `GET /auth/staff`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/user` |
| Dashboard | `GET /dashboard/summary`, `GET /dashboard/insights` |
| Drivers | `GET/POST /drivers`, `GET/PUT /drivers/<id>`, `PATCH /drivers/<id>/status` |
| Bookings | `GET /bookings`, `GET /bookings/<id>`, `PATCH .../status`, `POST .../unassign`, `PATCH .../payment`, `PATCH /bookings/payments/bulk` |
| Ingest | `POST /bookings/ingest`, `GET /bookings/ingest/lookup` |
| OCR | `POST /bookings/ocr-upload`, `GET /bookings/ocr-status`, review and image routes |
| Excel | `GET /uploads/template.xlsx`, `POST /uploads/excel`, history and batch status |
| Assignment | `POST /assignments`, `GET /assignments/<id>`, `POST .../resend-message` |
| Messages | `GET /messages`, `GET /messages/<id>` |
| Zoho WorkDrive | `POST /integrations/zoho/workdrive/webhook` (proxied to the OCR worker) |

Assignment, unassign, and cancel send WhatsApp text through the loopback bridge. There is no accept or reject API, no trip-start API, and no GPS API.

### Node RAC API (not deployed by the current image)

**Verified.** `rac/backend/src/server.js` mounts auth, dashboard, uploads, bookings, drivers, assignments, messages, and WhatsApp under `/api/v1`, plus `GET /health`. It seeds a local admin user on startup. This is a prototype of the same dispatch idea on PostgreSQL. It is not the API the live React bundle calls.

### OCR worker

**Verified.** `tools/wa_booking_ingest` listens on `127.0.0.1:8787` inside the container. Flask proxies upload and status to it. The worker publishes bookings back to `WEBSITE_API_URL`. `start.sh` forces that URL to `http://127.0.0.1:$PORT/api/v1`.

### WhatsApp bridge

**Verified.** `backend/wa_bridge/server.js` listens on `127.0.0.1` and exposes `GET /status` and `POST /send` only. It is not on the public port.

---

## 5. Authentication architecture

**Verified.** Staff identity is a Google sign-in for an allowlist in `backend/staff_auth.py`. The cookie is `smt_staff` (HttpOnly, SameSite Lax, 12 hours). Roles in code are `od` and `staff`. OD can open the overdraft workspace. There is no driver role and no client role.

**Verified.** If Google client id and secret are unset, `POST /admin/local-login` works only from loopback. Production with Google configured does not use that form.

**Verified.** The React app still has an email and password form. `POST /api/v1/auth/login` compares that password with `RAC_EMAIL` and `RAC_PASSWORD`. Defaults for both are committed in `rac_api.py`. `protect_rac_api` still requires a staff cookie before that route runs, so the form does not bypass Google for an anonymous visitor. The password check remains a second, weaker credential.

**Verified.** `GET /api/v1/auth/staff` issues a dispatch token for the signed-in staff member. The React app stores that token in `localStorage`. Logout on the client clears storage only. It does not clear the staff cookie.

**Verified.** Ingest routes accept `X-Ingest-Key` when it matches `RAC_INGEST_KEY`, `WEBSITE_API_KEY`, or `OCR_INGEST_KEY`. They also allow the request when both the Host header and `remote_addr` are loopback.

**Needs confirmation.** If the public proxy connects to gunicorn from `127.0.0.1`, every visitor would look like loopback and the ingest bypass would be public. The code intends this bypass only for the OCR process in the same container. The proxy’s source address has not been measured.

---

## 6. Data storage architecture

Four stores, none of them a shared transactional database for owner, driver, and client apps.

| Store | File | Contents | Durability |
| --- | --- | --- | --- |
| Website SQLite | `backend/database.db` | Inquiries, chat logs, cabs, cab documents, website drivers, companies, company cabs, trips, passengers, safety alerts | Local file. Gitignored. Lost when the container disk is replaced unless a volume is mounted. |
| RAC JSON | `backend/rac_data.json` | drivers, bookings, assignments, uploads, messages | Local file plus a copy to Zoho Sheet worksheets when Zoho is connected. Gitignored. Single-process lock. |
| OCR SQLite | `tools/wa_booking_ingest/data/ingest.sqlite3` | ingest records, review queue, jobs, dedupe of images and booking ids | Container disk. Gitignored. |
| Zoho Sheet | India API via `zoho_sheet.py` | Inquiries, and RAC worksheets `RAC_Drivers`, `RAC_Bookings`, `RAC_Assignments`, `RAC_Uploads`, `RAC_Messages` | External. Optional. |
| Zoho WorkDrive | `zoho_workdrive.py` | Screenshot files and a webhook into OCR | External. Optional. |

**Verified.** `rac_store.py` keeps the JSON document in memory, writes the whole file on change, and best-effort mirrors rows to Zoho. It is not safe for multiple gunicorn workers. `start.sh` uses one worker and four threads, so threads share that memory. Two containers would each have their own file and would diverge.

**Verified.** PostgreSQL appears only in `docker-compose.yml` and `rac/backend` (Sequelize, database name `dispatch_db`). The live Flask path does not connect to it.

**Verified.** Redis and Bull are dependencies of the Node prototype. They are not used by Flask.

**Assumption.** Zoho Sheet is a backup and a spreadsheet view, not a database that can enforce one booking row, one assignment, and one driver location at a time. GPS and concurrent accept or reject need a transactional store. PostgreSQL is the right candidate. Moving there is a migration, not a library swap, because booking identity, driver identity, and trip identity differ between SQLite and the JSON document.

---

## 7. External integrations

### Zoho

**Verified.** OAuth refresh tokens are stored in files named by `zoho_sheet.py` and `zoho_workdrive.py`, using the India accounts host. Sheet receives inquiries and RAC rows. WorkDrive lists files and can notify the OCR webhook. Tokens are gitignored. Whether production currently has a valid refresh token is **needs confirmation**.

### WhatsApp

**Verified.** Production send path is Baileys in `backend/wa_bridge`, account data under `backend/wa_bridge/auth/` (gitignored). Flask calls it on loopback. Assignment, reassignment, unassign, and cancel build a text message. The driver cannot accept or reject in the app. There is no delivery receipt stored as a business event beyond a message row.

**Verified.** `rac/backend` still contains a `whatsapp-web.js` service. That code is not on the live path.

**Verified.** The OCR package can watch a WhatsApp group. `start.sh` sets `WHATSAPP_WATCHER_ENABLED` default `0`. Group watching is off unless the host turns it on.

### OCR

**Verified.** Provider order in `tools/wa_booking_ingest/ocr_provider.py` is Gemini, then OCR.space if a key exists, then Tesseract. Tesseract is installed in the image. Gemini is called only when `GEMINI_API_KEY` is set. The free tier quota is per Google project, not per key, and a 429 falls through to the next reader. Screenshots that already contain a booking id can be published from local OCR. Screenshots with no id column need a reader that can see a date and a time, then the server builds an id from place, date, time, and cab.

### Maps

**Verified.** The public site has a places autocomplete proxy. Trip “optimize” and “simulate tick” in `app.py` are staff admin simulations over the SQLite trip table. They are not live fleet GPS.

### Invoices

**Verified.** `tools/invoices` and `tools/trips` generate documents from staff uploads. Customer invoice PDFs are also sitting in the repository root. Those files are business records and should not stay in git.

---

## 8. Deployment architecture

**Verified.** `start.sh` starts, in one container:

1. `node backend/wa_bridge/server.js` on loopback port 3100
2. `python -m tools.wa_booking_ingest --http` on port 8787
3. `gunicorn` one worker, four threads, `backend.app:app` on `$PORT` (8080 if unset)

The root `Dockerfile` builds the React app with Node, installs the WhatsApp bridge dependencies, installs Tesseract, then copies the Flask app. `render.yaml` points Render at that Dockerfile and the nested app directory. `fly.toml` names app `smt-website`, region `maa`, internal port 8080, and allows the machine to stop when idle.

**Verified.** A response from `https://www.shreemaruthitravels.com` included both `Server: Caddy` and `Server: gunicorn`.

**Needs confirmation.** Which host is the one that rebuilds from GitHub `main`. The Dockerfile comment says AIC App Hosting. `fly.toml` and `render.yaml` both exist. A push to GitHub does not by itself prove the live machine has rebuilt.

**Verified.** `docker-compose.yml` describes a second, unused stack: website, Postgres, Redis, Node RAC API, and the Vite dev server. Its environment block contains development database and JWT defaults. Do not point production at that file without replacing those defaults.

---

## 9. Missing functionality

Compared with the three-app platform. These are absent, not partially hidden.

| Module | Present now | Missing |
| --- | --- | --- |
| RAC booking and dispatch | Excel upload, OCR, list, detail, assign, reassign, unassign, WhatsApp text, payment flags | Driver accept and reject, trip start and end, GPS, duty-only tracking, branch on a booking |
| ETS | Company and cab assignment rows in SQLite, an “ets” label in admin navigation | Clients as login users, employees, routes, shifts, rosters, attendance, ETS billing |
| Owner dashboard | Public-site admin plus RAC dispatch | One overview, Bengaluru and Hyderabad as real branches, live fleet, expenses, role admin beyond two staff levels |
| Driver Android app | None in this repo | OTP, duty list, accept or reject, start and end, GPS, earnings |
| Client portal | Public marketing site and inquiry form | Client login, own bookings, live vehicle, invoices for that client, complaints |
| Shared database | Four stores | One transactional database used by every app |
| GPS | The word “gps” in the public chat replies and cab accessory text | No position table, no duty session, no map |

---

## 10. Security risks

Ordered by what should be fixed before multi-user or GPS work. No secret values are repeated.

1. **Default RAC password in source.** `backend/rac_api.py` and the Node seed both ship a local admin email and password. The React login form still posts them. Staff-cookie protection limits anonymous use, but the credential should be removed, not relied on.
2. **Development secrets in `docker-compose.yml`.** Database password and JWT secret are committed. They are for the unused Node stack. They must be rotated if that stack was ever exposed.
3. **Signing secrets fall back to constants** in `staff_auth.py` and `rac_api.py` when environment variables are empty. Production must set those variables. An empty secret means anyone who can read the source can forge a staff or dispatch token.
4. **Dispatch token in `localStorage`.** Any script on the dispatch origin can read it. The staff cookie is HttpOnly, which is the better store.
5. **Loopback ingest bypass.** Ingest routes skip the staff cookie for loopback. Safe only if the public proxy is not seen as `127.0.0.1`. Needs confirmation on the live host.
6. **WhatsApp session files on disk.** `backend/wa_bridge/auth/` is gitignored, which is correct. A copy of that directory is a full WhatsApp login. It must stay out of images, backups that are widely shared, and git.
7. **Zoho refresh-token files** are gitignored and are equivalent to account access. Same rule.
8. **Single JSON file as the booking database.** A crash mid-write, or two containers, can drop or duplicate bookings. Duplicate booking ids are checked by the OCR worker, not by a database constraint.
9. **Customer invoice PDFs in the repository root.** They are business documents in a tree that is pushed to GitHub.
10. **OD workspace inside the same app.** A finance ledger shares the process and the staff cookie with transport operations. A staff role bug would expose it. It should stay a separate deployment.
11. **No driver or client authorization model.** GPS added on top of the current staff cookie would either be visible to every staff user or unprotected. Duty-scoped tracking needs its own session and a start and stop record.
12. **CORS allowlist on the Node server** includes the production site, but that server is not the live API. Not a current hole. It becomes one if the Node process is started later without review.

---

## 11. Existing functionality that should be reused

Do not rewrite these.

- Flask staff Google allowlist and the `smt_staff` cookie.
- `rac/frontend` screens for bookings, drivers, assignment, messages, OCR, and Excel upload.
- `backend/rac_api.py` assignment, reassignment, unassign, and the WhatsApp message text.
- `backend/wa_bridge` as the only WhatsApp sender.
- `tools/wa_booking_ingest` parse, validate, dedupe, and the “place + date + time + cab” id rule when the screenshot has no id.
- Zoho Sheet and WorkDrive clients, as an export and file inbox, not as the future system of record.
- Public site templates and the inquiry form.
- Invoice and trip-sheet generators.

Leave `rac/backend` in place until a migration decision. It has useful Sequelize model ideas (users, drivers, bookings, assignments, messages) and a dangerous default admin seed. Do not run it beside Flask against a second database.

---

## 12. Recommended target architecture

One PostgreSQL database. One API, evolved from the Flask `/api/v1` already in production. Three clients.

```text
Owner web (existing React dispatch + staff admin)
Driver Android (new, not in this repo)
Client web (new)
        |
        v
Flask API  /api/v1     (keep the current routes working)
        |
        v
PostgreSQL
  branches, users, drivers, vehicles
  bookings, assignments, trip_sessions
  positions (only while a trip_session is open)
  invoices, messages
        |
        +-- Zoho Sheet / WorkDrive  (export and inbound files)
        +-- wa_bridge               (outbound WhatsApp only)
        +-- OCR worker              (writes bookings through the API)
```

Roles: `owner`, `staff`, `driver`, `client`. A driver token can read and update only that driver’s duties. A client token can read only that client’s bookings. GPS inserts are accepted only while that driver has an open trip session, and the session is closed on trip end.

Bengaluru and Hyderabad are rows in `branches`, not separate databases.

The Node RAC service should not be a second source of truth. If pieces of it are useful, port the behaviour into Flask and retire the process.

---

## 13. Migration strategy

Do this only after approval. Not part of this audit.

1. Add PostgreSQL beside the current files. Do not switch reads yet.
2. Define one booking id, one driver id, and one branch id. Map `rac_data.json` rows and SQLite company or cab rows into those tables. Keep the JSON file as the write path until counts match.
3. Dual-write new bookings to JSON and PostgreSQL. Compare.
4. Point `/api/v1` reads at PostgreSQL. Keep the same JSON responses the React app already expects.
5. Leave Zoho as a mirror: write-through export, not the lock.
6. Only then add trip sessions and GPS.

SQLite `database.db` and `rac_data.json` stay until the comparison is clean. No big-bang cutover.

---

## 14. Phased roadmap

Each phase needs approval before code changes.

| Phase | Outcome | Touches production behaviour |
| --- | --- | --- |
| 1. Audit | This document | No |
| 2. Security cleanup | Remove default RAC password, require real signing secrets, confirm the ingest bypass is not public, keep session files out of git | Yes, small |
| 3. PostgreSQL schema and dry-run import | Tables and a count report. Flask still serves JSON. | No user-facing change |
| 4. Dual-write RAC bookings and drivers | Same API responses, two stores | Careful |
| 5. Read from PostgreSQL | Same `/api/v1` contract | Yes |
| 6. Trip session: accept, reject, start, end | New endpoints. Old assign and WhatsApp stay. | Yes |
| 7. GPS during an open trip only | New table and driver endpoint | Yes |
| 8. Driver Android app against those endpoints | New repo or folder, OTP | New client |
| 9. Client portal | Client role, own bookings, invoice view | New client |
| 10. ETS | Routes, shifts, employees, attendance, billing | New module |
| 11. Owner analytics and both branches | Reports on the shared tables | New screens |

---

## 15. Items requiring confirmation

1. Which host rebuilds `main` for `www.shreemaruthitravels.com` (AIC, Fly `smt-website`, or Render).
2. Whether the live proxy’s connection to gunicorn is loopback.
3. Whether production Zoho Sheet and WorkDrive tokens are currently valid.
4. Where the Flutter driver starter lives, if it exists outside this repository.
5. Whether Bengaluru and Hyderabad must be separate legal entities or only branch rows.
6. Whether ETS clients are the same companies as the SQLite `companies` table.
7. Who is allowed to see GPS: owner only, the assigned client, or both.
8. The uncommitted local change to `requirements.txt` was not part of this audit and was not committed.
