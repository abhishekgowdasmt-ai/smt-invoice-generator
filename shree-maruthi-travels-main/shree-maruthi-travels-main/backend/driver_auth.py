"""Driver mobile session tokens. Identity is always resolved server-side."""
from __future__ import annotations

import os
import re

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

DRIVER_HEADER = "Authorization"
_TOKEN_MAX_AGE = 60 * 60 * 24 * 14  # 14 days


def _driver_secret():
    value = (os.environ.get("DRIVER_TOKEN") or "").strip()
    if len(value) >= 32:
        return value
    # Local development fallback: reuse STAFF_TOKEN with a different salt.
    staff = (os.environ.get("STAFF_TOKEN") or "").strip()
    if len(staff) >= 32:
        return staff
    raise RuntimeError(
        "DRIVER_TOKEN (or STAFF_TOKEN for local fallback) must be at least 32 characters"
    )


def _serializer():
    return URLSafeTimedSerializer(_driver_secret(), salt="smt-driver-v1")


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password_hash, password):
    if not password_hash or not isinstance(password, str):
        return False
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def normalize_phone(value):
    if not isinstance(value, str):
        return None
    digits = re.sub(r"\D", "", value.strip())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10:
        return None
    return digits


def issue_token(user_id, driver_id):
    user_id = (user_id or "").strip()
    driver_id = (driver_id or "").strip()
    if not user_id or not driver_id:
        return None
    return _serializer().dumps({"uid": user_id, "did": driver_id, "role": "driver"})


def read_token(token):
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("role") != "driver":
        return None
    user_id = str(data.get("uid") or "").strip()
    driver_id = str(data.get("did") or "").strip()
    if not user_id or not driver_id:
        return None
    return {"user_id": user_id, "driver_id": driver_id, "role": "driver"}


def bearer_token(header_value):
    if not isinstance(header_value, str):
        return None
    text = header_value.strip()
    if not text.lower().startswith("bearer "):
        return None
    token = text[7:].strip()
    return token or None
