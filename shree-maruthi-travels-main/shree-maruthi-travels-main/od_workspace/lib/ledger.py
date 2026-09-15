from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from lib.constants import CREDIT_TYPES, DEFAULT_FACILITY, DRAW_TYPES
from lib.formatting import parse_date


def facility_number(facility: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = facility.get(key, DEFAULT_FACILITY.get(key, default))
    try:
        return float(str(raw).replace(",", "").strip() or default)
    except ValueError:
        return default


def transactions_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "id",
                "date",
                "type",
                "amount",
                "category",
                "counterparty",
                "purpose",
                "mode",
                "reference",
                "project",
                "notes",
                "created_at",
            ]
        )
    frame = pd.DataFrame(rows)
    frame["amount"] = pd.to_numeric(frame.get("amount", 0), errors="coerce").fillna(0.0)
    frame["date"] = pd.to_datetime(frame.get("date"), errors="coerce")
    frame = frame.sort_values(["date", "created_at"], ascending=True, kind="mergesort")
    return frame.reset_index(drop=True)


def signed_amount(txn_type: str, amount: float) -> float:
    value = abs(float(amount))
    if txn_type in CREDIT_TYPES:
        return -value
    if txn_type == "Adjustment":
        return float(amount)
    return value


def with_running_balance(frame: pd.DataFrame, opening: float = 0.0) -> pd.DataFrame:
    if frame.empty:
        out = frame.copy()
        out["signed"] = pd.Series(dtype=float)
        out["outstanding"] = pd.Series(dtype=float)
        return out
    out = frame.copy()
    out["signed"] = [
        signed_amount(str(row["type"]), float(row["amount"])) for _, row in out.iterrows()
    ]
    out["outstanding"] = opening + out["signed"].cumsum()
    return out


def current_outstanding(frame: pd.DataFrame, opening: float = 0.0) -> float:
    if frame.empty:
        return float(opening)
    balanced = with_running_balance(frame, opening)
    return float(balanced["outstanding"].iloc[-1])


def snapshot(facility: dict[str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    limit = facility_number(facility, "limit", 9_900_000)
    opening = facility_number(facility, "opening_outstanding", 0)
    rate = facility_number(facility, "rate", 0)
    frame = transactions_frame(rows)
    outstanding = current_outstanding(frame, opening)
    available = limit - outstanding
    utilization = (outstanding / limit * 100) if limit else 0.0

    today = date.today()
    month_start = today.replace(day=1)
    dated = frame.copy()
    if not dated.empty:
        dated["date_only"] = dated["date"].dt.date
        this_month = dated[dated["date_only"] >= month_start]
    else:
        this_month = dated

    def _sum(subset: pd.DataFrame, types: set[str]) -> float:
        if subset.empty:
            return 0.0
        return float(subset.loc[subset["type"].isin(types), "amount"].abs().sum())

    return {
        "limit": limit,
        "opening": opening,
        "rate": rate,
        "outstanding": outstanding,
        "available": available,
        "utilization": utilization,
        "drawdowns_month": _sum(this_month, {"Drawdown"}),
        "credits_month": _sum(this_month, CREDIT_TYPES),
        "interest_month": _sum(this_month, {"Interest"}),
        "charges_month": _sum(this_month, {"Charge"}),
        "drawdowns_all": _sum(frame, {"Drawdown"}),
        "credits_all": _sum(frame, CREDIT_TYPES),
        "interest_all": _sum(frame, {"Interest"}),
        "charges_all": _sum(frame, {"Charge"}),
        "txn_count": int(len(frame)),
        "frame": frame,
    }


def daily_balances(
    frame: pd.DataFrame,
    opening: float,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    end = end or date.today()
    if frame.empty and start is None:
        start = end
    if not frame.empty:
        first = frame["date"].min()
        first_date = first.date() if pd.notna(first) else end
    else:
        first_date = end
    start = start or first_date
    if start > end:
        start, end = end, start

    balanced = with_running_balance(frame, opening)
    last = opening
    events: dict[date, float] = {}
    if not balanced.empty:
        for _, row in balanced.iterrows():
            if pd.isna(row["date"]):
                continue
            day = row["date"].date()
            value = float(row["outstanding"])
            if day < start:
                last = value
            elif day <= end:
                events[day] = value

    rows = []
    cursor = start
    while cursor <= end:
        if cursor in events:
            last = events[cursor]
        rows.append({"date": cursor, "outstanding": last})
        cursor += timedelta(days=1)
    return pd.DataFrame(rows)


def estimated_interest(
    frame: pd.DataFrame,
    opening: float,
    annual_rate: float,
    start: date | None = None,
    end: date | None = None,
    year_days: int = 365,
) -> dict[str, Any]:
    daily = daily_balances(frame, opening, start, end)
    if daily.empty or annual_rate <= 0:
        return {
            "days": 0,
            "average_outstanding": 0.0,
            "interest": 0.0,
            "daily": daily,
        }
    daily["interest"] = daily["outstanding"].clip(lower=0) * (annual_rate / 100) / year_days
    return {
        "days": int(len(daily)),
        "average_outstanding": float(daily["outstanding"].clip(lower=0).mean()),
        "interest": float(daily["interest"].sum()),
        "daily": daily,
    }


def category_breakdown(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "drawdown", "credit", "net"])
    work = frame.copy()
    work["category"] = work["category"].replace("", "Uncategorised").fillna("Uncategorised")
    work["drawdown"] = [
        abs(float(a)) if t not in CREDIT_TYPES else 0.0
        for t, a in zip(work["type"], work["amount"])
    ]
    work["credit"] = [
        abs(float(a)) if t in CREDIT_TYPES else 0.0
        for t, a in zip(work["type"], work["amount"])
    ]
    grouped = work.groupby("category", as_index=False)[["drawdown", "credit"]].sum()
    grouped["net"] = grouped["drawdown"] - grouped["credit"]
    return grouped.sort_values("drawdown", ascending=False)


def monthly_flow(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["month", "drawdown", "credit", "interest", "net"])
    work = frame.dropna(subset=["date"]).copy()
    work["month"] = work["date"].dt.to_period("M").astype(str)
    rows = []
    for month, part in work.groupby("month"):
        drawdown = float(part.loc[part["type"].isin(DRAW_TYPES), "amount"].abs().sum())
        credit = float(part.loc[part["type"].isin(CREDIT_TYPES), "amount"].abs().sum())
        interest = float(part.loc[part["type"] == "Interest", "amount"].abs().sum())
        rows.append(
            {
                "month": month,
                "drawdown": drawdown,
                "credit": credit,
                "interest": interest,
                "net": drawdown - credit,
            }
        )
    return pd.DataFrame(rows)


def parse_facility_date(facility: dict[str, str]) -> date | None:
    return parse_date(facility.get("sanction_date", ""))
