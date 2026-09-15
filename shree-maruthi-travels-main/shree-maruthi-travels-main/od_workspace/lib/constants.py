from __future__ import annotations

APP_PUBLIC_TITLE = "Workspace"
APP_PRIVATE_TITLE = "Overdraft Ledger"
BANK_NAME = "Bank of Baroda"
DEFAULT_LIMIT = 9_900_000.0
SESSION_MINUTES = 30

TXN_TYPES = ("Drawdown", "Credit", "Interest", "Charge", "Adjustment")
DRAW_TYPES = {"Drawdown", "Interest", "Charge"}
CREDIT_TYPES = {"Credit"}

MODES = ("NEFT", "RTGS", "IMPS", "UPI", "Cheque", "Cash", "Internal", "Standing instruction", "Other")

DEFAULT_CATEGORIES = [
    "Raw material",
    "Labour / contractor",
    "Inventory / stock",
    "Machinery / equipment",
    "Civil / construction",
    "Professional fees",
    "Rent / premises",
    "Salary",
    "Utilities",
    "Marketing",
    "Travel",
    "Personal withdrawal",
    "Tax / GST",
    "Vendor payment",
    "Bank interest",
    "Bank charges",
    "OD repayment",
    "Other",
]

TXN_COLUMNS = [
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

FACILITY_COLUMNS = [
    "id",
    "bank",
    "product",
    "limit",
    "rate",
    "sanction_date",
    "account_last4",
    "opening_outstanding",
    "holder_name",
    "branch",
    "notes",
]
CATEGORY_COLUMNS = ["id", "name"]

SHEET_TRANSACTIONS = "OD Usage"
SHEET_FACILITY = "Facility"
SHEET_CATEGORIES = "Categories"

DEFAULT_FACILITY = {
    "bank": BANK_NAME,
    "product": "Overdraft",
    "limit": str(DEFAULT_LIMIT),
    "rate": "12.00",
    "sanction_date": "",
    "account_last4": "",
    "opening_outstanding": "0",
    "holder_name": "",
    "branch": "",
    "notes": "",
}
