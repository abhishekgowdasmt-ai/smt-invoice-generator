from __future__ import annotations

import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

import pandas as pd

from lib.formatting import iso_date

VEHICLES = ("Sedan", "Ertiga", "Crysta")
PACKAGES = ("4hrs / 40km", "8hrs / 80km", "12hrs / 120km", "Airport", "Outstation", "Drop", "Custom")
PACKAGE_DUTY = {
    "4hrs / 40km": (4, 40),
    "8hrs / 80km": (8, 80),
    "12hrs / 120km": (12, 120),
}
HOURS_CHOICES = list(range(1, 17))
KMS_CHOICES = list(range(10, 410, 10))
HEADER_MARKERS = {"SL NO", "SLNO", "BOOKING ID", "BOOKINGID"}


def default_rates() -> dict[str, dict[str, float]]:
    keys = ["4-40", "8-80", "12-120", "Airport", "Outstation", "Drop"]
    return {vehicle: {key: 0.0 for key in keys} for vehicle in VEHICLES}


def normalize_vehicle(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text or text in {"CAB TYPE", "CABTYPE"}:
        return ""
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        return ""
    if "CRYST" in text:
        return "Crysta"
    if "ERTIGA" in text:
        return "Ertiga"
    if "SEDAN" in text:
        return "Sedan"
    return ""


def normalize_package(value: Any) -> tuple[str, int, int]:
    text = re.sub(r"[\s\-/]+", "", str(value or "").upper())
    if not text or "DUTY" in text:
        return "Custom", 0, 0
    if "AIRPORT" in text:
        return "Airport", 0, 0
    if "OUT" in text and "STATION" in text.replace("-", ""):
        return "Outstation", 0, 0
    if text == "OUTSTION" or text.startswith("OUTST"):
        return "Outstation", 0, 0
    if text == "DROP":
        return "Drop", 0, 0
    hours_match = re.search(r"(\d{1,2})HRS?", text)
    kms_match = re.search(r"(\d{2,4})KMS?", text)
    hours = int(hours_match.group(1)) if hours_match else 0
    kms = int(kms_match.group(1)) if kms_match else 0
    if hours == 4 and kms in {0, 40}:
        return "4hrs / 40km", 4, 40
    if hours == 8 and kms in {0, 80}:
        return "8hrs / 80km", 8, 80
    if hours == 12 and kms in {0, 120}:
        return "12hrs / 120km", 12, 120
    return "Custom", hours, kms


def rate_amount(rates: dict[str, Any], vehicle: str, package: str, hours: int, kms: int) -> float:
    table = rates.get(vehicle) or {}
    named = {
        "4hrs / 40km": "4-40",
        "8hrs / 80km": "8-80",
        "12hrs / 120km": "12-120",
        "Airport": "Airport",
        "Outstation": "Outstation",
        "Drop": "Drop",
    }
    key = named.get(package) or f"{hours}-{kms}"
    try:
        return float(table.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_clock(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    text = str(value).strip().upper().replace(" ", "")
    if not text or text in {"-", "NAN", "NONE"}:
        return ""
    text = text.replace(".", ":")
    meridiem = ""
    if text.endswith("AM") or text.endswith("PM"):
        meridiem = text[-2:]
        text = text[:-2]
    text = re.sub(r"[^0-9:]", "", text)
    parts = [part for part in text.split(":") if part != ""]
    if not parts:
        return ""
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return ""
    if meridiem == "PM" and hour < 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def booking_due(row: dict[str, Any]) -> datetime | None:
    day = iso_date(row.get("date"))
    if not day:
        return None
    clock = parse_clock(row.get("pickup_time")) or "00:00"
    try:
        start = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return start + timedelta(hours=48)


def sla_status(row: dict[str, Any], now: datetime | None = None) -> str:
    if str(row.get("sla") or "") == "historical":
        return "historical"
    due = booking_due(row)
    if due is None:
        return "unknown"
    paid = str(row.get("paid_at") or "").strip()
    if paid:
        try:
            paid_dt = datetime.fromisoformat(paid[:19])
        except ValueError:
            try:
                paid_dt = datetime.strptime(paid[:10], "%Y-%m-%d")
            except ValueError:
                return "unknown"
        return "on_time" if paid_dt <= due else "late"
    current = now or datetime.now()
    return "overdue" if current > due else "pending"


def parse_workbook(payload: bytes, paid_mode: str = "unpaid") -> list[dict[str, Any]]:
    book = pd.ExcelFile(BytesIO(payload))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sheet in book.sheet_names:
        frame = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object)
        header_index = _header_row(frame)
        if header_index is None:
            continue
        mapped = _map_columns(frame.iloc[header_index].tolist())
        for raw in frame.iloc[header_index + 1 :].itertuples(index=False, name=None):
            row = _row_from_excel(raw, mapped, paid_mode)
            if not row:
                continue
            key = str(row.get("booking_id") or "").strip().upper()
            if key:
                if key in seen:
                    continue
                seen.add(key)
            rows.append(row)
    return rows


def _header_row(frame: pd.DataFrame) -> int | None:
    for index, raw in enumerate(frame.itertuples(index=False, name=None)):
        cells = {re.sub(r"\s+", "", str(cell or "")).upper() for cell in raw[:8]}
        if cells & HEADER_MARKERS:
            return index
    return None


def _map_columns(headers: list[Any]) -> dict[str, int]:
    mapped: dict[str, int] = {}
    aliases = {
        "booking_id": ("BOOKINGID", "BOOKING ID"),
        "date": ("DATE",),
        "driver": ("NAME", "DRIVER", "DRIVERNAME"),
        "cab_reg": ("CABREGNO", "CAB REG NO", "VEHICLE"),
        "mobile": ("MOBILNO", "MOBILE", "MOBIL NO"),
        "pickup": ("PLANDSTART", "PLAND START", "START", "PICKUP"),
        "route": ("ENDLOACTION", "END LOCATION", "ROUTE"),
        "pickup_time": ("PICKUPTIME", "PICKUP TIME"),
        "end_time": ("ENDTIME", "END TIME"),
        "hours_actual": ("TOTALHRSSMT", "TOTAL HRS SMT"),
        "vehicle": ("CABTYPE", "CAB TYPE"),
        "employee": ("EMPNAME", "EMP NAME"),
        "start_km": ("STARTKM", "START KM"),
        "end_km": ("ENDKM", "END KM"),
        "kms": ("SMTTOTALKM", "SMT TOTAL KM", "TOTAL KM"),
        "duty": ("DUTYTYPE", "DUTY TYPE"),
        "toll": ("TOLL",),
        "parking": ("PARKING",),
    }
    normalized = [re.sub(r"\s+", "", str(cell or "")).upper() for cell in headers]
    for key, names in aliases.items():
        want = {re.sub(r"\s+", "", name).upper() for name in names}
        for index, label in enumerate(normalized):
            if label in want:
                mapped[key] = index
                break
    return mapped


def _cell(raw: tuple[Any, ...], mapped: dict[str, int], key: str) -> Any:
    index = mapped.get(key)
    if index is None or index >= len(raw):
        return ""
    value = raw[index]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return value


def _number(value: Any) -> str:
    text = str(value or "").replace(",", "").strip()
    if not text or text.upper() in {"NAN", "C", "-", "NONE"}:
        return "0"
    try:
        return f"{float(text):.2f}"
    except ValueError:
        return "0"


def _row_from_excel(raw: tuple[Any, ...], mapped: dict[str, int], paid_mode: str) -> dict[str, Any] | None:
    booking_id = str(_cell(raw, mapped, "booking_id") or "").strip()
    driver = str(_cell(raw, mapped, "driver") or "").strip()
    date_value = iso_date(_cell(raw, mapped, "date"))
    vehicle = normalize_vehicle(_cell(raw, mapped, "vehicle"))
    if str(booking_id).upper() in HEADER_MARKERS or driver.upper() in {"NAME", "DRIVER"}:
        return None
    if not date_value or (not driver and not booking_id):
        return None
    if not vehicle and not booking_id:
        return None
    package, hours, kms_pkg = normalize_package(_cell(raw, mapped, "duty"))
    actual_kms = int(float(_number(_cell(raw, mapped, "kms"))))
    duty_kms = kms_pkg or actual_kms
    if duty_kms and duty_kms % 10:
        duty_kms = int(round(duty_kms / 10.0) * 10)
    row = {
        "booking_id": booking_id,
        "date": date_value,
        "driver": driver,
        "cab_reg": str(_cell(raw, mapped, "cab_reg") or "").strip(),
        "mobile": str(_cell(raw, mapped, "mobile") or "").strip(),
        "pickup": str(_cell(raw, mapped, "pickup") or "").strip(),
        "route": str(_cell(raw, mapped, "route") or "").strip(),
        "pickup_time": parse_clock(_cell(raw, mapped, "pickup_time")),
        "end_time": str(_cell(raw, mapped, "end_time") or "").strip(),
        "hours_actual": str(_cell(raw, mapped, "hours_actual") or "").strip(),
        "vehicle": vehicle or "Sedan",
        "employee": str(_cell(raw, mapped, "employee") or "").strip(),
        "kms": str(actual_kms or duty_kms or 0),
        "duty_hours": str(hours or 0),
        "duty_kms": str(duty_kms or 0),
        "package": package,
        "toll": _number(_cell(raw, mapped, "toll")),
        "parking": _number(_cell(raw, mapped, "parking")),
        "amount": "0",
        "paid_at": "",
        "mode": "",
        "notes": "",
        "sla": "",
    }
    if paid_mode == "paid":
        row["paid_at"] = date_value
        row["sla"] = "historical"
    return row
