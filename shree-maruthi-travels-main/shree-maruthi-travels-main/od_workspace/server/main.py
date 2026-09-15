from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from lib.business import month_key, summarise
from lib.business_store import BusinessStore
from lib.rac import parse_workbook
from lib.config import session_secret
from lib.constants import SESSION_MINUTES
from lib.ledger import estimated_interest, snapshot, transactions_frame
from lib.storage import LedgerStore
from lib.zoho_sheet import ZohoSheetError, zoho_is_configured
from server.serialize import overview_payload

WEB = Path(__file__).resolve().parent.parent / "web"
STORE = LedgerStore()
BIZ = BusinessStore()
SECURE_COOKIES = os.getenv("RENDER") == "true" or os.getenv("HTTPS") == "1"
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
import staff_auth

app = FastAPI(title="Private Ledger", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    max_age=SESSION_MINUTES * 60,
    same_site="lax",
    https_only=SECURE_COOKIES,
)
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


def _od_staff(request: Request):
    return staff_auth.read_token(request.cookies.get(staff_auth.STAFF_COOKIE))


def _require(request: Request) -> None:
    staff = _od_staff(request)
    if not staff or staff.get("role") != "od":
        raise HTTPException(status_code=403, detail="OD access only")


@app.middleware("http")
async def od_google_gate(request: Request, call_next):
    if request.url.path in {"/health", "/api/session"}:
        return await call_next(request)
    staff = _od_staff(request)
    if staff and staff.get("role") == "od":
        return await call_next(request)
    if request.url.path.startswith("/api"):
        return JSONResponse({"detail": "OD access only"}, status_code=403)
    return RedirectResponse("/admin")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get("/api/session")
def session_status(request: Request) -> dict[str, Any]:
    staff = _od_staff(request) or {}
    ok = staff.get("role") == "od"
    return {
        "ok": ok,
        "email": staff.get("email") if ok else None,
        "password_configured": True,
    }


@app.post("/api/login")
async def login(request: Request) -> dict[str, Any]:
    raise HTTPException(status_code=410, detail="Use Google Sign-In on /admin")


@app.post("/api/logout")
async def logout(request: Request) -> dict[str, Any]:
    return {"ok": True, "redirect": "/admin"}


@app.get("/api/overview")
def overview(request: Request) -> dict[str, Any]:
    _require(request)
    STORE.load(force=True)
    payload = overview_payload(STORE)
    payload["zoho_configured"] = zoho_is_configured()
    return payload


