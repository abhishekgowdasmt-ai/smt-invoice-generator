"""Driver OTP login and password-reset helpers.

Uses hashed OTPs in driver_auth_otps (migration 019). Delivery prefers the
existing WhatsApp bridge. Password login remains available.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import driver_auth
import dev_postgres as pg

_OTP_TTL_SECONDS = 5 * 60
_OTP_COOLDOWN_SECONDS = 60
_OTP_MAX_ATTEMPTS = 5
_PURPOSES = frozenset({"login", "reset"})


def _owner_work(user_id, work):
    done = pg.authorized_transaction(user_id, work)
    if not done or done.get("role") != "owner":
        return None
    return done.get("result")


def _schema_ready(cur):
    cur.execute("SELECT to_regclass('public.driver_auth_otps') IS NOT NULL")
    return bool(cur.fetchone()[0])


def _dev_expose_allowed():
    flag = (os.environ.get("SMT_OTP_DEV_EXPOSE") or "").strip().lower()
    return flag in ("1", "yes", "true")


def _send_whatsapp(phone, body):
    try:
        from rac_api import _wa_bridge_send
    except Exception:
        return False, {"error": "whatsapp_unavailable"}
    # Bridge expects a dialable number; drivers store 10-digit local phones.
    dial = phone if phone.startswith("91") else ("91" + phone)
    return _wa_bridge_send(dial, body)


def _find_driver_login(cur, phone):
    cur.execute(
        """
        SELECT u.id::text, u.password_hash, u.status, u.full_name,
               d.id::text, d.display_name, d.active, d.verification_status, d.phone
        FROM users u
        JOIN drivers d ON d.user_id = u.id
        WHERE u.role = 'driver'
          AND regexp_replace(COALESCE(u.phone, d.phone, ''), '\\D', '', 'g')
              IN (%s, '91' || %s)
        """,
        (phone, phone),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        return None
    return rows[0]


def request_otp(phone, purpose):
    phone = driver_auth.normalize_phone(phone)
    purpose = (purpose or "").strip().lower()
    if not phone:
        return {"ok": False, "error": "invalid", "message": "Enter a valid 10-digit phone number."}
    if purpose not in _PURPOSES:
        return {"ok": False, "error": "invalid", "message": "Unknown OTP purpose."}
    owner_id = pg._bootstrap_owner_id()
    if owner_id is None:
        return None

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = driver_auth.hash_password(code)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=_OTP_TTL_SECONDS)
    box = {"driver": None, "cooldown": False, "ready": True}

    def work(cur):
        if not _schema_ready(cur):
            box["ready"] = False
            return True
        found = _find_driver_login(cur, phone)
        if found is None:
            box["driver"] = None
            return True
        user_id, password_hash, status, full_name, driver_id, display_name, active, verification, _ = found
        if status != "active" or not active:
            box["driver"] = "disabled"
            return True
        if purpose == "reset" and not password_hash:
            box["driver"] = None
            return True
        cur.execute(
            """
            SELECT created_at
            FROM driver_auth_otps
            WHERE phone = %s AND purpose = %s AND consumed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (phone, purpose),
        )
        latest = cur.fetchone()
        if latest and latest[0] is not None:
            created = latest[0]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() < _OTP_COOLDOWN_SECONDS:
                box["cooldown"] = True
                return True
        # Invalidate prior unused codes for this purpose.
        cur.execute(
            """
            UPDATE driver_auth_otps
            SET consumed_at = now()
            WHERE phone = %s AND purpose = %s AND consumed_at IS NULL
            """,
            (phone, purpose),
        )
        cur.execute(
            """
            INSERT INTO driver_auth_otps (phone, purpose, code_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (phone, purpose, code_hash, expires_at),
        )
        box["driver"] = {
            "user_id": user_id,
            "driver_id": driver_id,
            "display_name": display_name or full_name,
            "verification_status": verification,
            "active": active,
        }
        return True

    done = _owner_work(owner_id, work)
    if done is None:
        return None
    if not box["ready"]:
        return {
            "ok": False,
            "error": "unavailable",
            "message": "OTP sign-in is not available yet. Ask the office to finish setup.",
        }
    if box["cooldown"]:
        return {
            "ok": False,
            "error": "conflict",
            "message": "Wait about a minute before requesting another OTP.",
        }
    if box["driver"] == "disabled":
        return {"ok": False, "error": "disabled", "message": "This driver account is inactive."}
    if box["driver"] is None:
        return {
            "ok": False,
            "error": "not_found",
            "message": "No active driver login was found for that phone. Ask the office to create one.",
        }

    action = "sign in" if purpose == "login" else "reset your password"
    body = (
        f"SMT Driver OTP\n\n"
        f"Your code to {action} is {code}.\n"
        f"It expires in {_OTP_TTL_SECONDS // 60} minutes.\n"
        f"Do not share this code."
    )
    sent, send_info = _send_whatsapp(phone, body)
    delivery = "whatsapp" if sent else "pending"
    result = {
        "ok": True,
        "message": (
            "OTP sent on WhatsApp."
            if sent
            else "OTP created. WhatsApp delivery is offline — ask the office or retry shortly."
        ),
        "expires_in": _OTP_TTL_SECONDS,
        "delivery": delivery,
        "purpose": purpose,
    }
    if _dev_expose_allowed():
        # Local/dev only — never enable SMT_OTP_DEV_EXPOSE in production.
        result["dev_code"] = code
        result["delivery_detail"] = send_info if isinstance(send_info, dict) else {"info": str(send_info)}
    return result


def _consume_otp(cur, phone, purpose, code):
    cur.execute(
        """
        SELECT id, code_hash, attempts, expires_at, consumed_at
        FROM driver_auth_otps
        WHERE phone = %s AND purpose = %s
        ORDER BY created_at DESC
        LIMIT 1
        FOR UPDATE
        """,
        (phone, purpose),
    )
    row = cur.fetchone()
    if row is None:
        return {"ok": False, "error": "unauthorized", "message": "Invalid or expired OTP."}
    otp_id, code_hash, attempts, expires_at, consumed_at = row
    if consumed_at is not None:
        return {"ok": False, "error": "unauthorized", "message": "That OTP was already used."}
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return {"ok": False, "error": "unauthorized", "message": "That OTP has expired. Request a new one."}
    if attempts >= _OTP_MAX_ATTEMPTS:
        return {"ok": False, "error": "unauthorized", "message": "Too many attempts. Request a new OTP."}
    if not driver_auth.verify_password(code_hash, code):
        cur.execute(
            "UPDATE driver_auth_otps SET attempts = attempts + 1 WHERE id = %s",
            (otp_id,),
        )
        return {"ok": False, "error": "unauthorized", "message": "Invalid or expired OTP."}
    cur.execute(
        "UPDATE driver_auth_otps SET consumed_at = now(), attempts = attempts + 1 WHERE id = %s",
        (otp_id,),
    )
    return {"ok": True}


def verify_otp_login(phone, code):
    phone = driver_auth.normalize_phone(phone)
    code = (code or "").strip()
    if not phone:
        return {"ok": False, "error": "invalid", "message": "Enter a valid 10-digit phone number."}
    if not code.isdigit() or len(code) != 6:
        return {"ok": False, "error": "invalid", "message": "Enter the 6-digit OTP."}
    owner_id = pg._bootstrap_owner_id()
    if owner_id is None:
        return None
    box = {"result": None}

    def work(cur):
        if not _schema_ready(cur):
            box["result"] = {
                "ok": False,
                "error": "unavailable",
                "message": "OTP sign-in is not available yet.",
            }
            return True
        check = _consume_otp(cur, phone, "login", code)
        if not check.get("ok"):
            box["result"] = check
            return True
        found = _find_driver_login(cur, phone)
        if found is None:
            box["result"] = {
                "ok": False,
                "error": "unauthorized",
                "message": "Invalid or expired OTP.",
            }
            return True
        user_id, _hash, status, full_name, driver_id, display_name, active, verification, _ = found
        if status != "active" or not active:
            box["result"] = {
                "ok": False,
                "error": "disabled",
                "message": "This driver account is inactive.",
            }
            return True
        token = driver_auth.issue_token(user_id, driver_id)
        if not token:
            box["result"] = None
            return True
        box["result"] = {
            "ok": True,
            "token": token,
            "user": {"id": user_id, "full_name": full_name, "role": "driver"},
            "driver": {
                "id": driver_id,
                "display_name": display_name,
                "active": active,
                "verification_status": verification,
            },
        }
        return True

    done = _owner_work(owner_id, work)
    if done is None:
        return None
    return box["result"]


def reset_password_with_otp(phone, code, new_password):
    phone = driver_auth.normalize_phone(phone)
    code = (code or "").strip()
    if not phone:
        return {"ok": False, "error": "invalid", "message": "Enter a valid 10-digit phone number."}
    if not code.isdigit() or len(code) != 6:
        return {"ok": False, "error": "invalid", "message": "Enter the 6-digit OTP."}
    if not isinstance(new_password, str) or len(new_password) < 8:
        return {"ok": False, "error": "invalid", "message": "Password must be at least 8 characters."}
    owner_id = pg._bootstrap_owner_id()
    if owner_id is None:
        return None
    password_hash = driver_auth.hash_password(new_password)
    box = {"result": None}

    def work(cur):
        if not _schema_ready(cur):
            box["result"] = {
                "ok": False,
                "error": "unavailable",
                "message": "OTP reset is not available yet.",
            }
            return True
        check = _consume_otp(cur, phone, "reset", code)
        if not check.get("ok"):
            box["result"] = check
            return True
        found = _find_driver_login(cur, phone)
        if found is None:
            box["result"] = {
                "ok": False,
                "error": "unauthorized",
                "message": "Invalid or expired OTP.",
            }
            return True
        user_id, _old, status, _full, _driver_id, _display, active, _verification, _ = found
        if status != "active" or not active:
            box["result"] = {
                "ok": False,
                "error": "disabled",
                "message": "This driver account is inactive.",
            }
            return True
        cur.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s::uuid AND role = 'driver'
            RETURNING id::text
            """,
            (password_hash, user_id),
        )
        if cur.fetchone() is None:
            box["result"] = {
                "ok": False,
                "error": "conflict",
                "message": "Password could not be updated.",
            }
            return True
        box["result"] = {
            "ok": True,
            "message": "Password updated. You can sign in with the new password.",
        }
        return True

    done = _owner_work(owner_id, work)
    if done is None:
        return None
    return box["result"]
