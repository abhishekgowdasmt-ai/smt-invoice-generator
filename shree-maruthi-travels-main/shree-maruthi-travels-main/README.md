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
  - Google Sign-In only. PIN login is removed.
  - Who can open what, Google Cloud project, and where secrets live: [STAFF_AND_OD.md](STAFF_AND_OD.md)
  - Inquiries, cabs, drivers, and corporate clients.
  - Staff tools after Google login:
    - [Invoice generator](http://localhost:5000/admin/invoices/)
    - [Trip sheet generator](http://localhost:5000/admin/trips)
    - [RAC dispatch](http://localhost:5000/admin/dispatch/)
    - [OD workspace](http://localhost:5000/admin/workspace) — Abhishek and company Gmail only.
