from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_FILE = ROOT / ".streamlit" / "secrets.toml"


@lru_cache(maxsize=1)
def secrets() -> dict:
    if not SECRETS_FILE.exists():
        return {}
    try:
        return tomllib.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def auth_password() -> str:
    env = os.getenv("LEDGER_PASSWORD", "").strip()
    if env:
        return env
    return str(secrets().get("auth", {}).get("password", "") or "")


def session_secret() -> str:
    return os.getenv("LEDGER_SESSION_SECRET") or auth_password() or "ledger-dev-secret"


def zoho_config() -> dict[str, str]:
    defaults = {
        "client_id": "",
        "client_secret": "",
        "refresh_token": "",
        "resource_id": "",
        "accounts_url": "https://accounts.zoho.in",
        "api_base": "https://sheet.zoho.in/api/v2",
    }
    section = secrets().get("zoho", {})
    out = {}
    for key, default in defaults.items():
        ledger_key = f"LEDGER_ZOHO_{key.upper()}"
        shared_ok = key in {"client_id", "client_secret", "accounts_url", "api_base"}
        shared_key = f"ZOHO_{key.upper()}" if shared_ok else ""
        resource_fallback = os.getenv("ZOHO_RESOURCE_ID", "") if key == "resource_id" else ""
        out[key] = str(
            os.getenv(ledger_key)
            or (os.getenv(shared_key) if shared_key else "")
            or resource_fallback
            or section.get(key)
            or default
        )
    return out
