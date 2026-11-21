"""Shared API contracts for supervisor, driver, and client applications.

This module is documentation-as-code. It does not replace per-app auth or
response envelopes. Frontends must keep using their existing routes; services
should keep returning {ok, error, message} internally.
"""
from __future__ import annotations

# Internal service error codes → HTTP status (all three apps).
ERROR_HTTP_STATUS = {
    "not_found": 404,
    "forbidden": 403,
    "conflict": 409,
    "invalid": 400,
    "unauthorized": 401,
    "disabled": 403,
    "unavailable": 503,
}

BOOKING_STATUSES = frozenset(
    ("unassigned", "assigned", "accepted", "started", "completed", "cancelled")
)

ASSIGNMENT_STATUSES = frozenset(
    ("assigned", "accepted", "rejected", "withdrawn", "superseded", "completed")
)

BOOKING_ORIGINS = frozenset(("rac", "ets_occurrence", "retail", "client_request"))

# Client-visible trip fields (from client_duty_status). Internal notes, documents,
# payouts, and supervisor-only audit fields are intentionally omitted.
CLIENT_TRIP_FIELDS = frozenset(
    (
        "booking_id",
        "trip_date",
        "pickup_time",
        "cab_type",
        "pickup_location",
        "route",
        "passenger_name",
        "duty_status",
        "assignment_status",
        "driver_name",
        "driver_phone",
        "vehicle_registration",
        "vehicle_model",
    )
)

# Auth transport contract — keep mechanisms separate; never unify into one cookie.
AUTH_PROFILES = {
    "supervisor": {
        "transport": "cookie",
        "cookie": "smt_staff",
        "also_accepts": "Bearer",
        "db_roles": ("smt_owner", "smt_staff"),
        "identity": "email → users row via resolve_login_identity",
    },
    "driver": {
        "transport": "Bearer",
        "header": "Authorization",
        "db_roles": ("smt_driver",),
        "identity": "token uid/did → current_driver_id()",
    },
    "client": {
        "transport": "cookie",
        "cookie": "smt_client",
        "http_only": True,
        "db_roles": ("smt_client",),
        "identity": "token uid/cid → client_can_company()",
    },
}


def http_status_for_error(error, default=400):
    if not error:
        return default
    return ERROR_HTTP_STATUS.get(error, default)


def error_payload(message, error=None, extra=None):
    body = {"success": False, "message": message}
    if error == "disabled":
        body["code"] = "disabled"
    if isinstance(extra, dict):
        body.update(extra)
    return body
