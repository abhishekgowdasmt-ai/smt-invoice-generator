"""One-time Zoho Self Client exchange.

Create a Self Client at https://api-console.zoho.in
Generate a code with scopes:
    ZohoSheet.dataAPI.READ,ZohoSheet.dataAPI.UPDATE
Then run this script immediately — the code expires in a few minutes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / ".streamlit" / "secrets.toml"
EXAMPLE = ROOT / ".streamlit" / "secrets.toml.example"

REGIONS = {
    "in": ("https://accounts.zoho.in", "https://sheet.zoho.in/api/v2"),
    "com": ("https://accounts.zoho.com", "https://sheet.zoho.com/api/v2"),
    "eu": ("https://accounts.zoho.eu", "https://sheet.zoho.eu/api/v2"),
}


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> int:
    print("Zoho Sheet token setup")
    print("Use the India datacenter unless your Zoho account was created elsewhere.\n")
    region = prompt("Region (in / com / eu)", "in").lower()
    accounts_url, api_base = REGIONS.get(region, REGIONS["in"])
    client_id = prompt("Client ID")
    client_secret = prompt("Client secret")
    code = prompt("Self Client grant code")
    resource_id = prompt("Zoho Sheet resource id (from the workbook URL)")
    if not all([client_id, client_secret, code]):
        print("Client ID, secret, and grant code are required.")
        return 1

    response = requests.post(
        f"{accounts_url}/oauth/v2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
        timeout=30,
    )
    payload = response.json()
    if "refresh_token" not in payload:
        print("Zoho did not return a refresh token.")
        print(payload)
        return 1

    print("\nSuccess. Put these values in Streamlit secrets:\n")
    print(f'client_id = "{client_id}"')
    print(f'client_secret = "{client_secret}"')
    print(f'refresh_token = "{payload["refresh_token"]}"')
    print(f'resource_id = "{resource_id}"')
    print(f'accounts_url = "{accounts_url}"')
    print(f'api_base = "{api_base}"')

    if resource_id and prompt("Write into .streamlit/secrets.toml? (y/N)", "N").lower() == "y":
        _write_secrets(
            client_id,
            client_secret,
            payload["refresh_token"],
            resource_id,
            accounts_url,
            api_base,
        )
        print(f"Updated {SECRETS}")
    return 0


def _write_secrets(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    resource_id: str,
    accounts_url: str,
    api_base: str,
) -> None:
    SECRETS.parent.mkdir(parents=True, exist_ok=True)
    password = "change-this-now"
    if SECRETS.exists():
        text = SECRETS.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip().startswith("password"):
                password = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    elif EXAMPLE.exists():
        text = EXAMPLE.read_text(encoding="utf-8")
        password = "change-this-now"
    content = f"""[auth]
password = "{password}"

[zoho]
client_id = "{client_id}"
client_secret = "{client_secret}"
refresh_token = "{refresh_token}"
resource_id = "{resource_id}"
accounts_url = "{accounts_url}"
api_base = "{api_base}"
"""
    SECRETS.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
