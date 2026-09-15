from __future__ import annotations

from datetime import date

import streamlit as st

from lib.constants import MODES, TXN_TYPES
from lib.formatting import format_inr
from lib.ledger import facility_number, transactions_frame, with_running_balance
from lib.storage import LedgerStore
from ui.components import empty_state, page_header, statement


def render_ledger(store: LedgerStore) -> None:
    facility = store.facility()
    opening = facility_number(facility, "opening_outstanding")
    frame = with_running_balance(transactions_frame(store.transactions()), opening)

    page_header("Statement", "All movements", "Filter the OD like a bank statement, then edit any row.")

    if frame.empty:
        empty_state("The ledger is empty", "Post the first movement from New entry.")
        return

    filters = st.container(border=True)
    with filters:
        c1, c2, c3, c4 = st.columns(4)
        types = c1.multiselect("Type", TXN_TYPES)
        categories = c2.multiselect("Category", sorted(x for x in frame["category"].dropna().unique() if x))
        search = c3.text_input("Search")
        period = c4.date_input("Date range", value=(frame["date"].min().date(), date.today()))

    view = frame.copy()
    if types:
        view = view[view["type"].isin(types)]
    if categories:
        view = view[view["category"].isin(categories)]
    if search:
        blob = (
            view["purpose"].fillna("")
            + " "
            + view["counterparty"].fillna("")
            + " "
            + view["reference"].fillna("")
            + " "
            + view["notes"].fillna("")
            + " "
            + view["project"].fillna("")
        )
        view = view[blob.str.contains(search, case=False, na=False)]
    if isinstance(period, tuple) and len(period) == 2:
        start, end = period
        view = view[(view["date"].dt.date >= start) & (view["date"].dt.date <= end)]

    st.caption(f"{len(view)} rows  ·  net in view {format_inr(view['signed'].sum())}")
    statement(view)

    csv = view.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, file_name="od-ledger.csv", mime="text/csv")

    st.markdown('<div class="page-kicker" style="margin-top:1.2rem">Edit or remove</div>', unsafe_allow_html=True)
    options = {
        f"{row.date.strftime('%d %b %Y')} · {row.type} · {format_inr(row.amount)} · {row.purpose or row.category}": row.id
        for row in view.itertuples()
    }
    if not options:
        return
    selected_label = st.selectbox("Select an entry", list(options))
    selected_id = options[selected_label]
    row = frame.loc[frame["id"] == selected_id].iloc[0]

    with st.form("edit_txn"):
        c1, c2, c3 = st.columns(3)
        txn_date = c1.date_input("Date", value=row["date"].date())
        txn_type = c2.selectbox(
            "Type",
            TXN_TYPES,
            index=TXN_TYPES.index(row["type"]) if row["type"] in TXN_TYPES else 0,
        )
        amount = c3.number_input("Amount (₹)", min_value=0.0, value=float(row["amount"]), step=1000.0)
        c4, c5 = st.columns(2)
        cats = store.categories()
        category = c4.selectbox(
            "Category",
            cats,
            index=cats.index(row["category"]) if row["category"] in cats else 0,
        )
        mode = c5.selectbox(
            "Mode",
            MODES,
            index=MODES.index(row["mode"]) if row["mode"] in MODES else 0,
        )
        counterparty = st.text_input("Paid to / received from", value=str(row["counterparty"]))
        purpose = st.text_input("Purpose", value=str(row["purpose"]))
        project = st.text_input("Project / bucket", value=str(row["project"]))
        reference = st.text_input("Reference", value=str(row["reference"]))
        notes = st.text_area("Notes", value=str(row["notes"]))
        save = st.form_submit_button("Update entry", type="primary", use_container_width=True)

    if save:
        store.update_transaction(
            selected_id,
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
                "created_at": row["created_at"],
            },
        )
        st.success("Entry updated.")
        st.rerun()

    if st.button("Delete this entry"):
        store.delete_transaction(selected_id)
        st.success("Entry deleted.")
        st.rerun()
