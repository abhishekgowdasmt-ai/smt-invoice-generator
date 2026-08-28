# SMT System Architecture & Documentation

This document outlines the technical design, database schema, and API specifications for the **Shree Maruthi Travels (SMT)** web application.

---

## 📂 Project Structure

```text
shree-maruthi-travels/
│
├── backend/
│   ├── app.py                # Main Flask application & REST API endpoints
│   ├── database.db           # SQLite database file (auto-generated on startup, ignored in Git)
│   ├── requirements.txt      # Python dependencies
│   └── venv/                 # Python virtual environment (ignored in Git)
│
├── frontend/
│   ├── static/               # Assets, custom styling, and client-side logic
│   │   ├── css/
│   │   │   # CSS files are linked dynamically or embedded in HTML
│   │   └── js/
│   │       # JS files and libraries
│   │
│   └── templates/
│       ├── index.html        # Main Client Homepage
│       └── admin.html        # Supervisor Admin Dashboard
│
├── .gitignore                # Git exclusion patterns
├── ARCHITECTURE.md           # Architecture documentation (this file)
└── README.md                 # Main Readme & Getting Started Guide
```

---

## 🗄️ Database Schema (SQLite)

The application uses a lightweight local SQLite database (`database.db`) initialized automatically on startup by `app.py`. It consists of two tables:

### 1. `inquiries` Table
Stores client-submitted quote requests from the homepage booking wizard.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique identifier for each inquiry |
| `name` | TEXT | NOT NULL | Client contact name |
| `email` | TEXT | NOT NULL | Client email address |
| `phone` | TEXT | NOT NULL | Client phone number |
| `company` | TEXT | Optional | Client corporate name |
| `service_type`| TEXT | NOT NULL | Selected service (e.g., Corporate ETS, Airport Pick-up) |
| `employee_count`| INTEGER| DEFAULT 0 | Estimated number of daily commuters |
| `details` | TEXT | Optional | Specific route, timings, or additional comments |
| `status` | TEXT | DEFAULT 'Pending' | Current state: `'Pending'`, `'In Progress'`, or `'Completed'` |
| `created_at` | TEXT | NOT NULL | Submission timestamp (`YYYY-MM-DD HH:MM:SS`) |

### 2. `chat_logs` Table
Logs helpdesk chatbot conversations for quality assurance and analytical reviews.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique log ID |
| `session_id` | TEXT | Optional | Session ID for the chat (allows session grouping) |
| `user_message`| TEXT | - | Raw text entered by the visitor |
| `bot_response`| TEXT | - | Response returned by SMT Helpdesk Bot |
| `created_at` | TEXT | NOT NULL | Message timestamp (`YYYY-MM-DD HH:MM:SS`) |

---

## 🔌 API Reference

### Client Interfaces
* **`POST /api/inquiries`**
  * **Description:** Inserts a new quote booking inquiry into the database. Spawns an asynchronous thread to send/log a notification email.
  * **Payload (JSON):**
    ```json
    {
      "name": "Jane Doe",
      "email": "jane@example.com",
      "phone": "+919876543210",
      "company": "Tech Corp",
      "service_type": "Corporate ETS",
      "employee_count": 45,
      "details": "Jayanagar to Whitefield shift pick-up"
    }
    ```
  * **Response (201 Created):**
    ```json
    {
      "message": "Inquiry submitted successfully",
      "status": "success"
    }
    ```

* **`POST /api/chat`**
  * **Description:** Interacts with the local Helpdesk AI Bot. Uses a quick rule-based keyword matching algorithm containing SMT's head office address, services description, accessories list (GPS, safety kits, stereos), partners (Amazon, TCS, Uber, etc.), and contact phone numbers.
  * **Payload (JSON):**
    ```json
    {
      "message": "What is the contact number?",
      "session_id": "abc-123"
    }
    ```
  * **Response (200 OK):**
    ```json
    {
      "response": "You can contact SMT at +91 9611975999..."
    }
    ```

### Admin / Supervisor Interfaces (Requires Authorization)
*Note: Protected endpoints require the HTTP Header: `Authorization: Bearer smt-session-token`.*

* **`POST /api/admin/login`**
  * **Description:** Validates supervisor passcode (local passcode `5999`).
  * **Payload (JSON):** `{"passcode": "5999"}`
  * **Response (200 OK):** `{"authenticated": true, "token": "smt-session-token"}`
  * **Response (401 Unauthorized):** `{"authenticated": false, "error": "Invalid passcode"}`

* **`GET /api/inquiries`**
  * **Description:** Retrieves all client inquiries from newest to oldest.
  * **Response (200 OK):** Array of inquiry objects.

* **`POST /api/inquiries/<int:inquiry_id>/status`**
  * **Description:** Updates the status workflow step for a specific inquiry.
  * **Payload (JSON):** `{"status": "In Progress"}` *(Values: 'Pending', 'In Progress', 'Completed')*
  * **Response (200 OK):** `{"message": "Inquiry status updated to In Progress"}`

* **`GET /api/stats`**
  * **Description:** Computes real-time statistics regarding inquiries.
  * **Response (200 OK):**
    ```json
    {
      "total": 12,
      "pending": 4,
      "in_progress": 5,
      "completed": 3,
      "services": {
        "Corporate ETS": 8,
        "Rental Services": 4
      }
    }
    ```

---

## 🎨 Frontend Design & Aesthetics

The frontend is crafted for high-performance and premium user experience:
1. **Color Palette:** Custom HSL variables representing a sleek dark mode backdrop combined with vibrant cyan/blue gradients for headers and key CTA buttons.
2. **Interactive Elements:**
   - **Hero Marquee:** An auto-scrolling partner logo marquee for top brands like Amazon, TCS, Uber, etc.
   - **Service Filters:** Category toggle buttons that instantly filter the displayed services grid.
   - **Helpdesk Chat Drawer:** Smooth slide-out panel that persists state and updates messaging via asynchronous fetch calls.
   - **Quote Wizard:** Dynamic step-by-step progress tracking preventing form submissions until all pages are valid.
