from __future__ import annotations

from typing import Any

import pandas as pd

from lib.formatting import format_inr, format_lakhs, pct
from lib.ledger import (
    category_breakdown,
    estimated_interest,
    monthly_flow,
    parse_facility_date,
    snapshot,
    with_running_balance,
)
from lib.storage import LedgerStore


def frame_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for _, row in frame.iterrows():
        item = {
            "id": str(row.get("id", "")),
            "date": row["date"].strftime("%Y-%m-%d") if pd.notna(row.get("date")) else "",
            "type": str(row.get("type", "")),
            "amount": float(row.get("amount") or 0),
            "category": str(row.get("category") or ""),
            "counterparty": str(row.get("counterparty") or ""),
            "purpose": str(row.get("purpose") or ""),
            "mode": str(row.get("mode") or ""),
            "reference": str(row.get("reference") or ""),
            "project": str(row.get("project") or ""),
            "notes": str(row.get("notes") or ""),
            "created_at": str(row.get("created_at") or ""),
        }
        if "outstanding" in row and pd.notna(row["outstanding"]):
            item["outstanding"] = float(row["outstanding"])
            item["signed"] = float(row.get("signed") or 0)
        rows.append(item)
    return rows


def overview_payload(store: LedgerStore) -> dict[str, Any]:
    facility = store.facility()
    rows = store.transactions()
    state = snapshot(facility, rows)
    sanction = parse_facility_date(facility)
    interest = estimated_interest(state["frame"], state["opening"], state["rate"], start=sanction)
    balanced = with_running_balance(state["frame"], state["opening"])
    cats = category_breakdown(state["frame"])
    months = monthly_flow(state["frame"])
    return {
        "facility": facility,
        "storage": store.backend,
        "snapshot": {
            "limit": state["limit"],
            "opening": state["opening"],
            "rate": state["rate"],
            "outstanding": state["outstanding"],
            "available": state["available"],
            "utilization": state["utilization"],
            "drawdowns_month": state["drawdowns_month"],
            "credits_month": state["credits_month"],
            "interest_month": state["interest_month"],
            "charges_month": state["charges_month"],
            "drawdowns_all": state["drawdowns_all"],
            "credits_all": state["credits_all"],
            "interest_all": state["interest_all"],
            "charges_all": state["charges_all"],
            "txn_count": state["txn_count"],
            "labels": {
                "limit": format_inr(state["limit"]),
                "outstanding": format_inr(state["outstanding"]),
                "available": format_inr(state["available"]),
                "limit_l": format_lakhs(state["limit"]),
                "outstanding_l": format_lakhs(state["outstanding"]),
                "utilization": pct(state["utilization"]),
            },
        },
        "interest": {
            "estimated": interest["interest"],
            "average_outstanding": interest["average_outstanding"],
            "days": interest["days"],
            "labels": {
                "estimated": format_inr(interest["interest"]),
                "average": format_inr(interest["average_outstanding"]),
            },
        },
        "transactions": frame_rows(balanced),
        "categories": store.categories(),
        "breakdown": cats.to_dict(orient="records") if not cats.empty else [],
        "monthly": months.to_dict(orient="records") if not months.empty else [],
        "series": [
            {
                "date": row["date"].strftime("%Y-%m-%d") if pd.notna(row["date"]) else "",
                "outstanding": float(row["outstanding"]),
            }
            for _, row in balanced.iterrows()
            if pd.notna(row.get("date"))
        ],
    }
