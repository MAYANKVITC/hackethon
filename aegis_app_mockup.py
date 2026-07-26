"""
Aegis — AML Intelligence Platform
==================================
Streamlit implementation of the AML Intelligence Platform UI/UX spec.

Run with:
    pip install streamlit pandas numpy plotly
    streamlit run aegis_app.py

All data in this file is synthetic/mocked (accounts, transactions, risk
scores, AI confidence values) so the app runs standalone with no external
API, database, or LLM key required. Swap `generate_accounts()` for your
real data source and `run_ai_investigation()` for a real LLM/agent call
when you wire this into your actual pipeline.
"""

import time
import random
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
import streamlit as st

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Aegis | AML Intelligence Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

COUNTRIES = ["UAE", "Cayman Is.", "Singapore", "Switzerland", "Panama",
             "Cyprus", "Malta", "Hong Kong", "UK", "US"]
TYPOLOGIES = ["Layering", "Smurfing", "Shell Company", "Trade-Based ML",
              "Crypto Mixing", "Structuring"]
ANALYSTS = ["J. Alvarez", "R. Chen", "M. Osei", "S. Novak", "A. Khan"]
STATUSES = ["Open", "Escalated", "SAR Filed", "Under Review", "Closed"]

RISK_COLORS = {"High": "#f0475b", "Medium": "#f5a623", "Low": "#2ed598"}
BLUE, CYAN = "#2e6bff", "#22d3ee"

TIMELINE_STAGES = [
    ("Intent Detection", "Classifying query as a targeted risk investigation"),
    ("Entity Extraction", "Identifying accounts, amounts, and date ranges"),
    ("Tool Selection", "Routing to graph traversal + risk scoring models"),
    ("Graph Analysis", "Traversing transaction network for layering paths"),
    ("Risk Scoring", "Computing composite risk score from behavioral features"),
    ("Recommendation", "Drafting next-action guidance for the analyst"),
]

SAMPLE_PROMPTS = [
    "Which accounts show signs of layering above $250K?",
    "Find rapid in-out transfers under 48 hours across borders",
    "Surface shell-company networks linked to account ACC-88213",
    "Rank the top 10 highest risk crypto off-ramp accounts",
]