@app.post("/api/transactions")
async def add_transaction(request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    amount = float(str(body.get("amount") or 0).replace(",", "") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    row = STORE.add_transaction(body)
    return {"ok": True, "row": row}


@app.put("/api/transactions/{record_id}")
async def update_transaction(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    row = STORE.update_transaction(record_id, body)
    return {"ok": True, "row": row}


@app.delete("/api/transactions/{record_id}")
def delete_transaction(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    STORE.delete_transaction(record_id)
    return {"ok": True}


@app.put("/api/facility")
async def save_facility(request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    STORE.save_facility(body)
    return {"ok": True}


@app.put("/api/categories")
async def save_categories(request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    STORE.save_categories(body.get("categories") or [])
    return {"ok": True}


@app.post("/api/zoho/init")
def zoho_init(request: Request) -> dict[str, Any]:
    _require(request)
    try:
        STORE.initialise_zoho()
    except ZohoSheetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/interest")
def interest(request: Request, start: str = "", end: str = "", rate: float = 0) -> dict[str, Any]:
    _require(request)
    facility = STORE.facility()
    state = snapshot(facility, STORE.transactions())
    used_rate = rate or state["rate"]
    from datetime import date as date_cls

    from lib.formatting import parse_date

    start_d = parse_date(start) or parse_date(facility.get("sanction_date")) or date_cls.today().replace(day=1)
    end_d = parse_date(end) or date_cls.today()
    estimate = estimated_interest(state["frame"], state["opening"], used_rate, start_d, end_d)
    frame = transactions_frame(STORE.transactions())
    posted = 0.0
    if not frame.empty:
        mask = (
            (frame["type"] == "Interest")
            & (frame["date"].dt.date >= start_d)
            & (frame["date"].dt.date <= end_d)
        )
        posted = float(frame.loc[mask, "amount"].abs().sum())
    daily = estimate["daily"]
    return {
        "estimated": estimate["interest"],
        "posted": posted,
        "difference": estimate["interest"] - posted,
        "average": estimate["average_outstanding"],
        "days": estimate["days"],
        "rate": used_rate,
        "daily": [
            {"date": str(row["date"]), "outstanding": float(row["outstanding"])}
            for _, row in daily.iterrows()
        ]
        if not daily.empty
        else [],
    }


@app.get("/api/business")
def business(request: Request, month: str = "") -> dict[str, Any]:
    _require(request)
    BIZ.load(force=True)
    used = month_key(month)
    data = BIZ.load()
    summary = summarise(data, used)
    return {
        "month": used,
        "summary": summary,
        "entries": data.get("entries") or [],
        "partners": data.get("partners") or [],
        "loans": data.get("loans") or [],
        "cards": data.get("cards") or [],
        "bookings": summary.get("bookings") or [],
        "rates": data.get("rates") or {},
        "zoho_configured": zoho_is_configured(),
        "storage": BIZ.backend,
    }


@app.post("/api/business/entries")
async def add_business_entry(request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    kind = str(body.get("kind") or "expense")
    if kind not in {"income", "expense", "saving", "note"}:
        raise HTTPException(status_code=400, detail="Unknown entry kind")
    if kind != "note":
        amount = float(str(body.get("amount") or 0).replace(",", "") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    row = BIZ.add_entry(body)
    return {"ok": True, "row": row}


@app.put("/api/business/entries/{record_id}")
async def update_business_entry(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    row = BIZ.update_entry(record_id, body)
    return {"ok": True, "row": row}


@app.delete("/api/business/entries/{record_id}")
def delete_business_entry(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    BIZ.delete_entry(record_id)
    return {"ok": True}


@app.post("/api/business/registers/{key}")
async def upsert_register(key: str, request: Request) -> dict[str, Any]:
    _require(request)
    if key not in {"partners", "loans", "cards"}:
        raise HTTPException(status_code=400, detail="Unknown register")
    body = await request.json()
    try:
        row = BIZ.upsert_register(key, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "row": row}


@app.delete("/api/business/registers/{key}/{record_id}")
def delete_register(key: str, record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    if key not in {"partners", "loans", "cards"}:
        raise HTTPException(status_code=400, detail="Unknown register")
    BIZ.delete_register(key, record_id)
    return {"ok": True}


@app.post("/api/business/bookings")
async def add_booking(request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    row = BIZ.upsert_booking(body)
    return {"ok": True, "row": row}


@app.put("/api/business/bookings/{record_id}")
async def update_booking(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    body["id"] = record_id
    row = BIZ.upsert_booking(body)
    return {"ok": True, "row": row}


@app.post("/api/business/bookings/{record_id}/pay")
async def pay_booking(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    try:
        row = BIZ.mark_booking_paid(record_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "row": row}


@app.delete("/api/business/bookings/{record_id}")
def delete_booking(record_id: str, request: Request) -> dict[str, Any]:
    _require(request)
    BIZ.delete_booking(record_id)
    return {"ok": True}


@app.post("/api/business/bookings/import")
async def import_bookings(
    request: Request,
    file: UploadFile = File(...),
    paid: str = Form("unpaid"),
) -> dict[str, Any]:
    _require(request)
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        rows = parse_workbook(payload, paid_mode=paid)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read Excel: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=400, detail="No RAC bookings found in that file")
    result = BIZ.import_bookings(rows)
    return {"ok": True, **result}


@app.put("/api/business/rates")
async def save_rates(request: Request) -> dict[str, Any]:
    _require(request)
    body = await request.json()
    rates = BIZ.save_rates(body)
    return {"ok": True, "rates": rates}


@app.post("/api/business/zoho")
def init_business_zoho(request: Request) -> dict[str, Any]:
    _require(request)
    try:
        BIZ.initialise_sheet()
    except ZohoSheetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
