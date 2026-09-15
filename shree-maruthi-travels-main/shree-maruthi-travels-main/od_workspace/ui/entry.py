from __future__ import annotations

from datetime import date

import streamlit as st

from lib.constants import MODES, TXN_TYPES
from lib.formatting import format_inr
from lib.ledger import current_outstanding, facility_number, transactions_frame
from lib.storage import LedgerStore
from ui.components import page_header


def render_entry(store: LedgerStore) -> None:
    facility = store.facility()
    opening = facility_number(facility, "opening_outstanding")
    outstanding = current_outstanding(transactions_frame(store.transactions()), opening)
    available = facility_number(facility, "limit", 9_900_000) - outstanding

    page_header(
        "Post a movement",
        "New entry",
        f"Outstanding {format_inr(outstanding)}  ·  available {format_inr(available)}",
    )

    with st.form("txn_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        txn_date = c1.date_input("Date", value=date.today())
        txn_type = c2.selectbox("Type", TXN_TYPES)
        amount = c3.number_input("Amount (₹)", min_value=0.0, step=1000.0, format="%.2f")
        c4, c5 = st.columns(2)
        category = c4.selectbox("Category", store.categories())
        mode = c5.selectbox("Mode", MODES)
        c6, c7 = st.columns(2)
        counterparty = c6.text_input("Paid to / received from")
        reference = c7.text_input("UTR / cheque / reference")
        purpose = st.text_input("Purpose")
        project = st.text_input("Project / bucket", placeholder="Site A, stock, personal")
        notes = st.text_area("Private notes", height=80)
        submitted = st.form_submit_button("Save entry", type="primary", use_container_width=True)

    st.caption(
        "Drawdown = money out of the OD. Credit = money back. Interest / Charge = bank debit."
    )

    if not submitted:
        return
    if amount <= 0:
        st.error("Enter an amount greater than zero.")
        return
    if txn_type == "Drawdown" and amount > available + 1:
        st.error(f"This exceeds available limit by {format_inr(amount - available)}.")
        return

    store.add_transaction(
        {
            "date": txn_date,
            "type": txn_type,
            "amount": amount,
            "category": category,
            "counterparty": counterparty,
            "purpose": purpose,
            "mode": mode,
            "reference": reference,
            "project": project,
            "notes": notes,
        }
    )
    st.success(f"Saved {txn_type.lower()} of {format_inr(amount)}.")
    st.rerun()