# ============================================================
# CSS — DARK GLASSMORPHIC ENTERPRISE THEME
# ============================================================
def inject_css():
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background:
            radial-gradient(ellipse 1200px 800px at 10% -10%, rgba(46,107,255,0.10), transparent 60%),
            radial-gradient(ellipse 900px 700px at 100% 0%, rgba(34,211,238,0.06), transparent 55%),
            #05070c;
        color: #eef2fa;
    }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px;}

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0e18, #05070c);
        border-right: 1px solid rgba(255,255,255,0.09);
    }
    section[data-testid="stSidebar"] * { color: #aab3c5; }

    /* Glass card container */
    .glass-card {
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 18px;
        padding: 20px 22px;
        margin-bottom: 16px;
        backdrop-filter: blur(10px);
    }
    .card-title {
        font-size: 14px; font-weight: 700; margin-bottom: 12px;
        display:flex; align-items:center; gap:8px; color:#eef2fa;
    }
    .card-title .dot {width:7px; height:7px; border-radius:50%; background:#22d3ee;
        box-shadow:0 0 6px #22d3ee; display:inline-block;}

    /* KPI cards */
    .kpi-card {
        background: rgba(255,255,255,0.035); border:1px solid rgba(255,255,255,0.09);
        border-radius:16px; padding:16px 18px; position:relative; overflow:hidden;
    }
    .kpi-label {font-size:10.5px; text-transform:uppercase; letter-spacing:0.8px;
        color:#6b7488; font-weight:700;}
    .kpi-value {font-family:'JetBrains Mono', monospace; font-size:25px; font-weight:700;
        margin-top:6px; color:#eef2fa; letter-spacing:-0.5px;}
    .kpi-delta {font-size:11px; margin-top:6px; font-weight:600;}
    .kpi-delta.up {color:#f0475b;} .kpi-delta.down {color:#2ed598;} .kpi-delta.neutral {color:#22d3ee;}

    /* Badges */
    .badge {padding:3px 11px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:0.3px;}
    .badge.High {background:rgba(240,71,91,0.14); color:#f0475b;}
    .badge.Medium {background:rgba(245,166,35,0.14); color:#f5a623;}
    .badge.Low {background:rgba(46,213,152,0.14); color:#2ed598;}

    .recommend-box {
        margin-top:12px; padding:14px; border-radius:14px; background:rgba(46,107,255,0.08);
        border:1px solid rgba(46,107,255,0.25); font-size:12.8px; line-height:1.55; color:#cfd9f5;
    }

    /* Buttons */
    .stButton>button {
        background: rgba(255,255,255,0.035); border:1px solid rgba(255,255,255,0.14);
        color:#eef2fa; border-radius:10px; font-weight:600; font-size:13px; padding:0.5rem 1.1rem;
        transition:.15s;
    }
    .stButton>button:hover {border-color:rgba(255,255,255,0.35); background:rgba(255,255,255,0.07); color:#fff;}
    .stButton>button[kind="primary"] {
        background:linear-gradient(135deg, #2e6bff, #1d4fd6); border:none;
        box-shadow:0 4px 18px rgba(46,107,255,0.35);
    }

    /* Metric widget cleanup */
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.035); border:1px solid rgba(255,255,255,0.09);
        border-radius:14px; padding:12px 16px;
    }

    /* Text input / selectbox */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background: rgba(255,255,255,0.04) !important; border-radius:10px !important;
        color:#eef2fa !important; border:1px solid rgba(255,255,255,0.1) !important;
    }

    /* Tabs -> nav pills */
    .stTabs [data-baseweb="tab-list"] {gap: 4px; border-bottom:1px solid rgba(255,255,255,0.09);}
    .stTabs [data-baseweb="tab"] {
        height:42px; border-radius:11px 11px 0 0; background:transparent; color:#aab3c5;
        font-weight:500; font-size:14px; padding:0 18px;
    }
    .stTabs [aria-selected="true"] {
        background:linear-gradient(135deg, rgba(46,107,255,0.28), rgba(34,211,238,0.14)) !important;
        color:#fff !important;
    }

    /* status widget (AI timeline) */
    div[data-testid="stStatusWidget"] {
        background: rgba(255,255,255,0.035); border:1px solid rgba(255,255,255,0.09); border-radius:14px;
    }

    .mono {font-family:'JetBrains Mono', monospace;}
    .subtle {color:#6b7488; font-size:12.5px;}
    hr {border-color: rgba(255,255,255,0.08);}
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# SYNTHETIC DATA
# ============================================================
@st.cache_data
def generate_accounts(n=40, seed=42):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        risk = rng.randint(20, 98)
        level = "High" if risk >= 70 else "Medium" if risk >= 40 else "Low"
        rows.append({
            "account_id": f"ACC-{88200 + i}",
            "risk_score": risk,
            "risk_level": level,
            "typology": rng.choice(TYPOLOGIES),
            "total_sent": rng.randint(15_000, 2_100_000),
            "total_received": rng.randint(10_000, 1_900_000),
            "country": rng.choice(COUNTRIES),
            "countries_count": rng.randint(1, 9),
            "analyst": rng.choice(ANALYSTS),
            "status": rng.choice(STATUSES),
        })
    df = pd.DataFrame(rows).sort_values("risk_score", ascending=False).reset_index(drop=True)
    return df


def fmt_money(n):
    return f"${n:,.0f}"


# ============================================================
# SIDEBAR
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:10px; padding-bottom:14px;
                    border-bottom:1px solid rgba(255,255,255,0.09); margin-bottom:16px;">
            <div style="width:34px;height:34px;border-radius:10px;
                        background:conic-gradient(from 220deg,#2e6bff,#22d3ee,#2e6bff);
                        display:flex;align-items:center;justify-content:center;
                        box-shadow:0 0 22px rgba(46,107,255,0.45);font-weight:800;color:#fff;">A</div>
            <div>
                <div style="font-size:15px;font-weight:700;color:#eef2fa;">Aegis</div>
                <div style="font-size:10px;letter-spacing:1.2px;text-transform:uppercase;color:#6b7488;">AML Intelligence</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.caption("DATASET")
        dataset = st.selectbox("Dataset", [
            "SAML-D Synthetic v3 (2.1M txns)",
            "IBM AML Sim — HI-Small",
            "Live Ingest — Core Banking",
        ], label_visibility="collapsed")

        st.caption("LLM MODEL")
        model = st.selectbox("Model", [
            "Claude Sonnet 4.6", "Claude Opus 4.8", "GPT-4o",
        ], label_visibility="collapsed")

        st.caption("API KEY")
        st.text_input("API Key", value="sk-ant-••••••••••••8f2a", type="password",
                       label_visibility="collapsed", disabled=True)

        st.caption("FILTERS")
        filters = st.multiselect(
            "Filters",
            ["High Risk", "Medium", "Cross-Border", "Crypto", "Shell Co."],
            default=["High Risk"], label_visibility="collapsed",
        )

        st.caption("SYSTEM STATUS")
        st.markdown("""
        <div style="font-size:12px; line-height:2.1;">
            <span style="color:#2ed598;">●</span> Graph Engine — Online<br>
            <span style="color:#2ed598;">●</span> LLM Gateway — Online<br>
            <span style="color:#f5a623;">●</span> Sanctions Feed — Sync 4m ago
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:10.5px; color:#6b7488; line-height:1.7; position:fixed; bottom:20px; width:220px;">
        Built with <b style="color:#aab3c5;">Streamlit · LangChain · NetworkX · Plotly · OpenAI</b><br>
        Hackathon 2026 — AML Intelligence Platform
        </div>
        """, unsafe_allow_html=True)

    return dataset, model, filters


# ============================================================
# DASHBOARD
# ============================================================
def render_kpi_cards(df):
    kpis = [
        ("Total Transactions", "2,148,392", "+4.2% vs last week", "neutral"),
        ("Suspicious Accounts", str(len(df[df.risk_level != "Low"])), "+18 new today", "up"),
        ("Total Laundered Est.", "$18.42M", "+2.1M this month", "up"),
        ("High-Risk Alerts", str(len(df[df.risk_level == "High"])), "7 unresolved > 24h", "up"),
        ("AI Confidence", "91.4%", "model avg. this week", "neutral"),
        ("Active Investigations", "12", "3 escalated today", "down"),
    ]
    cols = st.columns(6)
    arrows = {"up": "▲", "down": "▼", "neutral": "●"}
    for col, (label, value, delta, direction) in zip(cols, kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-delta {direction}">{arrows[direction]} {delta}</div>
            </div>
            """, unsafe_allow_html=True)


def render_dashboard(df):
    st.markdown("### Investigation Dashboard")
    st.caption("SAML-D Synthetic v3 · last refreshed 2 minutes ago")
    st.write("")

    render_kpi_cards(df)
    st.write("")

    col1, col2 = st.columns([1.4, 1])
    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Executive Summary</div>', unsafe_allow_html=True)
        rows = [
            ("Dataset", "SAML-D Synthetic v3"),
            ("Overall Risk Level", '<span class="badge High">HIGH</span>'),
            ("Top Typology", "Layering via Shell Networks"),
            ("Estimated Exposure", "$18.42M"),
            ("Accounts Under Review", str(len(df))),
        ]
        for k, v in rows:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; padding:9px 2px;
                        border-bottom:1px solid rgba(255,255,255,0.08); font-size:13px;">
                <span style="color:#6b7488;">{k}</span><span style="font-weight:600;">{v}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown("""
        <div class="recommend-box">
            <b>Recommended action:</b> Escalate 14 accounts flagged with layering + rapid
            cross-border transfer patterns for SAR filing within 24h. Freeze holds
            recommended on 3 accounts exceeding $500K exposure.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Risk Distribution</div>', unsafe_allow_html=True)
        counts = df.risk_level.value_counts()
        fig = go.Figure(data=[go.Pie(
            labels=counts.index, values=counts.values, hole=0.68,
            marker=dict(colors=[RISK_COLORS.get(l, "#888") for l in counts.index]),
            textinfo="none",
        )])
        fig.update_layout(
            showlegend=True, legend=dict(orientation="h", y=-0.1, font=dict(color="#aab3c5", size=11)),
            margin=dict(t=10, b=10, l=10, r=10), height=240,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title"><span class="dot"></span>Recent High-Risk Alerts</div>', unsafe_allow_html=True)
    top = df.head(8)[["account_id", "risk_score", "typology", "total_sent", "country", "risk_level"]].copy()
    top.columns = ["Account", "Risk", "Typology", "Amount", "Country", "Level"]
    st.dataframe(
        top, use_container_width=True, hide_index=True,
        column_config={
            "Risk": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%d"),
            "Amount": st.column_config.NumberColumn("Amount", format="$%d"),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# AI INVESTIGATOR
# ============================================================
def run_ai_investigation(query, df):
    """
    Simulated multi-stage agent reasoning. Replace the body of this
    function with a real call to your LLM/agent (e.g. Claude via the
    Anthropic API with tool use over `df`) to make this reflect the
    actual query instead of a canned result.
    """
    for title, desc in TIMELINE_STAGES:
        with st.status(title, expanded=True) as status:
            st.caption(desc)
            time.sleep(0.5)
            confidence = random.randint(82, 97)
            st.write(f"Confidence: **{confidence}%**")
            status.update(label=f"{title} — {confidence}%", state="complete")

    flagged = df.iloc[0]  # highest risk account in the dataset
    st.session_state.investigation_result = {
        "query": query,
        "account": flagged.to_dict(),
        "confidence": random.randint(88, 96),
    }
    st.session_state.investigation_done = True


def render_ai_investigator(df):
    st.markdown("### AI Investigator")
    st.caption("Ask a question in plain language — the agent plans, retrieves, and scores automatically")
    st.write("")

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    query = st.text_input(
        "Query", placeholder="e.g. Show me accounts with layering patterns above $250K in the last 30 days",
        label_visibility="collapsed", key="query_input",
    )

    run_clicked = st.button("Investigate →", type="primary")

    st.write("**Try a sample prompt:**")
    prompt_cols = st.columns(len(SAMPLE_PROMPTS))
    sample_clicked = None
    for col, prompt in zip(prompt_cols, SAMPLE_PROMPTS):
        with col:
            if st.button(prompt, key=f"sample_{prompt}", use_container_width=True):
                sample_clicked = prompt
    st.markdown("</div>", unsafe_allow_html=True)

    active_query = sample_clicked or (query if run_clicked else None)

    if active_query:
        st.session_state.investigation_done = False
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>AI Thinking Timeline</div>', unsafe_allow_html=True)
        run_ai_investigation(active_query, df)
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("investigation_done"):
        result = st.session_state.investigation_result
        acc = result["account"]
        st.success(f"Investigation complete — {result['confidence']}% confidence")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:14px; margin-bottom:14px;">
                <div style="width:52px;height:52px;border-radius:50%;
                    background:conic-gradient(#f0475b 0% {acc['risk_score']}%, rgba(255,255,255,0.08) {acc['risk_score']}% 100%);
                    display:flex;align-items:center;justify-content:center;">
                    <div style="width:42px;height:42px;border-radius:50%;background:#0a0e18;
                        display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono';
                        font-weight:700;font-size:12px;">{acc['risk_score']}</div>
                </div>
                <div>
                    <div class="mono" style="font-size:15px;font-weight:700;">{acc['account_id']}</div>
                    <div class="subtle">Risk Score {acc['risk_score']}/100 ·
                        <span class="badge {acc['risk_level']}">{acc['risk_level'].upper()}</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            m1, m2 = st.columns(2)
            m1.metric("Total Sent", fmt_money(acc["total_sent"]))
            m2.metric("Total Received", fmt_money(acc["total_received"]))
            m3, m4 = st.columns(2)
            m3.metric("Countries", acc["countries_count"])
            m4.metric("Typology", acc["typology"])

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Generate SAR", type="primary", use_container_width=True):
                    st.session_state.show_sar = True
            with b2:
                if st.button("Freeze Account", use_container_width=True):
                    st.toast(f"Account {acc['account_id']} frozen pending review", icon="🧊")
            with b3:
                if st.button("Continue Investigation", use_container_width=True):
                    st.info("Open the **Investigations** tab to continue this case.")
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title"><span class="dot"></span>Reasoning Panel</div>', unsafe_allow_html=True)
            reasons = [
                f"Flagged: transfers routed through multiple intermediary entities, consistent with {acc['typology'].lower()}.",
                f"Risk factor: rapid fund movement across {acc['countries_count']} jurisdictions.",
                "Risk factor: transaction sizes structured near common reporting thresholds.",
                f"Confidence: {result['confidence']}% — pattern matches historical typology cluster.",
                "Suggested next action: file SAR, review linked accounts.",
            ]
            for r in reasons:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.09);
                    border-radius:10px; padding:10px 12px; margin-bottom:8px; font-size:12.5px; color:#aab3c5;">
                    ⚠ {r}
                </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("show_sar"):
            render_sar_text(acc, result["confidence"])


def render_sar_text(acc, confidence):
    report = f"""SAR NARRATIVE — ACCOUNT {acc['account_id']}
Filing Institution: [Institution Name]
Prepared by: AI Investigator (reviewed by Senior Analyst)
Date: {datetime.now().strftime('%Y-%m-%d')}

SUBJECT: Account {acc['account_id']} exhibits a pattern of {acc['typology'].lower()}
consistent with known money laundering typologies.

SUMMARY OF ACTIVITY:
The subject account sent {fmt_money(acc['total_sent'])} and received
{fmt_money(acc['total_received'])} across {acc['countries_count']} jurisdictions.

RISK ASSESSMENT: {acc['risk_level'].upper()} (Score: {acc['risk_score']}/100, Model Confidence: {confidence}%)

RECOMMENDED ACTION:
File SAR with the relevant regulator within the compliance deadline.

— End of draft. Requires compliance officer sign-off before filing. —
"""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title"><span class="dot"></span>SAR Draft</div>', unsafe_allow_html=True)
    st.code(report, language=None)
    st.download_button("Download SAR (.txt)", report, file_name=f"SAR_{acc['account_id']}.txt")
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# INVESTIGATIONS
# ============================================================
def render_investigations(df):
    st.markdown("### Investigations")
    st.caption(f"{len(df)} accounts under active review")
    st.write("")
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    show = df[["account_id", "risk_score", "typology", "total_sent", "countries_count", "analyst", "status"]].copy()
    show.columns = ["Account", "Risk Score", "Typology", "Total Sent", "Countries", "Analyst", "Status"]
    st.dataframe(
        show, use_container_width=True, hide_index=True, height=560,
        column_config={
            "Risk Score": st.column_config.ProgressColumn("Risk Score", min_value=0, max_value=100, format="%d"),
            "Total Sent": st.column_config.NumberColumn("Total Sent", format="$%d"),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Export CSV", csv, file_name="aegis_accounts_export.csv")


# ============================================================
# GRAPH EXPLORER
# ============================================================
def build_network(df, min_risk, min_amount, typology_filter, n=26, seed=7):
    rng = random.Random(seed)
    subset = df.head(n).reset_index(drop=True)
    G = nx.Graph()
    for _, row in subset.iterrows():
        G.add_node(row["account_id"], **row.to_dict())
    edges = []
    for i, row in subset.iterrows():
        for _ in range(rng.randint(1, 3)):
            j = rng.randint(0, len(subset) - 1)
            if j != i:
                amount = rng.randint(5_000, 480_000)
                prob = rng.uniform(0.1, 0.98)
                edges.append((subset.iloc[i]["account_id"], subset.iloc[j]["account_id"], amount, prob))
                G.add_edge(subset.iloc[i]["account_id"], subset.iloc[j]["account_id"], amount=amount, prob=prob)
    pos = nx.spring_layout(G, seed=seed, k=0.9)

    fig = go.Figure()
    for u, v, amount, prob in edges:
        if amount < min_amount:
            continue
        row_u = subset[subset.account_id == u].iloc[0]
        if row_u.risk_score < min_risk:
            continue
        if typology_filter != "All" and row_u.typology != typology_filter:
            continue
        color = "#f0475b" if prob > 0.66 else "#f5a623" if prob > 0.35 else "#2ed598"
        x0, y0 = pos[u]; x1, y1 = pos[v]
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(width=max(0.8, amount / 90000), color=color),
            opacity=0.55, hoverinfo="skip", showlegend=False,
        ))

    node_x, node_y, node_color, node_size, node_text = [], [], [], [], []
    for node_id in G.nodes():
        row = subset[subset.account_id == node_id].iloc[0]
        if row.risk_score < min_risk:
            continue
        if typology_filter != "All" and row.typology != typology_filter:
            continue
        x, y = pos[node_id]
        node_x.append(x); node_y.append(y)
        node_color.append(RISK_COLORS[row.risk_level])
        node_size.append(10 + (row.risk_score / 100) * 26)
        node_text.append(
            f"<b>{row.account_id}</b><br>Risk: {row.risk_score} ({row.risk_level})"
            f"<br>Typology: {row.typology}<br>Sent: {fmt_money(row.total_sent)}<br>Country: {row.country}"
        )
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers", marker=dict(size=node_size, color=node_color,
        line=dict(width=1, color="rgba(255,255,255,0.3)")),
        hovertext=node_text, hoverinfo="text", showlegend=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(t=10, b=10, l=10, r=10), height=560,
    )
    return fig


def render_graph_explorer(df):
    st.markdown("### Graph Explorer")
    st.caption("Node size = risk score · edge width = amount · edge color = laundering probability")
    st.write("")

    col_filters, col_graph = st.columns([1, 3])
    with col_filters:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        min_risk = st.slider("Min Risk Score", 0, 100, 0)
        min_amount = st.slider("Min Edge Amount ($)", 0, 500_000, 0, step=10_000)
        typology_filter = st.selectbox("Typology", ["All"] + TYPOLOGIES)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Legend</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:12px; line-height:2;">
        <span style="color:#f0475b;">●</span> High risk node<br>
        <span style="color:#f5a623;">●</span> Medium risk node<br>
        <span style="color:#2ed598;">●</span> Low risk node
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_graph:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        fig = build_network(df, min_risk, min_amount, typology_filter)
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ANALYTICS
# ============================================================
def render_analytics(df):
    st.markdown("### Analytics")
    st.caption("Portfolio-wide typology, exposure and behavioral patterns")
    st.write("")

    plotly_dark = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#aab3c5"), margin=dict(t=20, b=20, l=20, r=20), height=260)

    row1 = st.columns(3)
    with row1[0]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Typology Distribution</div>', unsafe_allow_html=True)
        counts = df.typology.value_counts()
        fig = go.Figure([go.Bar(x=counts.index, y=counts.values, marker_color=BLUE)])
        fig.update_layout(**plotly_dark)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with row1[1]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Payment Methods</div>', unsafe_allow_html=True)
        methods = pd.Series({"Wire Transfer": 34, "Crypto": 26, "Card": 18, "Cash": 12, "ACH": 10})
        fig = go.Figure([go.Pie(labels=methods.index, values=methods.values, hole=0.35,
                                 marker=dict(colors=["#2e6bff", "#22d3ee", "#f5a623", "#f0475b", "#2ed598"]))])
        fig.update_layout(**plotly_dark)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with row1[2]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Country Exposure</div>', unsafe_allow_html=True)
        exposure = df.groupby("country")["total_sent"].sum().sort_values(ascending=True).tail(7)
        fig = go.Figure([go.Bar(x=exposure.values, y=exposure.index, orientation="h", marker_color=CYAN)])
        fig.update_layout(**plotly_dark)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    row2 = st.columns(3)
    with row2[0]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Hourly Activity</div>', unsafe_allow_html=True)
        hours = list(range(24))
        vals = [random.randint(20, 180) for _ in hours]
        fig = go.Figure([go.Scatter(x=hours, y=vals, mode="lines", fill="tozeroy",
                                     line=dict(color=BLUE), fillcolor="rgba(46,107,255,0.15)")])
        fig.update_layout(**plotly_dark)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with row2[1]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Risk Distribution</div>', unsafe_allow_html=True)
        counts = df.risk_level.value_counts()
        fig = go.Figure([go.Pie(labels=counts.index, values=counts.values, hole=0.6,
                                 marker=dict(colors=[RISK_COLORS.get(l, "#888") for l in counts.index]))])
        fig.update_layout(**plotly_dark)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with row2[2]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Monthly Trends</div>', unsafe_allow_html=True)
        months = ["Feb", "Mar", "Apr", "May", "Jun", "Jul"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=[2.1, 3.4, 2.8, 4.6, 5.2, 6.1], name="Flagged Volume",
                                  line=dict(color="#f0475b")))
        fig.add_trace(go.Scatter(x=months, y=[1.2, 1.8, 2.0, 2.4, 2.9, 3.3], name="Cases Closed",
                                  line=dict(color="#2ed598")))
        fig.update_layout(**plotly_dark, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# REPORTS
# ============================================================
def render_reports(df):
    st.markdown("### Reports")
    st.caption("Generate compliance-ready documents in one click")
    st.write("")

    high_risk = df[df.risk_level == "High"]
    cols = st.columns(3)

    with cols[0]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("**📈 Executive Report**")
        st.caption("Portfolio-level summary of risk exposure, typologies and recommended actions.")
        if st.button("Generate Executive Report", use_container_width=True, type="primary"):
            report = f"""EXECUTIVE SUMMARY REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Overall Risk Level: HIGH
Total Accounts Reviewed: {len(df)}
High-Risk Accounts: {len(high_risk)}
Estimated Laundering Exposure: $18.42M
Top Typology: {df.typology.value_counts().idxmax()}

KEY FINDINGS:
- {len(high_risk)} accounts flagged as high risk.
- Recommend SAR filing review for top-risk accounts.
"""
            st.code(report, language=None)
            st.download_button("Download (.txt)", report, file_name="executive_report.txt")
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[1]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("**🚨 Suspicious Activity Report**")
        st.caption("Regulator-ready SAR narrative for the top flagged account.")
        if st.button("Generate SAR", use_container_width=True, type="primary"):
            acc = df.iloc[0]
            render_sar_text(acc, random.randint(88, 96))
        st.markdown("</div>", unsafe_allow_html=True)

    with cols[2]:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("**🔍 Investigation Summary**")
        st.caption("Case-file summary combining reasoning trail and graph context.")
        if st.button("Generate Summary", use_container_width=True, type="primary"):
            acc = df.iloc[0]
            report = f"""INVESTIGATION CASE FILE
Account: {acc.account_id}
Status: Escalated

REASONING TRAIL:
1. Intent Detection — targeted account review
2. Entity Extraction — linked entities identified
3. Graph Analysis — layering path confirmed
4. Risk Scoring — composite score {acc.risk_score}/100
5. Recommendation — file SAR, review linked accounts
"""
            st.code(report, language=None)
            st.download_button("Download (.txt)", report, file_name=f"summary_{acc.account_id}.txt")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("🗃 Export full dataset (CSV)", csv, file_name="aegis_accounts_export.csv")


# ============================================================
# SETTINGS
# ============================================================
def render_settings():
    st.markdown("### Settings")
    st.caption("Platform configuration")
    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>General</div>', unsafe_allow_html=True)
        st.toggle("Real-time alert stream", value=True)
        st.toggle("Sound notifications", value=False)
        st.toggle("Auto-generate SAR draft on high risk", value=False)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title"><span class="dot"></span>Model &amp; Access</div>', unsafe_allow_html=True)
        st.selectbox("Model", ["Claude Sonnet 4.6", "Claude Opus 4.8", "GPT-4o"])
        st.slider("Confidence threshold", 0, 100, 75)
        st.toggle("Two-factor authentication", value=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# MAIN
# ============================================================
def main():
    inject_css()
    if "investigation_done" not in st.session_state:
        st.session_state.investigation_done = False
    if "show_sar" not in st.session_state:
        st.session_state.show_sar = False

    render_sidebar()
    df = generate_accounts()

    tabs = st.tabs([
        "▣ Dashboard", "✦ AI Investigator", "🗂 Investigations",
        "◈ Graph Explorer", "📊 Analytics", "📄 Reports", "⚙ Settings",
    ])
    with tabs[0]:
        render_dashboard(df)
    with tabs[1]:
        render_ai_investigator(df)
    with tabs[2]:
        render_investigations(df)
    with tabs[3]:
        render_graph_explorer(df)
    with tabs[4]:
        render_analytics(df)
    with tabs[5]:
        render_reports(df)
    with tabs[6]:
        render_settings()


if __name__ == "__main__":
    main()
