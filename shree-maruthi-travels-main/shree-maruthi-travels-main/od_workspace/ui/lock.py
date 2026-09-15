from __future__ import annotations

import streamlit as st

from lib.auth import login, password_is_configured
from lib.constants import APP_PUBLIC_TITLE


def render_lock() -> None:
    st.markdown(
        f"""
        <div class="lock-card">
            <div class="page-kicker">Restricted</div>
            <h1>{APP_PUBLIC_TITLE}</h1>
            <p>Private overdraft ledger. Unlock to continue.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not password_is_configured():
        st.error("Set auth.password in .streamlit/secrets.toml first.")
        return
    with st.form("lock_form"):
        password = st.text_input("Passphrase", type="password", label_visibility="collapsed", placeholder="Passphrase")
        submitted = st.form_submit_button("Unlock workspace", use_container_width=True)
    if submitted:
        ok, message = login(password)
        if ok:
            st.rerun()
        st.error(message)
