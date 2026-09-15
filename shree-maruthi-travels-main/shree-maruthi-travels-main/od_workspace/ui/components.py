from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from lib.constants import CREDIT_TYPES
from lib.formatting import format_inr


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def page_header(kicker: str, title: str, subtitle: str = "") -> None:
    sub = f'<p class="page-sub">{esc(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f'<div class="page-kicker">{esc(kicker)}</div>'
        f'<h1 class="page-title">{esc(title)}</h1>{sub}',
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f'<div class="empty"><h3>{esc(title)}</h3><p>{esc(body)}</p></div>',
        unsafe_allow_html=True,
    )


def notice(body: str, tone: str = "warn") -> None:
    st.markdown(f'<div class="notice {tone}"><p>{esc(body)}</p></div>', unsafe_allow_html=True)


def chip_class(txn_type: str) -> str:
    key = str(txn_type).lower()
    if key == "credit":
        return "credit"
    if key == "interest":
        return "interest"
    if key == "charge":
        return "charge"
    return ""


def statement(frame: pd.DataFrame, limit: int | None = None) -> None:
    if frame.empty:
        empty_state("No movements yet", "Add a drawdown, repayment, or bank interest from New entry.")
        return
    sort_cols = [col for col in ("date", "created_at") if col in frame.columns]
    rows = frame.sort_values(sort_cols, ascending=False) if sort_cols else frame
    if limit:
        rows = rows.head(limit)
    parts = ['<div class="panel">']
    for row in rows.itertuples():
        incoming = str(row.type) in CREDIT_TYPES
        amount = abs(float(row.amount))
        formatted = f"{'+' if incoming else '−'}{format_inr(amount)}"
        purpose = getattr(row, "purpose", "") or getattr(row, "category", "")
        extras = " · ".join(
            item
            for item in [
                getattr(row, "category", ""),
                getattr(row, "counterparty", ""),
                getattr(row, "project", ""),
            ]
            if item
        )
        day = row.date.strftime("%d %b %Y") if pd.notna(row.date) else ""
        outstanding = ""
        if hasattr(row, "outstanding") and pd.notna(row.outstanding):
            outstanding = f" · bal {format_inr(row.outstanding)}"
        parts.append(
            f'<div class="txn">'
            f'<div class="txn-date">{esc(day)}</div>'
            f'<div><div class="txn-title">'
            f'<span class="chip {chip_class(row.type)}">{esc(row.type)}</span>{esc(purpose)}</div>'
            f'<div class="txn-sub">{esc(extras)}{esc(outstanding)}</div></div>'
            f'<div class="txn-amt {"in" if incoming else "out"}">{esc(formatted)}</div>'
            f"</div>"
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
