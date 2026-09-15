from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from lib.formatting import format_inr, format_lakhs, pct
from lib.ledger import estimated_interest, parse_facility_date, snapshot, with_running_balance
from lib.storage import LedgerStore
from ui.components import empty_state, notice, page_header, statement


def render_dashboard(store: LedgerStore) -> None:
    facility = store.facility()
    state = snapshot(facility, store.transactions())
    sanction = parse_facility_date(facility)
    interest = estimated_interest(
        state["frame"],
        state["opening"],
        state["rate"],
        start=sanction,
    )
    tone = "good"
    if state["utilization"] >= 90:
        tone = "danger"
    elif state["utilization"] >= 75:
        tone = "warn"

    holder = facility.get("holder_name") or "Private account"
    extras = [holder, facility.get("product", "Overdraft")]
    if facility.get("account_last4"):
        extras.append(f"A/c ••{facility['account_last4']}")
    if facility.get("branch"):
        extras.append(facility["branch"])
    page_header("Bank of Baroda", "Overdraft facility", " · ".join(extras))

    st.markdown(_hero_html(state, tone), unsafe_allow_html=True)

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.plotly_chart(_balance_chart(state), use_container_width=True, config={"displayModeBar": False})
    with right:
        st.markdown(
            f"""
            <div class="hero-side">
                <div class="page-kicker">This month</div>
                <div class="side-row"><span>Drawdowns</span><b>{format_inr(state['drawdowns_month'])}</b></div>
                <div class="side-row"><span>Credits</span><b>{format_inr(state['credits_month'])}</b></div>
                <div class="side-row"><span>Interest posted</span><b>{format_inr(state['interest_month'])}</b></div>
                <div class="side-row"><span>Charges</span><b>{format_inr(state['charges_month'])}</b></div>
                <div class="side-row"><span>Estimated interest</span><b>{format_inr(interest['interest'])}</b></div>
                <div class="side-row"><span>Average use</span><b>{format_inr(interest['average_outstanding'])}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if store.backend != "zoho":
        notice("Zoho Sheet is not connected yet. This copy lives on this device only.")
    if state["utilization"] >= 90:
        notice("Limit is almost fully used. Keep headroom for interest and charges.", "danger")
    elif state["utilization"] >= 75:
        notice("Utilisation is high. Plan a credit before the next interest debit.")

    st.markdown('<div class="page-kicker" style="margin-top:1rem">Recent movements</div>', unsafe_allow_html=True)
    recent = with_running_balance(state["frame"], state["opening"])
    if recent.empty:
        empty_state("Nothing posted yet", "Record the first drawdown or the amount already utilised.")
        return
    statement(recent, limit=8)


def _hero_html(state: dict, tone: str) -> str:
    fill = {"good": "", "warn": "warn", "danger": "danger"}[tone]
    width = max(0, min(100, state["utilization"]))
    return f"""
    <div class="hero-main" style="margin:0.4rem 0 1.1rem">
        <div class="hero-label">Available to draw</div>
        <div class="hero-amount">{format_inr(state['available'])}</div>
        <div class="util-track"><div class="util-fill {fill}" style="width:{width:.1f}%"></div></div>
        <div class="hero-meta">{format_lakhs(state['outstanding'])} used of {format_lakhs(state['limit'])} · {pct(state['utilization'])} utilised</div>
        <div class="stat-grid">
          <div class="stat"><span>Outstanding</span><b>{format_inr(state['outstanding'])}</b></div>
          <div class="stat"><span>Sanctioned</span><b>{format_inr(state['limit'])}</b></div>
          <div class="stat"><span>Rate</span><b>{state['rate']:.2f}% p.a.</b></div>
          <div class="stat"><span>Entries</span><b>{state['txn_count']}</b></div>
        </div>
    </div>
    """


def _balance_chart(state: dict) -> go.Figure:
    frame = with_running_balance(state["frame"], state["opening"])
    fig = go.Figure()
    if not frame.empty:
        fig.add_trace(
            go.Scatter(
                x=frame["date"],
                y=frame["outstanding"],
                fill="tozeroy",
                name="Outstanding",
                line={"color": "#0e2a47", "width": 2.5},
                fillcolor="rgba(14, 42, 71, 0.10)",
            )
        )
    fig.add_hline(y=state["limit"], line_dash="dot", line_color="#e85d04", annotation_text="Limit")
    fig.update_layout(
        height=300,
        margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#142033", "family": "Plus Jakarta Sans"},
        yaxis={"gridcolor": "#efe7d8", "tickprefix": "₹", "zeroline": False},
        xaxis={"gridcolor": "#efe7d8"},
        title={"text": "Running outstanding", "font": {"size": 14, "color": "#5c6b7a"}},
        showlegend=False,
    )
    return fig
