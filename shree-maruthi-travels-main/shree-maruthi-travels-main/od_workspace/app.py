from __future__ import annotations

import streamlit as st

from lib.auth import is_authenticated, logout, touch_session
from lib.constants import APP_PUBLIC_TITLE
from lib.storage import LedgerStore
from lib.zoho_sheet import zoho_is_configured
from ui.dashboard import render_dashboard
from ui.entry import render_entry
from ui.insights import render_insights
from ui.interest import render_interest
from ui.ledger_view import render_ledger
from ui.lock import render_lock
from ui.settings import render_settings
from ui.styles import inject

st.set_page_config(
    page_title=APP_PUBLIC_TITLE,
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not is_authenticated():
    inject(lock=True)
    render_lock()
    st.stop()

inject()
touch_session()

if "store" not in st.session_state:
    st.session_state.store = LedgerStore()
store: LedgerStore = st.session_state.store

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-mark">B</div>
            <div>
                <div class="brand-name">Private Ledger</div>
                <div class="brand-sub">Bank of Baroda · 99 Lakh OD</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    storage = "Zoho Sheet synced" if zoho_is_configured() and store.backend == "zoho" else "Saved on this device"
    st.caption(storage)
    section = st.radio(
        "Go to",
        ["Overview", "New entry", "Ledger", "Insights", "Interest", "Settings"],
        label_visibility="collapsed",
    )
    st.write("")
    if st.button("Reload", use_container_width=True):
        st.session_state.store = LedgerStore()
        st.session_state.store.load(force=True)
        st.rerun()
    if st.button("Lock", use_container_width=True):
        logout()
        st.rerun()

if section == "Overview":
    render_dashboard(store)
elif section == "New entry":
    render_entry(store)
elif section == "Ledger":
    render_ledger(store)
elif section == "Insights":
    render_insights(store)
elif section == "Interest":
    render_interest(store)
else:
    render_settings(store)
