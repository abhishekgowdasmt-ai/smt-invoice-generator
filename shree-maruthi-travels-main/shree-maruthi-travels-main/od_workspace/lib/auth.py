from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta

import streamlit as st

from lib.constants import SESSION_MINUTES


def _configured_password() -> str:
    try:
        return str(st.secrets["auth"]["password"])
    except Exception:
        return ""


def _matches(provided: str, expected: str) -> bool:
    if not expected:
        return False
    if expected.startswith("sha256:"):
        digest = hashlib.sha256(provided.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, expected.split(":", 1)[1])
    return hmac.compare_digest(provided, expected)


def is_authenticated() -> bool:
    if not st.session_state.get("authed"):
        return False
    stamp = st.session_state.get("authed_at")
    if not stamp:
        return False
    expiry = datetime.fromisoformat(stamp) + timedelta(minutes=SESSION_MINUTES)
    if datetime.now() > expiry:
        logout()
        return False
    return True


def touch_session() -> None:
    if st.session_state.get("authed"):
        st.session_state["authed_at"] = datetime.now().isoformat()


def login(password: str) -> tuple[bool, str]:
    expected = _configured_password()
    if not expected:
        return (
            False,
            "Set auth.password in .streamlit/secrets.toml before using this ledger.",
        )
    if _matches(password, expected):
        st.session_state["authed"] = True
        st.session_state["authed_at"] = datetime.now().isoformat()
        return True, ""
    return False, "Incorrect passphrase."


def logout() -> None:
    for key in ("authed", "authed_at"):
        st.session_state.pop(key, None)


def password_is_configured() -> bool:
    return bool(_configured_password())
