# Shree Maruthi Travels (SMT) Website

A premium, highly interactive corporate website and booking queue dashboard for **Shree Maruthi Travels (SMT)**, Bangalore.

## Tech Stack
- **Backend**: Python (Flask)
- **Database**: SQLite (No external setup required, auto-generated on startup)
- **Frontend**: Vanilla HTML5, CSS3, & JS (custom responsive styling, interactive forms, helpdesk chatbot, auto-scrolling partner logo marquee, Supervisor dashboard)

---

## Getting Started

### 1. Setup Environment & Install Dependencies
Navigate to the project directory and install the requirements:

```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the Application
Start the Flask local development server:

```bash
python app.py
```

The server runs on **`http://localhost:5000`** by default.

---

## Navigation & Portals
- **Client Homepage**: [http://localhost:5000/](http://localhost:5000/)
  - Features the animated hero header, corporate about panel, interactive Mission/Vision tab toggles, filterable services list, multi-stage booking quote wizard, and a live AI Helpdesk chat drawer.
- **Supervisor Admin Dashboard**: [http://localhost:5000/admin](http://localhost:5000/admin)
  - restricted portal for supervisor Mr. Byre Gowda.
  - **Passcode (local verification)**: `5999`
  - Inquiries, cabs, drivers, and corporate clients.
  - Staff tools (same PIN, cookie after login):
    - [Invoice generator](http://localhost:5000/admin/invoices/)
    - [Trip sheet generator](http://localhost:5000/admin/trips)
    - [RAC dispatch](http://localhost:5000/admin/dispatch/) — after the supervisor PIN, dispatch opens for staff. Fallback login: `admin@dispatch.local` / `Admin@12345`.
      Drivers, bookings, and assignments are stored in **Zoho Sheet** (worksheets `RAC_Drivers`, `RAC_Bookings`, `RAC_Assignments`, `RAC_Uploads`, `RAC_Messages`) using the same Zoho API keys as inquiries. If Zoho keys are missing, data is saved locally in `backend/rac_data.json`.
