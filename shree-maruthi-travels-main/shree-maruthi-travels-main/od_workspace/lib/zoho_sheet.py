from __future__ import annotations

import json
import time
from typing import Any

import requests

from lib.config import zoho_config as _zoho_config_values


class ZohoSheetError(RuntimeError):
    pass


class ZohoSheetClient:
    def __init__(self) -> None:
        cfg = _zoho_config()
        self.client_id = cfg["client_id"]
        self.client_secret = cfg["client_secret"]
        self.refresh_token = cfg["refresh_token"]
        self.resource_id = cfg["resource_id"]
        self.accounts_url = cfg["accounts_url"].rstrip("/")
        self.api_base = cfg["api_base"].rstrip("/")
        self._access_token = ""
        self._token_expiry = 0.0

    @property
    def configured(self) -> bool:
        return all(
            [
                self.client_id,
                self.client_secret,
                self.refresh_token,
                self.resource_id,
            ]
        )

    def access_token(self, force: bool = False) -> str:
        if not force and self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        response = requests.post(
            f"{self.accounts_url}/oauth/v2/token",
            data={
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        payload = _safe_json(response)
        if "access_token" not in payload:
            raise ZohoSheetError(
                payload.get("error")
                or payload.get("error_description")
                or f"Could not refresh Zoho token ({response.status_code})."
            )
        self._access_token = payload["access_token"]
        self._token_expiry = time.time() + float(payload.get("expires_in", 3600))
        return self._access_token

    def call(self, method: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise ZohoSheetError("Zoho Sheet credentials are incomplete.")
        data = {"method": method}
        if extra:
            data.update({k: v for k, v in extra.items() if v is not None})
        response = requests.post(
            f"{self.api_base}/{self.resource_id}",
            headers={"Authorization": f"Zoho-oauthtoken {self.access_token()}"},
            data=data,
            timeout=45,
        )
        if response.status_code in {401, 403}:
            response = requests.post(
                f"{self.api_base}/{self.resource_id}",
                headers={"Authorization": f"Zoho-oauthtoken {self.access_token(force=True)}"},
                data=data,
                timeout=45,
            )
        payload = _safe_json(response)
        if payload.get("status") == "failure" or response.status_code >= 400:
            message = (
                payload.get("error_message")
                or payload.get("error")
                or payload.get("message")
                or response.text
                or "Zoho Sheet request failed."
            )
            raise ZohoSheetError(str(message))
        return payload

    def workbook(self) -> dict[str, Any]:
        try:
            return self.call("worksheet.list")
        except ZohoSheetError:
            return self.call("workbook.data.get")

    def worksheet_names(self) -> list[str]:
        payload = self.workbook()
        names: list[str] = []
        raw = (
            payload.get("worksheet_names")
            or payload.get("worksheet_list")
            or payload.get("worksheets")
            or []
        )
        for item in raw:
            if isinstance(item, dict):
                name = item.get("worksheet_name") or item.get("sheet_name") or item.get("name")
                if name:
                    names.append(str(name))
            elif item:
                names.append(str(item))
        return names

    def create_worksheet(self, name: str) -> None:
        existing = {item.lower() for item in self.worksheet_names()}
        if name.lower() in existing:
            return
        try:
            self.call("worksheet.create", {"new_sheet_name": name})
        except ZohoSheetError as exc:
            if "not supported" in str(exc).lower():
                return
            raise

    def write_headers(self, worksheet: str, headers: list[str]) -> None:
        for index, header in enumerate(headers, start=1):
            self.call(
                "cell.content.set",
                {
                    "worksheet_name": worksheet,
                    "row": "1",
                    "column": str(index),
                    "content": header,
                },
            )

    def fetch_records(self, worksheet: str) -> list[dict[str, Any]]:
        payload = self.call(
            "worksheet.records.fetch",
            {"worksheet_name": worksheet, "header_row": "1"},
        )
        records = payload.get("records") or payload.get("data") or []
        if isinstance(records, dict):
            return [records]
        return [row for row in records if isinstance(row, dict)]

    def add_records(self, worksheet: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "worksheet_name": worksheet,
            "header_row": "1",
            "json_data": json.dumps(rows),
        }
        try:
            return self.call("worksheet.records.add", payload)
        except ZohoSheetError:
            payload["cell_data"] = payload.pop("json_data")
            return self.call("worksheet.records.add", payload)

    def update_record(self, worksheet: str, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        extra = {
            "worksheet_name": worksheet,
            "header_row": "1",
            "criteria": f'id="{record_id}"',
            "json_data": json.dumps(values),
        }
        try:
            return self.call("worksheet.records.update", extra)
        except ZohoSheetError:
            extra["cell_data"] = extra.pop("json_data")
            return self.call("worksheet.records.update", extra)

    def delete_record(self, worksheet: str, record_id: str) -> dict[str, Any]:
        try:
            return self.call(
                "worksheet.records.delete",
                {
                    "worksheet_name": worksheet,
                    "header_row": "1",
                    "criteria": f'id="{record_id}"',
                },
            )
        except ZohoSheetError:
            return self.call(
                "tabular_range.records.delete",
                {
                    "worksheet_name": worksheet,
                    "criteria": f'id="{record_id}"',
                },
            )


def _zoho_config() -> dict[str, str]:
    return _zoho_config_values()


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"error": response.text, "status_code": response.status_code}
    if isinstance(payload, dict):
        return payload
    return {"data": payload}


def zoho_is_configured() -> bool:
    cfg = _zoho_config()
    return all(cfg[key] for key in ("client_id", "client_secret", "refresh_token", "resource_id"))
