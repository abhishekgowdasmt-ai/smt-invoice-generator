from __future__ import annotations

from datetime import date

import plotly.express as px
import streamlit as st

from lib.formatting import format_inr
from lib.ledger import estimated_interest, parse_facility_date, snapshot, transactions_frame
from lib.storage import LedgerStore
from ui.components import empty_state, page_header


def render_interest(store: LedgerStore) -> None:
    facility = store.facility()
    state = snapshot(facility, store.transactions())
    default_start = parse_facility_date(facility) or date.today().replace(day=1)

    page_header(
        "Daily product",
        "Interest estimator",
        "Banks usually charge outstanding × rate ÷ 365. Compare this with posted Interest rows.",
    )

    c1, c2, c3 = st.columns(3)
    start = c1.date_input("From", value=default_start)
    end = c2.date_input("To", value=date.today())
    rate = c3.number_input("Annual rate %", min_value=0.0, value=float(state["rate"] or 12), step=0.05)

    estimate = estimated_interest(state["frame"], state["opening"], rate, start, end)
    posted = 0.0
    frame = transactions_frame(store.transactions())
    if not frame.empty:
        mask = (
            (frame["type"] == "Interest")
            & (frame["date"].dt.date >= start)
            & (frame["date"].dt.date <= end)
        )
        posted = float(frame.loc[mask, "amount"].abs().sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Estimated interest", format_inr(estimate["interest"]))
    m2.metric("Posted by bank", format_inr(posted))
    m3.metric("Difference", format_inr(estimate["interest"] - posted))
    m4.metric("Average outstanding", format_inr(estimate["average_outstanding"]))

    daily = estimate["daily"]
    if daily.empty:
        empty_state("No balance in this range", "Add movements or widen the dates.")
        return
    fig = px.area(daily, x="date", y="outstanding")
    fig.update_traces(line_color="#0e2a47", fillcolor="rgba(14, 42, 71, 0.12)")
    fig.update_layout(
        title={"text": "Daily outstanding used for interest", "font": {"size": 14, "color": "#5c6b7a"}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#142033", "family": "Plus Jakarta Sans"},
        yaxis={"gridcolor": "#efe7d8", "tickprefix": "₹", "zeroline": False},
        xaxis={"gridcolor": "#efe7d8"},
        margin=dict(l=8, r=8, t=48, b=8),
        height=340,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        f"{estimate['days']} days · {rate:.2f}% p.a. · "
        "Penal interest or a 365/360 day basis can explain a small gap."
    )
