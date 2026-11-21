"""Client portal session tokens (httpOnly cookie). Identity is server-resolved."""
from __future__ import annotations

import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

CLIENT_COOKIE = "smt_client"
_TOKEN_MAX_AGE = 60 * 60 * 12  # 12 hours


def _client_secret():
    value = (os.environ.get("CLIENT_TOKEN") or "").strip()
    if len(value) >= 32:
        return value
    staff = (os.environ.get("STAFF_TOKEN") or "").strip()
    if len(staff) >= 32:
        return staff
    raise RuntimeError(
        "CLIENT_TOKEN (or STAFF_TOKEN for local fallback) must be at least 32 characters"
    )


def _serializer():
    return URLSafeTimedSerializer(_client_secret(), salt="smt-client-v1")


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password_hash, password):
    if not password_hash or not isinstance(password, str):
        return False
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def normalize_email(value):
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if not email or "@" not in email or " " in email:
        return None
    return email


def issue_token(user_id, company_id):
    user_id = (user_id or "").strip()
    company_id = (company_id or "").strip()
    if not user_id or not company_id:
        return None
    return _serializer().dumps({"uid": user_id, "cid": company_id, "role": "client"})


def read_token(token):
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("role") != "client":
        return None
    user_id = str(data.get("uid") or "").strip()
    company_id = str(data.get("cid") or "").strip()
    if not user_id or not company_id:
        return None
    return {"user_id": user_id, "company_id": company_id, "role": "client"}
