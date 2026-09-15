from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from lib.business import SMT_COLUMNS, SMT_SHEET
from lib.rac import default_rates, rate_amount, sla_status
from lib.formatting import iso_date
from lib.storage import DATA_DIR
from lib.zoho_sheet import ZohoSheetClient, ZohoSheetError, zoho_is_configured

LOCAL_FILE = DATA_DIR / "business.json"


def empty_business() -> dict[str, Any]:
    return {
        "entries": [],
        "partners": [],
        "loans": [],
        "cards": [],
        "bookings": [],
        "rates": default_rates(),
    }


class BusinessStore:
    def __init__(self) -> None:
        self.backend = "zoho" if zoho_is_configured() else "local"
        self.client = ZohoSheetClient() if self.backend == "zoho" else None
        self._cache: dict[str, Any] | None = None

    def load(self, force: bool = False) -> dict[str, Any]:
        if self._cache is not None and not force:
            return self._cache
        local = _read()
        bookings = list(local.get("bookings") or [])
        rates = local.get("rates") or default_rates()
        if self.backend == "zoho" and self.client:
            try:
                names = {item.lower() for item in self.client.worksheet_names()}
                if SMT_SHEET.lower() in names:
                    remote = self._from_zoho()
                    if _has_rows(remote) or not _has_rows(local):
                        remote["bookings"] = bookings
                        remote["rates"] = rates or default_rates()
                        local = remote
                        _write(local)
                    else:
                        self._rewrite_zoho(local)
            except ZohoSheetError:
                local["_zoho_error"] = True
        local["bookings"] = bookings
        local["rates"] = rates or default_rates()
        self._cache = local
        return self._cache

    def add_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = _entry(payload)
        data = self.load()
        data["entries"].append(row)
        self._persist(data)
        return row

    def update_entry(self, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = _entry(payload, record_id)
        data = self.load()
        data["entries"] = [row if item.get("id") == record_id else item for item in data["entries"]]
        self._persist(data)
        return row

    def delete_entry(self, record_id: str) -> None:
        data = self.load()
        data["entries"] = [item for item in data["entries"] if item.get("id") != record_id]
        self._persist(data)

    def save_register(self, key: str, rows: list[dict[str, Any]]) -> None:
        if key not in {"partners", "loans", "cards"}:
            raise ValueError("Unknown register")
        data = self.load()
        data[key] = [_register(key, item) for item in rows]
        self._persist(data)

    def upsert_register(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = _register(key, payload)
        data = self.load()
        items = list(data.get(key) or [])
        found = False
        for index, item in enumerate(items):
            if item.get("id") == row["id"]:
                items[index] = row
                found = True
                break
        if not found:
            items.append(row)
        data[key] = items
        self._persist(data)
        return row

    def delete_register(self, key: str, record_id: str) -> None:
        data = self.load()
        data[key] = [item for item in data.get(key) or [] if item.get("id") != record_id]
        self._persist(data)

    def upsert_booking(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = _booking(payload)
        data = self.load()
        items = list(data.get("bookings") or [])
        found = False
        for index, item in enumerate(items):
            same_id = item.get("id") == row["id"]
            same_ref = row.get("booking_id") and item.get("booking_id") == row["booking_id"]
            if same_id or same_ref:
                keep_pay = {k: item.get(k) for k in ("amount", "paid_at", "mode", "notes", "sla") if not payload.get(k)}
                items[index] = {**row, **{k: v for k, v in keep_pay.items() if v}}
                row = items[index]
                found = True
                break
        if not found:
            items.append(row)
        data["bookings"] = items
        self._persist(data)
        return row

    def delete_booking(self, record_id: str) -> None:
        data = self.load()
        data["bookings"] = [item for item in data.get("bookings") or [] if item.get("id") != record_id]
        self._persist(data)

    def import_bookings(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        data = self.load()
        existing = {str(item.get("booking_id") or "").strip().upper(): item for item in data.get("bookings") or [] if item.get("booking_id")}
        added = 0
        skipped = 0
        merged = list(data.get("bookings") or [])
        for payload in rows:
            key = str(payload.get("booking_id") or "").strip().upper()
            if key and key in existing:
                skipped += 1
                continue
            row = _booking(payload)
            if key:
                existing[key] = row
            merged.append(row)
            added += 1
        data["bookings"] = merged
        self._persist(data)
        return {"imported": added, "skipped": skipped, "total": len(merged)}

    def save_rates(self, payload: dict[str, Any]) -> dict[str, Any]:
        rates = default_rates()
        incoming = payload.get("rates") if "rates" in payload else payload
        for vehicle, table in (incoming or {}).items():
            if vehicle not in rates or not isinstance(table, dict):
                continue
            for key, value in table.items():
                try:
                    rates[vehicle][str(key)] = float(value or 0)
                except (TypeError, ValueError):
                    rates[vehicle][str(key)] = 0.0
        data = self.load()
        data["rates"] = rates
        self._persist(data)
        return rates

    def mark_booking_paid(self, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        updated = None
        for index, item in enumerate(data.get("bookings") or []):
            if item.get("id") != record_id:
                continue
            item = dict(item)
            if payload.get("amount") not in (None, ""):
                item["amount"] = f"{float(str(payload.get('amount')).replace(',', '') or 0):.2f}"
            elif float(item.get("amount") or 0) <= 0:
                item["amount"] = f"{rate_amount(data.get('rates') or {}, item.get('vehicle') or '', item.get('package') or '', int(float(item.get('duty_hours') or 0)), int(float(item.get('duty_kms') or 0))):.2f}"
            item["paid_at"] = str(payload.get("paid_at") or datetime.now().isoformat(timespec="minutes"))
            item["mode"] = str(payload.get("mode") or item.get("mode") or "UPI")
            item["sla"] = sla_status(item)
            data["bookings"][index] = item
            updated = item
            break
        if updated is None:
            raise ValueError("Booking not found")
        self._persist(data)
        return updated

    def initialise_sheet(self) -> None:
        if not self.client:
            raise ZohoSheetError("Zoho is not configured.")
        names = {item.lower() for item in self.client.worksheet_names()}
        if SMT_SHEET.lower() not in names:
            self.client.create_worksheet(SMT_SHEET)
            names = {item.lower() for item in self.client.worksheet_names()}
        if SMT_SHEET.lower() not in names:
            raise ZohoSheetError(
                f'Create a worksheet named "{SMT_SHEET}" in Zoho Sheet, then tap initialise again.'
            )
        self.client.write_headers(SMT_SHEET, SMT_COLUMNS)
        current = _read()
        existing = self.client.fetch_records(SMT_SHEET)
        if not existing:
            rows = _flatten(current)
            if rows:
                self.client.add_records(SMT_SHEET, rows)
        self._cache = None

    def _persist(self, data: dict[str, Any]) -> None:
        _write(data)
        self._cache = data
        if self.backend == "zoho" and self.client:
            try:
                names = {item.lower() for item in self.client.worksheet_names()}
                if SMT_SHEET.lower() not in names:
                    return
                self._rewrite_zoho(data)
            except ZohoSheetError:
                pass

    def _from_zoho(self) -> dict[str, Any]:
        assert self.client is not None
        rows = self.client.fetch_records(SMT_SHEET)
        store = empty_business()
        for row in rows:
            kind = str(row.get("kind") or "expense")
            if kind in {"partner", "loan", "card"}:
                key = {"partner": "partners", "loan": "loans", "card": "cards"}[kind]
                store[key].append(_register(key, {**row, **_parse_extra(row.get("extra"))}))
            else:
                store["entries"].append(_entry(row, row.get("id")))
        return store

    def _rewrite_zoho(self, data: dict[str, Any]) -> None:
        assert self.client is not None
        existing = self.client.fetch_records(SMT_SHEET)
        for row in existing:
            ident = row.get("id")
            if ident:
                try:
                    self.client.delete_record(SMT_SHEET, str(ident))
                except ZohoSheetError:
                    continue
        rows = _flatten(data)
        if rows:
            self.client.add_records(SMT_SHEET, rows)


def _entry(payload: dict[str, Any], record_id: str | None = None) -> dict[str, Any]:
    return {
        "id": str(record_id or payload.get("id") or uuid4()),
        "kind": str(payload.get("kind") or "expense"),
        "date": iso_date(payload.get("date")) or datetime.now().date().isoformat(),
        "amount": f"{float(str(payload.get('amount') or 0).replace(',', '') or 0):.2f}",
        "stream": str(payload.get("stream") or ""),
        "category": str(payload.get("category") or ""),
        "party": str(payload.get("party") or ""),
        "vehicle": str(payload.get("vehicle") or ""),
        "reference": str(payload.get("reference") or ""),
        "mode": str(payload.get("mode") or ""),
        "notes": str(payload.get("notes") or ""),
        "extra": str(payload.get("extra") or ""),
        "created_at": str(payload.get("created_at") or datetime.now().isoformat(timespec="seconds")),
    }


def _booking(payload: dict[str, Any]) -> dict[str, Any]:
    hours = str(payload.get("duty_hours") or "0")
    kms = str(payload.get("duty_kms") or payload.get("kms") or "0")
    return {
        "id": str(payload.get("id") or uuid4()),
        "booking_id": str(payload.get("booking_id") or "").strip(),
        "date": iso_date(payload.get("date")) or datetime.now().date().isoformat(),
        "driver": str(payload.get("driver") or payload.get("party") or "").strip(),
        "cab_reg": str(payload.get("cab_reg") or "").strip(),
        "mobile": str(payload.get("mobile") or "").strip(),
        "pickup": str(payload.get("pickup") or "").strip(),
        "route": str(payload.get("route") or "").strip(),
        "pickup_time": str(payload.get("pickup_time") or "").strip(),
        "end_time": str(payload.get("end_time") or "").strip(),
        "hours_actual": str(payload.get("hours_actual") or "").strip(),
        "vehicle": str(payload.get("vehicle") or "Sedan"),
        "employee": str(payload.get("employee") or "").strip(),
        "kms": str(payload.get("kms") or kms),
        "duty_hours": hours,
        "duty_kms": kms,
        "package": str(payload.get("package") or "Custom"),
        "toll": f"{float(str(payload.get('toll') or 0).replace(',', '') or 0):.2f}",
        "parking": f"{float(str(payload.get('parking') or 0).replace(',', '') or 0):.2f}",
        "amount": f"{float(str(payload.get('amount') or 0).replace(',', '') or 0):.2f}",
        "paid_at": str(payload.get("paid_at") or ""),
        "mode": str(payload.get("mode") or ""),
        "notes": str(payload.get("notes") or ""),
        "sla": str(payload.get("sla") or sla_status(payload)),
        "created_at": str(payload.get("created_at") or datetime.now().isoformat(timespec="seconds")),
    }


def _register(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    base = {
        "id": str(payload.get("id") or uuid4()),
        "name": str(payload.get("name") or ""),
        "notes": str(payload.get("notes") or ""),
    }
    if key == "partners":
        base["share_pct"] = str(payload.get("share_pct") or "0")
    if key == "loans":
        base.update(
            {
                "lender": str(payload.get("lender") or ""),
                "principal": str(payload.get("principal") or "0"),
                "emi": str(payload.get("emi") or "0"),
                "outstanding": str(payload.get("outstanding") or "0"),
            }
        )
    if key == "cards":
        base.update(
            {
                "last4": str(payload.get("last4") or ""),
                "limit": str(payload.get("limit") or "0"),
                "outstanding": str(payload.get("outstanding") or "0"),
            }
        )
    return base


def _flatten(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_entry(item, item.get("id")) for item in data.get("entries") or []]
    for partner in data.get("partners") or []:
        rows.append(
            _entry(
                {
                    **partner,
                    "kind": "partner",
                    "party": partner.get("name"),
                    "extra": json.dumps({"share_pct": partner.get("share_pct")}),
                    "amount": 0,
                    "date": datetime.now().date().isoformat(),
                },
                partner.get("id"),
            )
        )
    for loan in data.get("loans") or []:
        rows.append(
            _entry(
                {
                    **loan,
                    "kind": "loan",
                    "party": loan.get("name"),
                    "amount": loan.get("outstanding") or 0,
                    "extra": json.dumps(
                        {
                            "lender": loan.get("lender"),
                            "principal": loan.get("principal"),
                            "emi": loan.get("emi"),
                            "outstanding": loan.get("outstanding"),
                        }
                    ),
                    "date": datetime.now().date().isoformat(),
                },
                loan.get("id"),
            )
        )
    for card in data.get("cards") or []:
        rows.append(
            _entry(
                {
                    **card,
                    "kind": "card",
                    "party": card.get("name"),
                    "amount": card.get("outstanding") or 0,
                    "extra": json.dumps(
                        {
                            "last4": card.get("last4"),
                            "limit": card.get("limit"),
                            "outstanding": card.get("outstanding"),
                        }
                    ),
                    "date": datetime.now().date().isoformat(),
                },
                card.get("id"),
            )
        )
    return rows


def _parse_extra(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(str(raw))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _has_rows(store: dict[str, Any]) -> bool:
    return any(store.get(key) for key in ("entries", "partners", "loans", "cards"))


def _read() -> dict[str, Any]:
    if not LOCAL_FILE.exists():
        store = empty_business()
        _write(store)
        return store
    try:
        payload = json.loads(LOCAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = empty_business()
    store = empty_business()
    store["entries"] = payload.get("entries") or []
    store["partners"] = payload.get("partners") or []
    store["loans"] = payload.get("loans") or []
    store["cards"] = payload.get("cards") or []
    store["bookings"] = payload.get("bookings") or []
    store["rates"] = payload.get("rates") or default_rates()
    return store


def _write(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_FILE.write_text(
        json.dumps(
            {
                "entries": store.get("entries") or [],
                "partners": store.get("partners") or [],
                "loans": store.get("loans") or [],
                "cards": store.get("cards") or [],
                "bookings": store.get("bookings") or [],
                "rates": store.get("rates") or default_rates(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
