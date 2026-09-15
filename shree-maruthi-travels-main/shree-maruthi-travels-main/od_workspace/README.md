# Private Overdraft Ledger

A locked Streamlit workspace for a Bank of Baroda overdraft of ₹99,00,000.  
Every drawdown, repayment, interest debit, and charge is stored in **your Zoho Sheet**, so a free Streamlit Cloud restart cannot wipe the books.

The public page title is only **Workspace**. The OD details stay behind a passphrase.

## Why Zoho Sheet

Streamlit Community Cloud is free, but its disk is ephemeral. Files written on the server disappear on reboot.

Zoho Workplace / WorkDrive already gives you Zoho Sheet. The app treats that workbook as the database:

| Worksheet | Purpose |
| --- | --- |
| `Transactions` | Every movement |
| `Facility` | Limit, rate, opening outstanding, branch |
| `Categories` | Spend labels |

You keep the file in your Zoho account, unshared. The website only holds a refresh token.

## Local run

Use the custom site, not Streamlit. Streamlit cannot look like a finished product.

```powershell
cd "C:\Users\Abhishek B G\Downloads\BOB"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
python -m uvicorn server.main:app --reload --port 8800
```

Open http://localhost:8800

## Free deploy on Render

Data stays in Zoho Sheet. Render only hosts the website and sleeps after 15 minutes of no traffic.

1. Push this folder to a **private** GitHub repo (secrets.toml is gitignored).
2. Open [Render — New Web Service](https://dashboard.render.com/select-repo?type=web) and pick the repo.
3. Choose the **Free** instance.
4. Build: `pip install -r requirements.txt`
5. Start: `uvicorn server.main:app --host 0.0.0.0 --port $PORT`
6. Add these environment variables from your local `.streamlit/secrets.toml`:

```
LEDGER_PASSWORD
ZOHO_CLIENT_ID
ZOHO_CLIENT_SECRET
ZOHO_REFRESH_TOKEN
ZOHO_RESOURCE_ID
ZOHO_ACCOUNTS_URL=https://accounts.zoho.in
ZOHO_API_BASE=https://sheet.zoho.in/api/v2
```

First open after sleep can take about a minute. The URL is public; the passphrase and Zoho file stay private.

## If Render free is full

Use [Railway](https://railway.app/new) (free plan / trial, GitHub deploy):

1. New project → Deploy from GitHub → `private-workspace`
2. Same environment variables as Render
3. Start command is already in `railway.toml`

Other no-card hosts: [Velixir](https://velixir.net/free), [Runsite](https://runsite.app/). Fly.io is cheap but not free.

Set a real passphrase in `.streamlit/secrets.toml` before you put any money data in.

## Connect Zoho Sheet (do this once)

Use a **Self Client**. That is the right OAuth type when the app reads your own workbook and nobody else logs into Zoho through the site.

1. Create a blank workbook in Zoho Sheet. Name it something boring, not `BOB 99L OD`.
2. Copy the resource id from the URL:
   `https://sheet.zoho.in/sheet/open/<RESOURCE_ID>`
3. Open [Zoho API Console](https://api-console.zoho.in) (use `.com` if your account is not on the India datacenter).
4. **Get Started → Self Client → Create**.
5. On **Generate Code**, scopes:
   `ZohoSheet.dataAPI.READ,ZohoSheet.dataAPI.UPDATE`
   Expiry: 10 minutes.
6. Run the helper immediately:

```powershell
python scripts/zoho_oauth.py
```

Paste Client ID, Client Secret, grant code, and resource id. The script prints a `refresh_token`.

7. Put those values under `[zoho]` in `.streamlit/secrets.toml`.
8. Unlock the app → **Settings → Create worksheets and headers**.

If header writing fails, paste the rows from `templates/zoho_headers.md` into row 1 of each worksheet, then click the button again.

### How the API calls work

```
Authorization: Zoho-oauthtoken <access_token>
POST https://sheet.zoho.in/api/v2/<resource_id>
```

| Action | Zoho method |
| --- | --- |
| Read rows | `worksheet.records.fetch` |
| Add a movement | `worksheet.records.add` |
| Edit / delete | `worksheet.records.update` / `delete` with `criteria=id="..."` |
| New access token | `grant_type=refresh_token` against `accounts.zoho.in` |

Access tokens last about an hour. The refresh token stays in Streamlit secrets and is never shown in the UI.

India accounts must use `accounts.zoho.in` and `sheet.zoho.in`. US/EU accounts use `.com` / `.eu`.

## Free deploy without losing data

1. Push this folder to a **private** GitHub repo. Never commit `secrets.toml`.
2. Go to [share.streamlit.io](https://share.streamlit.io), deploy `app.py`.
3. In the app settings → **Secrets**, paste the same TOML as local `.streamlit/secrets.toml`.
4. Open **Settings** in the live app and initialise the workbook once.

Streamlit Cloud is free. The URL is guessable if you share it, so use a long passphrase and a bland repo name.

## How to keep it secret

- Do not share the Streamlit URL, the Zoho workbook, or the refresh token.
- Store only the last 4 digits of the account number.
- Do not grant Zoho Sheet access to anyone else.
- Lock the workspace when you step away. The session expires after 30 minutes.
- Prefer a hashed password: `sha256:` plus the hex digest of your passphrase.

## Sections

- **Overview** — limit, outstanding, available, utilisation, month-to-date, interest watch
- **New entry** — drawdown, credit, bank interest, charge
- **Ledger** — filter, edit, delete, CSV export
- **Insights** — category, month, and project buckets
- **Interest** — daily-product estimate vs interest the bank actually posted
- **Settings** — facility of ₹99 Lakh, Zoho connection, categories

Opening outstanding is for money already used before you started this ledger. After that, record every bank movement, including monthly interest.

## If Zoho is down

The app still writes a local `data/ledger.json` copy. On Streamlit Cloud that file is only a cache. Zoho remains the copy that survives deploys.
