from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from lib.rac import VEHICLES, sla_status

COMPANY = "Shree Maruthi Travels"

INCOME_STREAMS = (
    "Employee transport",
    "Insurance",
    "RAC",
)

ETS_CATEGORIES = (
    "Driver salary",
    "Diesel advance",
    "Cab EMI",
    "ETS daily pay",
    "ETS other",
)

OTHER_CATEGORIES = (
    "Insurance",
    "Partner payout",
    "Loan payment",
    "Credit card payment",
    "Food / daily",
    "Office / admin",
    "Custom",
)

EXPENSE_CATEGORIES = ETS_CATEGORIES + OTHER_CATEGORIES + ("RAC booking payment",)

DRIVER_CATEGORIES = {"Driver salary", "Diesel advance", "RAC booking payment", "ETS daily pay"}
PAY_MODES = ("UPI", "Cash", "NEFT", "IMPS", "Cheque", "Credit card", "OD", "Other")

ENTRY_KINDS = ("income", "expense", "saving", "note")

SMT_SHEET = "SMT Books"
SMT_COLUMNS = [
    "id",
    "kind",
    "date",
    "amount",
    "stream",
    "category",
    "party",
    "vehicle",
    "reference",
    "mode",
    "notes",
    "extra",
    "created_at",
]


def month_key(value: str | date | None) -> str:
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    text = str(value or "")[:7]
    return text if len(text) == 7 else date.today().strftime("%Y-%m")


def in_month(row: dict[str, Any], month: str) -> bool:
    return month_key(row.get("date")) == month


def money(row: dict[str, Any]) -> float:
    try:
        return float(str(row.get("amount") or 0).replace(",", "") or 0)
    except ValueError:
        return 0.0


def _bucket(row: dict[str, Any]) -> str:
    extra = str(row.get("extra") or "")
    if "ETS" in extra or row.get("stream") == "Employee transport":
        return "ETS"
    if str(row.get("category") or "") in ETS_CATEGORIES:
        return "ETS"
    if str(row.get("category") or "") == "RAC booking payment":
        return "RAC"
    return "Other"


def summarise(store: dict[str, Any], month: str) -> dict[str, Any]:
    entries = store.get("entries") or []
    incomes = [row for row in entries if row.get("kind") == "income" and in_month(row, month)]
    expenses = [row for row in entries if row.get("kind") == "expense" and in_month(row, month)]
    savings = [row for row in entries if row.get("kind") == "saving" and in_month(row, month)]
    bookings = store.get("bookings") or []
    month_bookings = [row for row in bookings if in_month(row, month)]
    paid_bookings = [row for row in month_bookings if str(row.get("paid_at") or "").strip()]

    by_stream: dict[str, float] = defaultdict(float)
    for row in incomes:
        by_stream[str(row.get("stream") or "Other")] += money(row)

    by_category: dict[str, float] = defaultdict(float)
    ets_total = 0.0
    other_total = 0.0
    driver_total = 0.0
    rac_pay = sum(money(row) for row in paid_bookings)
    for row in expenses:
        cat = str(row.get("category") or "Custom")
        amt = money(row)
        by_category[cat] += amt
        if cat == "RAC booking payment":
            continue
        if cat in DRIVER_CATEGORIES:
            driver_total += amt
        if _bucket(row) == "ETS":
            ets_total += amt
        else:
            other_total += amt
    by_category["RAC booking payment"] += rac_pay
    driver_total += rac_pay

    by_driver: dict[str, dict[str, float]] = defaultdict(
        lambda: {"paid": 0.0, "salary": 0.0, "diesel": 0.0, "rac": 0.0}
    )
    for row in expenses:
        cat = str(row.get("category") or "")
        if cat not in DRIVER_CATEGORIES or cat == "RAC booking payment":
            continue
        name = str(row.get("party") or "Unnamed driver")
        amt = money(row)
        by_driver[name]["paid"] += amt
        if cat == "Driver salary":
            by_driver[name]["salary"] += amt
        elif cat == "Diesel advance":
            by_driver[name]["diesel"] += amt
    for row in paid_bookings:
        name = str(row.get("driver") or "Unnamed driver")
        amt = money(row)
        by_driver[name]["paid"] += amt
        by_driver[name]["rac"] += amt

    sla: dict[str, int] = defaultdict(int)
    by_vehicle: dict[str, dict[str, Any]] = {
        vehicle: {"count": 0, "paid": 0.0, "unpaid": 0, "overdue": 0} for vehicle in VEHICLES
    }
    enriched = []
    for row in month_bookings:
        status = sla_status(row)
        item = {**row, "sla": status}
        enriched.append(item)
        sla[status] += 1
        vehicle = str(row.get("vehicle") or "Sedan")
        if vehicle not in by_vehicle:
            by_vehicle[vehicle] = {"count": 0, "paid": 0.0, "unpaid": 0, "overdue": 0}
        by_vehicle[vehicle]["count"] += 1
        if str(row.get("paid_at") or "").strip():
            by_vehicle[vehicle]["paid"] += money(row)
        else:
            by_vehicle[vehicle]["unpaid"] += 1
            if status == "overdue":
                by_vehicle[vehicle]["overdue"] += 1

    by_pot: dict[str, float] = defaultdict(float)
    for row in savings:
        by_pot[str(row.get("category") or "Custom")] += money(row)

    loans = store.get("loans") or []
    cards = store.get("cards") or []
    partners = store.get("partners") or []
    partner_paid: dict[str, float] = defaultdict(float)
    for row in expenses:
        if row.get("category") == "Partner payout":
            partner_paid[str(row.get("party") or "").strip().lower()] += money(row)
    partner_rows = []
    for partner in partners:
        name = str(partner.get("name") or "")
        partner_rows.append({**partner, "paid_month": partner_paid.get(name.strip().lower(), 0.0)})

    income_total = sum(money(row) for row in incomes)
    expense_total = ets_total + other_total + rac_pay
    rac_in = by_stream.get("RAC", 0.0)
    ets_in = by_stream.get("Employee transport", 0.0)
    ins_in = by_stream.get("Insurance", 0.0)

    return {
        "company": COMPANY,
        "month": month,
        "income_total": income_total,
        "expense_total": expense_total,
        "net": income_total - expense_total,
        "savings_total": sum(money(row) for row in savings),
        "income_by_stream": dict(by_stream),
        "expense_by_category": dict(by_category),
        "ets_total": ets_total,
        "other_total": other_total,
        "ets_income": ets_in,
        "insurance_income": ins_in,
        "driver_total": driver_total,
        "rac_income": rac_in,
        "rac_payout": rac_pay,
        "rac_gap": rac_in - rac_pay,
        "rac_sla": dict(sla),
        "rac_vehicles": by_vehicle,
        "bookings": enriched,
        "ets_expenses": [row for row in expenses if _bucket(row) == "ETS"],
        "other_expenses": [row for row in expenses if _bucket(row) == "Other"],
        "drivers": sorted(
            [{"name": name, **paid} for name, paid in by_driver.items()],
            key=lambda item: item["paid"],
            reverse=True,
        ),
        "savings_by_pot": dict(by_pot),
        "partners": partner_rows,
        "loans_outstanding": sum(float(item.get("outstanding") or 0) for item in loans),
        "cards_outstanding": sum(float(item.get("outstanding") or 0) for item in cards),
        "incomes": incomes,
        "expenses": expenses,
        "savings": savings,
        "notes": [row for row in entries if row.get("kind") == "note" and in_month(row, month)],
        "all_notes": [row for row in entries if row.get("kind") == "note"],
        "loans": loans,
        "cards": cards,
    }
