from __future__ import annotations

from datetime import date, datetime


def format_inr(amount: float | int | str | None, decimals: bool = True) -> str:
    if amount is None or amount == "":
        amount = 0
    value = float(amount)
    negative = value < 0
    value = abs(round(value, 2))
    whole, frac = f"{value:.2f}".split(".")
    if len(whole) <= 3:
        grouped = whole
    else:
        last3 = whole[-3:]
        rest = whole[:-3]
        parts: list[str] = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        grouped = ",".join(reversed(parts)) + "," + last3
    sign = "-" if negative else ""
    if decimals:
        return f"{sign}₹{grouped}.{frac}"
    return f"{sign}₹{grouped}"


def format_lakhs(amount: float | int | str | None) -> str:
    if amount is None or amount == "":
        amount = 0
    value = float(amount)
    sign = "-" if value < 0 else ""
    return f"{sign}₹{abs(value) / 100_000:.2f} L"


def parse_date(value: str | date | datetime | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().date()
        except Exception:
            pass
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%b-%y",
        "%d-%b-%Y",
        "%d/%b/%y",
        "%d/%b/%Y",
        "%d-%B-%y",
        "%d-%B-%Y",
    ):
        try:
            return datetime.strptime(text.replace(" 00:00:00", "")[:18].strip(), fmt).date()
        except ValueError:
            continue
    return None


def iso_date(value: str | date | datetime | None) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else ""


def pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"
