from __future__ import annotations

from datetime import date

import streamlit as st

from lib.constants import DEFAULT_CATEGORIES
from lib.formatting import parse_date
from lib.storage import LedgerStore
from lib.zoho_sheet import ZohoSheetError, zoho_is_configured
from ui.components import notice, page_header


def render_settings(store: LedgerStore) -> None:
    page_header("Setup", "Facility & storage", "Keep the workbook private. Only you should hold the refresh token.")
    _connection_panel(store)
    st.write("")
    _facility_form(store)
    st.write("")
    _category_form(store)


def _connection_panel(store: LedgerStore) -> None:
    st.markdown('<div class="page-kicker">Zoho Sheet</div>', unsafe_allow_html=True)
    if zoho_is_configured():
        try:
            store.ping()
            notice("Connected. New entries are written to your private Zoho workbook.", "ok")
        except ZohoSheetError as exc:
            notice(f"Credentials found, but Zoho rejected the call: {exc}", "danger")
        if st.button("Create worksheets and headers"):
            try:
                store.initialise_zoho()
                st.success("Workbook is ready.")
            except ZohoSheetError as exc:
                st.error(str(exc))
    else:
        notice("Running on this device only. Connect Zoho before a cloud deploy.")
        st.markdown(
            """
1. Create a blank Zoho Sheet and copy the id from  
   `https://sheet.zoho.in/sheet/open/RESOURCE_ID`
2. In [Zoho API Console](https://api-console.zoho.in) create a **Self Client**
3. Generate a code with `ZohoSheet.dataAPI.READ,ZohoSheet.dataAPI.UPDATE`
4. Run `python scripts/zoho_oauth.py`
5. Paste the values into `.streamlit/secrets.toml`
            """
        )


def _facility_form(store: LedgerStore) -> None:
    facility = store.facility()
    st.markdown('<div class="page-kicker">Overdraft facility</div>', unsafe_allow_html=True)
    with st.form("facility_form"):
        c1, c2 = st.columns(2)
        bank = c1.text_input("Bank", value=facility.get("bank", "Bank of Baroda"))
        product = c2.text_input("Product", value=facility.get("product", "Overdraft"))
        c3, c4 = st.columns(2)
        limit = c3.number_input(
            "Sanctioned limit (₹)",
            min_value=0.0,
            value=float(facility.get("limit") or 9_900_000),
            step=10000.0,
        )
        rate = c4.number_input(
            "Interest rate % p.a.",
            min_value=0.0,
            value=float(facility.get("rate") or 12),
            step=0.05,
        )
        c5, c6 = st.columns(2)
        sanction = parse_date(facility.get("sanction_date")) or date.today()
        sanction_date = c5.date_input("Sanction / start date", value=sanction)
        opening = c6.number_input(
            "Opening outstanding already used (₹)",
            min_value=0.0,
            value=float(facility.get("opening_outstanding") or 0),
            step=1000.0,
        )
        c7, c8 = st.columns(2)
        holder = c7.text_input("Account holder", value=facility.get("holder_name", ""))
        last4 = c8.text_input("Account last 4 digits", value=facility.get("account_last4", ""), max_chars=4)
        branch = st.text_input("Branch", value=facility.get("branch", ""))
        notes = st.text_area("Internal notes", value=facility.get("notes", ""))
        saved = st.form_submit_button("Save facility", type="primary", use_container_width=True)
    if saved:
        store.save_facility(
            {
                "bank": bank,
                "product": product,
                "limit": f"{limit:.2f}",
                "rate": f"{rate:.2f}",
                "sanction_date": sanction_date.isoformat(),
                "opening_outstanding": f"{opening:.2f}",
                "holder_name": holder,
                "account_last4": last4,
                "branch": branch,
                "notes": notes,
            }
        )
        st.success("Facility saved.")
        st.rerun()


def _category_form(store: LedgerStore) -> None:
    st.markdown('<div class="page-kicker">Categories</div>', unsafe_allow_html=True)
    current = "\n".join(store.categories())
    text = st.text_area("One category per line", value=current, height=220)
    c1, c2 = st.columns(2)
    if c1.button("Save categories", use_container_width=True):
        store.save_categories([line.strip() for line in text.splitlines() if line.strip()])
        st.success("Categories saved.")
        st.rerun()
    if c2.button("Restore defaults", use_container_width=True):
        store.save_categories(DEFAULT_CATEGORIES)
        st.success("Default categories restored.")
        st.rerun()
