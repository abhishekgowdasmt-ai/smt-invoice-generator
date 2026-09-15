from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.formatting import format_inr
from lib.ledger import category_breakdown, facility_number, monthly_flow, snapshot
from lib.storage import LedgerStore
from ui.components import empty_state, page_header

PALETTE = ["#0e2a47", "#e85d04", "#c9a227", "#1f7a4d", "#8b5e3c", "#5c6b7a", "#c0392b"]


def render_insights(store: LedgerStore) -> None:
    facility = store.facility()
    state = snapshot(facility, store.transactions())
    frame = state["frame"]

    page_header("Allocation", "Where the limit went", "Split the OD by category, month, and project.")

    if frame.empty:
        empty_state("No spend to chart yet", "Add a few drawdowns first.")
        return

    cats = category_breakdown(frame)
    months = monthly_flow(frame)
    projects = _project_breakdown(frame)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total drawdowns", format_inr(state["drawdowns_all"]))
    c2.metric("Total credits", format_inr(state["credits_all"]))
    c3.metric("Interest + charges", format_inr(state["interest_all"] + state["charges_all"]))

    left, right = st.columns(2, gap="large")
    with left:
        if not cats.empty:
            fig = px.pie(cats, values="drawdown", names="category", hole=0.62, color_discrete_sequence=PALETTE)
            _style(fig, "Drawdowns by category")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right:
        if not months.empty:
            fig = px.bar(
                months,
                x="month",
                y=["drawdown", "credit", "interest"],
                barmode="group",
                color_discrete_sequence=["#e85d04", "#1f7a4d", "#0e2a47"],
            )
            _style(fig, "Monthly movement")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    pretty = cats.copy()
    for col in ("drawdown", "credit", "net"):
        pretty[col] = pretty[col].map(format_inr)
    st.markdown('<div class="page-kicker">Categories</div>', unsafe_allow_html=True)
    st.dataframe(pretty, use_container_width=True, hide_index=True)

    if not projects.empty:
        show = projects.copy()
        for col in ("drawdown", "credit", "net"):
            show[col] = show[col].map(format_inr)
        st.markdown('<div class="page-kicker" style="margin-top:1rem">Projects</div>', unsafe_allow_html=True)
        st.dataframe(show, use_container_width=True, hide_index=True)

    opening = facility_number(facility, "opening_outstanding")
    if opening:
        st.caption(f"Opening outstanding already on the books: {format_inr(opening)}")


def _project_breakdown(frame):
    work = frame.copy()
    work["project"] = work["project"].replace("", "Unassigned").fillna("Unassigned")
    work["drawdown"] = [
        abs(float(a)) if t != "Credit" else 0.0 for t, a in zip(work["type"], work["amount"])
    ]
    work["credit"] = [
        abs(float(a)) if t == "Credit" else 0.0 for t, a in zip(work["type"], work["amount"])
    ]
    grouped = work.groupby("project", as_index=False)[["drawdown", "credit"]].sum()
    grouped["net"] = grouped["drawdown"] - grouped["credit"]
    return grouped.sort_values("drawdown", ascending=False)


def _style(fig, title: str) -> None:
    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#5c6b7a"}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#142033", "family": "Plus Jakarta Sans"},
        legend={"bgcolor": "rgba(0,0,0,0)"},
        margin=dict(l=8, r=8, t=48, b=8),
        height=340,
    )
    if fig.data and fig.data[0].type == "pie":
        fig.update_traces(textposition="inside", textinfo="percent")
