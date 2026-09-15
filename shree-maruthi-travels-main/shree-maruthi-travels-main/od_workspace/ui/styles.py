from __future__ import annotations

import streamlit as st


def inject(lock: bool = False) -> None:
    extra = _LOCK_CSS if lock else ""
    st.markdown(f"<style>{_APP_CSS}{extra}</style>", unsafe_allow_html=True)


_APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, p, label, input, textarea, button {
    font-family: "Plus Jakarta Sans", sans-serif !important;
}

.stApp {
    background:
        radial-gradient(900px 420px at 100% -10%, rgba(232, 93, 4, 0.08), transparent 50%),
        #f3efe6;
    color: #142033;
}

header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
.stAppDeployButton,
#MainMenu,
footer { display: none !important; }

.block-container {
    padding: 1.6rem 2rem 3.5rem !important;
    max-width: 1120px;
}

section[data-testid="stSidebar"] {
    background: #0e2a47 !important;
    border-right: 0 !important;
}
section[data-testid="stSidebar"] > div { background: #0e2a47; }
section[data-testid="stSidebar"] * { color: #eef3f8 !important; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #b7c4d3 !important; }

.brand {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 0.4rem 0.2rem 1.1rem;
}
.brand-mark {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    background: #e85d04;
    color: white;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.15rem;
}
.brand-name { font-weight: 800; font-size: 1.05rem; color: #fff !important; letter-spacing: -0.02em; }
.brand-sub { font-size: 0.75rem; color: #9db0c4 !important; }

section[data-testid="stSidebar"] .stRadio > label { display: none; }
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: 6px; }
section[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 12px !important;
    padding: 0.72rem 0.9rem !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.08) !important;
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
    background: rgba(232, 93, 4, 0.22) !important;
    border-color: rgba(232, 93, 4, 0.55) !important;
}

.stButton button {
    height: 44px;
    border-radius: 12px !important;
    font-weight: 700 !important;
    border: 1px solid #d9d0c2 !important;
    background: #fff !important;
    color: #142033 !important;
}
.stButton button:hover { border-color: #e85d04 !important; color: #e85d04 !important; }
.stButton button[kind="primary"],
.stButton button[data-testid="stBaseButton-primary"] {
    background: #e85d04 !important;
    color: #fff !important;
    border: none !important;
}
section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.06) !important;
    color: #eef3f8 !important;
    border-color: rgba(255,255,255,0.08) !important;
}

.stTextInput input, .stNumberInput input, .stDateInput input,
.stSelectbox [data-baseweb="select"] > div, .stMultiSelect [data-baseweb="select"] > div,
.stTextArea textarea {
    border-radius: 12px !important;
    border: 1px solid #e4ddd0 !important;
    background: #fffdf8 !important;
    min-height: 44px;
    color: #142033 !important;
}
[data-testid="stForm"] {
    background: #fff;
    border: 1px solid #e4ddd0;
    border-radius: 20px;
    padding: 1.1rem 1.15rem 0.4rem;
    box-shadow: 0 10px 30px rgba(20, 32, 51, 0.04);
}
[data-testid="stMetric"] {
    background: #fff;
    border: 1px solid #e4ddd0;
    border-radius: 16px;
    padding: 0.85rem 1rem;
}
[data-testid="stPlotlyChart"],
[data-testid="stDataFrame"],
[data-testid="stDataFrameResizable"] {
    background: #fff;
    border: 1px solid #e4ddd0;
    border-radius: 22px;
    padding: 6px;
    box-shadow: 0 16px 40px rgba(20, 32, 51, 0.05);
}
[data-testid="stMetricValue"] { font-weight: 800; color: #0e2a47; }

.page-kicker {
    color: #e85d04;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.page-title {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: #0e2a47;
    margin: 0 0 0.25rem;
}
.page-sub { color: #5c6b7a; margin: 0 0 1.2rem; }

.hero {
    display: grid;
    grid-template-columns: 1.35fr 1fr;
    gap: 18px;
    margin: 0.4rem 0 1.1rem;
}
.hero-main, .hero-side, .panel, .empty, .notice {
    background: #fff;
    border: 1px solid #e4ddd0;
    border-radius: 22px;
    box-shadow: 0 16px 40px rgba(20, 32, 51, 0.05);
}
.hero-main { padding: 1.5rem 1.6rem 1.4rem; }
.hero-side { padding: 1.15rem 1.25rem; }
.hero-label { color: #5c6b7a; font-size: 0.86rem; font-weight: 600; }
.hero-amount {
    font-size: 2.55rem;
    font-weight: 800;
    letter-spacing: -0.05em;
    color: #0e2a47;
    line-height: 1.1;
    margin: 0.15rem 0 0.85rem;
}
.util-track {
    height: 10px;
    background: #efe7d8;
    border-radius: 99px;
    overflow: hidden;
}
.util-fill { height: 100%; border-radius: 99px; background: #e85d04; }
.util-fill.warn { background: #d97706; }
.util-fill.danger { background: #c0392b; }
.hero-meta { margin-top: 0.65rem; color: #5c6b7a; font-size: 0.88rem; }
.stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 1rem;
}
.stat {
    background: #f7f1e6;
    border-radius: 14px;
    padding: 0.75rem 0.85rem;
}
.stat b { display: block; font-size: 1.05rem; color: #0e2a47; margin-top: 2px; }
.stat span { color: #5c6b7a; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }

.side-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.55rem 0;
    border-bottom: 1px solid #f0e9dc;
    font-size: 0.92rem;
}
.side-row:last-child { border-bottom: 0; }
.side-row span { color: #5c6b7a; }
.side-row b { color: #0e2a47; }

.txn {
    display: grid;
    grid-template-columns: 110px 1fr auto;
    gap: 12px;
    padding: 0.9rem 0;
    border-bottom: 1px solid #f0e9dc;
    align-items: center;
}
.txn:last-child { border-bottom: 0; }
.txn-date { color: #5c6b7a; font-size: 0.84rem; font-weight: 600; }
.txn-title { font-weight: 700; color: #142033; }
.txn-sub { color: #7a8796; font-size: 0.8rem; margin-top: 2px; }
.txn-amt { font-weight: 800; text-align: right; white-space: nowrap; }
.txn-amt.out { color: #c0392b; }
.txn-amt.in { color: #1f7a4d; }
.chip {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 99px;
    background: #f7f1e6;
    color: #0e2a47;
    margin-right: 6px;
}
.chip.credit { background: #e5f6ee; color: #1f7a4d; }
.chip.interest { background: #e8eef6; color: #0e2a47; }
.chip.charge { background: #f8ece6; color: #c0392b; }

.panel { padding: 1.1rem 1.2rem 0.7rem; margin: 0.8rem 0; }
.empty, .notice { padding: 1.6rem 1.4rem; text-align: center; margin: 0.8rem 0; }
.empty h3, .notice h3 { margin: 0 0 0.35rem; color: #0e2a47; }
.empty p, .notice p { color: #5c6b7a; margin: 0; }
.notice.warn { border-color: #f0d3a8; background: #fff8ec; }
.notice.danger { border-color: #f0c2bc; background: #fff1ef; }
.notice.ok { border-color: #bfe3cf; background: #f1faf5; }

.lock-card {
    background: #fff;
    border: 1px solid #e4ddd0;
    border-radius: 28px;
    padding: 2.2rem 2rem 0.4rem;
    box-shadow: 0 24px 60px rgba(14, 42, 71, 0.12);
    text-align: center;
}
.lock-card h1 { font-size: 2rem; margin: 0.2rem 0 0.4rem; color: #0e2a47; letter-spacing: -0.04em; }
.lock-card p { color: #5c6b7a; }

.status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}
.status-ok { background: #1f7a4d; }
.status-warn { background: #d97706; }
.status-err { background: #c0392b; }

@media (max-width: 900px) {
    .hero { grid-template-columns: 1fr; }
    .txn { grid-template-columns: 1fr auto; }
    .txn-date { grid-column: 1 / -1; }
}
"""

_LOCK_CSS = """
section[data-testid="stSidebar"] { display: none !important; }
.block-container { max-width: 460px !important; padding-top: 11vh !important; }
"""
