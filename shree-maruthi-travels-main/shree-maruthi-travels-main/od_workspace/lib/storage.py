from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from lib.constants import (
    CATEGORY_COLUMNS,
    DEFAULT_CATEGORIES,
    DEFAULT_FACILITY,
    FACILITY_COLUMNS,
    SHEET_CATEGORIES,
    SHEET_FACILITY,
    SHEET_TRANSACTIONS,
    TXN_COLUMNS,
)
from lib.formatting import iso_date
from lib.zoho_sheet import ZohoSheetClient, ZohoSheetError, zoho_is_configured

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCAL_FILE = DATA_DIR / "ledger.json"


def empty_store() -> dict[str, Any]:
    return {
        "facility": dict(DEFAULT_FACILITY),
        "transactions": [],
        "categories": list(DEFAULT_CATEGORIES),
    }


class LedgerStore:
    def __init__(self) -> None:
        self.backend = "zoho" if zoho_is_configured() else "local"
        self.client = ZohoSheetClient() if self.backend == "zoho" else None
        self._cache: dict[str, Any] | None = None

    def load(self, force: bool = False) -> dict[str, Any]:
        if self._cache is not None and not force:
            return self._cache
        if self.backend == "zoho":
            try:
                self._cache = self._load_zoho()
            except ZohoSheetError:
                local = _read_local()
                local["_zoho_error"] = True
                self._cache = local
        else:
            self._cache = _read_local()
        return self._cache

    def facility(self) -> dict[str, str]:
        data = self.load()
        merged = dict(DEFAULT_FACILITY)
        merged.update({k: str(v) for k, v in data.get("facility", {}).items()})
        return merged

    def transactions(self) -> list[dict[str, Any]]:
        return list(self.load().get("transactions", []))

    def categories(self) -> list[str]:
        values = [str(item).strip() for item in self.load().get("categories", []) if str(item).strip()]
        return values or list(DEFAULT_CATEGORIES)

    def save_facility(self, facility: dict[str, Any]) -> None:
        clean = {k: str(v) for k, v in {**DEFAULT_FACILITY, **facility}.items()}
        row = {"id": "facility", **clean}
        if self.backend == "zoho" and self.client:
            try:
                existing = self.client.fetch_records(SHEET_FACILITY)
                if existing:
                    self.client.update_record(SHEET_FACILITY, "facility", row)
                else:
                    self.client.add_records(SHEET_FACILITY, [row])
            except ZohoSheetError:
                pass
        data = self.load()
        data["facility"] = clean
        _write_local(data)
        self._cache = data

    def add_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = _normalise_txn(payload)
        if self.backend == "zoho" and self.client:
            self.client.add_records(SHEET_TRANSACTIONS, [row])
        data = self.load()
        data["transactions"].append(row)
        _write_local(data)
        self._cache = data
        return row

    def update_transaction(self, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = _normalise_txn(payload, record_id=record_id)
        if self.backend == "zoho" and self.client:
            self.client.update_record(SHEET_TRANSACTIONS, record_id, row)
        data = self.load()
        data["transactions"] = [
            row if item.get("id") == record_id else item for item in data["transactions"]
        ]
        _write_local(data)
        self._cache = data
        return row

    def delete_transaction(self, record_id: str) -> None:
        if self.backend == "zoho" and self.client:
            self.client.delete_record(SHEET_TRANSACTIONS, record_id)
        data = self.load()
        data["transactions"] = [item for item in data["transactions"] if item.get("id") != record_id]
        _write_local(data)
        self._cache = data

    def save_categories(self, categories: list[str]) -> None:
        clean = [item.strip() for item in categories if item.strip()]
        rows = [{"id": name.lower().replace(" ", "_"), "name": name} for name in clean]
        if self.backend == "zoho" and self.client:
            try:
                self._rewrite_simple(SHEET_CATEGORIES, rows, CATEGORY_COLUMNS)
            except ZohoSheetError:
                pass
        data = self.load()
        data["categories"] = clean
        _write_local(data)
        self._cache = data

    def initialise_zoho(self) -> None:
        if not self.client:
            raise ZohoSheetError("Zoho is not configured.")
        names = {item.lower() for item in self.client.worksheet_names()}
        for name in (SHEET_TRANSACTIONS, SHEET_FACILITY, SHEET_CATEGORIES):
            if name.lower() not in names:
                self.client.create_worksheet(name)
        names = {item.lower() for item in self.client.worksheet_names()}
        if SHEET_TRANSACTIONS.lower() not in names:
            raise ZohoSheetError(
                f'Open the workbook and keep a worksheet named "{SHEET_TRANSACTIONS}".'
            )
        self.client.write_headers(SHEET_TRANSACTIONS, TXN_COLUMNS)
        current = _read_local()
        if SHEET_FACILITY.lower() in names:
            self.client.write_headers(SHEET_FACILITY, FACILITY_COLUMNS)
            if not self.client.fetch_records(SHEET_FACILITY):
                self.client.add_records(SHEET_FACILITY, [{"id": "facility", **current["facility"]}])
        if SHEET_CATEGORIES.lower() in names:
            self.client.write_headers(SHEET_CATEGORIES, CATEGORY_COLUMNS)
            if not self.client.fetch_records(SHEET_CATEGORIES):
                self.client.add_records(
                    SHEET_CATEGORIES,
                    [
                        {"id": name.lower().replace(" ", "_"), "name": name}
                        for name in current["categories"]
                    ],
                )
        if current["transactions"] and not self.client.fetch_records(SHEET_TRANSACTIONS):
            self.client.add_records(SHEET_TRANSACTIONS, current["transactions"])
        self._cache = None

    def ping(self) -> str:
        if self.backend != "zoho" or not self.client:
            return "local"
        self.client.workbook()
        return "zoho"

    def _load_zoho(self) -> dict[str, Any]:
        assert self.client is not None
        names = {item.lower() for item in self.client.worksheet_names()}
        facility_rows = (
            self.client.fetch_records(SHEET_FACILITY) if SHEET_FACILITY.lower() in names else []
        )
        txn_rows = self.client.fetch_records(SHEET_TRANSACTIONS)
        category_rows = (
            self.client.fetch_records(SHEET_CATEGORIES) if SHEET_CATEGORIES.lower() in names else []
        )
        facility = dict(DEFAULT_FACILITY)
        if facility_rows:
            for key in DEFAULT_FACILITY:
                if key in facility_rows[0] and facility_rows[0][key] not in (None, ""):
                    facility[key] = str(facility_rows[0][key])
        categories = [
            str(row.get("name", "")).strip()
            for row in category_rows
            if str(row.get("name", "")).strip()
        ]
        store = {
            "facility": facility,
            "transactions": [_normalise_txn(row, row.get("id")) for row in txn_rows],
            "categories": categories or list(DEFAULT_CATEGORIES),
        }
        _write_local(store)
        return store

    def _rewrite_simple(self, worksheet: str, rows: list[dict[str, Any]], headers: list[str]) -> None:
        assert self.client is not None
        existing = self.client.fetch_records(worksheet)
        for row in existing:
            ident = row.get("id") or row.get("key") or row.get("name")
            if ident:
                try:
                    self.client.delete_record(worksheet, str(ident))
                except ZohoSheetError:
                    continue
        if rows:
            try:
                self.client.add_records(worksheet, rows)
            except ZohoSheetError:
                self.client.write_headers(worksheet, headers)
                self.client.add_records(worksheet, rows)


def _normalise_txn(payload: dict[str, Any], record_id: str | None = None) -> dict[str, Any]:
    created = payload.get("created_at") or datetime.now().isoformat(timespec="seconds")
    return {
        "id": str(record_id or payload.get("id") or uuid4()),
        "date": iso_date(payload.get("date")) or datetime.now().date().isoformat(),
        "type": str(payload.get("type") or "Drawdown"),
        "amount": f"{float(str(payload.get('amount') or 0).replace(',', '') or 0):.2f}",
        "category": str(payload.get("category") or ""),
        "counterparty": str(payload.get("counterparty") or ""),
        "purpose": str(payload.get("purpose") or ""),
        "mode": str(payload.get("mode") or ""),
        "reference": str(payload.get("reference") or ""),
        "project": str(payload.get("project") or ""),
        "notes": str(payload.get("notes") or ""),
        "created_at": str(created),
    }


def _read_local() -> dict[str, Any]:
    if not LOCAL_FILE.exists():
        store = empty_store()
        _write_local(store)
        return store
    try:
        payload = json.loads(LOCAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = empty_store()
    store = empty_store()
    store["facility"].update(payload.get("facility") or {})
    store["transactions"] = payload.get("transactions") or []
    store["categories"] = payload.get("categories") or list(DEFAULT_CATEGORIES)
    return store


def _write_local(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    persist = {
        "facility": store.get("facility", DEFAULT_FACILITY),
        "transactions": store.get("transactions", []),
        "categories": store.get("categories", DEFAULT_CATEGORIES),
    }
    LOCAL_FILE.write_text(json.dumps(persist, indent=2), encoding="utf-8")
