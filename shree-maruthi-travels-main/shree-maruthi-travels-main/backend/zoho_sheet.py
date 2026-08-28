"""
zoho_sheet.py — Zoho Sheet API Integration for SMT Leads
Appends inquiry data as new rows in the Zoho Sheet spreadsheet.
Uses OAuth2 refresh token flow for authentication.
"""
import os
import requests
import json
from datetime import datetime

# ─── Zoho Configuration (from environment variables) ───
ZOHO_CLIENT_ID     = os.environ.get('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET', '')
ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN', '')
ZOHO_SPREADSHEET_ID = os.environ.get('ZOHO_SPREADSHEET_ID', '2x1po0f84c2bbaca14b88adfb5cb5f58e732d')

# Zoho API base URLs (India DC)
ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.in/oauth/v2/token'
ZOHO_SHEET_API_URL = 'https://sheet.zoho.in/api/v2'

# Cache the access token in memory
_access_token_cache = {'token': None, 'expires_at': 0}


def _get_access_token():
    """Get a valid Zoho access token using the refresh token."""
    import time
    now = time.time()

    # Return cached token if still valid (with 60s buffer)
    if _access_token_cache['token'] and _access_token_cache['expires_at'] > now + 60:
        return _access_token_cache['token']

    if not all([ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN]):
        print("[ZOHO] Missing API credentials — skipping Zoho Sheet push")
        return None

    try:
        resp = requests.post(ZOHO_ACCOUNTS_URL, params={
            'refresh_token': ZOHO_REFRESH_TOKEN,
            'client_id': ZOHO_CLIENT_ID,
            'client_secret': ZOHO_CLIENT_SECRET,
            'grant_type': 'refresh_token'
        }, timeout=10)

        data = resp.json()
        if 'access_token' in data:
            _access_token_cache['token'] = data['access_token']
            _access_token_cache['expires_at'] = now + data.get('expires_in', 3600)
            print(f"[ZOHO] Access token refreshed successfully")
            return data['access_token']
        else:
            print(f"[ZOHO] Token refresh failed: {data}")
            return None
    except Exception as e:
        print(f"[ZOHO] Token refresh error: {e}")
        return None


def append_inquiry_to_sheet(inquiry_data):
    """
    Append a new inquiry row to the Zoho Sheet.

    Args:
        inquiry_data: dict with keys: name, email, phone, company,
                      service_type, employee_count, details
    Returns:
        True if successful, False otherwise
    """
    token = _get_access_token()
    if not token:
        print("[ZOHO] No token available — falling back to local logging")
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Build the row data matching our spreadsheet columns:
    # A: Timestamp | B: Name | C: Phone | D: Email | E: Service Type |
    # F: Company | G: Employee Count | H: Details | I: Status
    row_data = [
        timestamp,
        inquiry_data.get('name', ''),
        inquiry_data.get('phone', ''),
        inquiry_data.get('email', ''),
        inquiry_data.get('service_type', ''),
        inquiry_data.get('company', ''),
        str(inquiry_data.get('employee_count', 0)),
        inquiry_data.get('details', ''),
        'New'
    ]

    url = f"{ZOHO_SHEET_API_URL}/{ZOHO_SPREADSHEET_ID}"

    headers = {
        'Authorization': f'Zoho-oauthtoken {token}'
    }

    payload = {
        "method": "worksheet.records.add",
        "worksheet_name": "Sheet1",
        "header_row": 1,
        "json_data": json.dumps([{
            "Timestamp": row_data[0],
            "Name": row_data[1],
            "Phone": row_data[2],
            "Email": row_data[3],
            "Service Type": row_data[4],
            "Company": row_data[5],
            "Employee Count": row_data[6],
            "Details": row_data[7],
            "Status": row_data[8]
        }])
    }

    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=15)
        result = resp.json()

        if resp.status_code == 200 and result.get('status') == 'success':
            print(f"[ZOHO] [SUCCESS] Inquiry from {row_data[1]} added to Zoho Sheet")
            return True
        else:
            print(f"[ZOHO] [WARN] API response: {result}")
            return False
    except Exception as e:
        print(f"[ZOHO] [ERROR] Error pushing to sheet: {e}")
        return False


def test_connection():
    """Quick test to verify Zoho Sheet API connectivity."""
    token = _get_access_token()
    if not token:
        return {"status": "error", "message": "Could not obtain access token"}

    url = f"{ZOHO_SHEET_API_URL}/{ZOHO_SPREADSHEET_ID}"
    headers = {
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json'
    }

    try:
        resp = requests.get(url, headers=headers, params={
            "method": "worksheet.records.fetch",
            "worksheet_name": "Sheet1",
            "header_row": 1,
            "count": 1
        }, timeout=10)
        data = resp.json()
        return {"status": "success", "response": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
