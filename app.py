"""
app.py — Streamlit Frontend for AI-Powered AML Agent.

A multi-panel dashboard that provides:
  - Sidebar: Dataset configuration, API key entry, model selection
  - Query Interface: Natural language input with sample query buttons
  - Response Section: Agent execution summary, risk tables, network graphs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from src.agent import create_aml_agent, run_agent_query
from src.graph_engine import load_accounts_data, load_aml_data, load_patterns_data
from src.metrics import MetricsCollector, format_efficiency_dashboard
from src.utils import (
    APP_SUBTITLE,
    APP_TITLE,
    AVAILABLE_DATASETS,
    DATASET_BY_NAME,
    DATASET_FORMAT_SAML,
    DEFAULT_DATASET_NAME,
    LAUNDERING_TYPOLOGY_COLORS,
    EDGE_COLORS,
    NODE_COLORS,
    RISK_COLORS,
    SAMPLE_QUERIES,
    format_currency,
    format_number,
)

# Load environment variables
load_dotenv()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AML Agent — Suspicious Activity Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* ── Global ────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ── Header ────────────────────────────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .main-header h1 {
        color: #FFFFFF;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #B0C4DE;
        font-size: 1.05rem;
        margin: 0.3rem 0 0;
        font-weight: 300;
    }

    /* ── Metric Cards ──────────────────────────────────────── */
    .metric-card {
        background: linear-gradient(145deg, #1A1A2E, #16213E);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
    }
    .metric-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #4FC3F7;
    }
    .metric-card .label {
        font-size: 0.85rem;
        color: #90A4AE;
        margin-top: 0.3rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ── Risk Badges ───────────────────────────────────────── */
    .risk-high {
        background: linear-gradient(135deg, #FF4B4B, #CC0000);
        color: white; padding: 4px 14px; border-radius: 20px;
        font-weight: 700; font-size: 0.8em; display: inline-block;
    }
    .risk-medium {
        background: linear-gradient(135deg, #FFA500, #CC8400);
        color: white; padding: 4px 14px; border-radius: 20px;
        font-weight: 700; font-size: 0.8em; display: inline-block;
    }
    .risk-low {
        background: linear-gradient(135deg, #4CAF50, #2E7D32);
        color: white; padding: 4px 14px; border-radius: 20px;
        font-weight: 700; font-size: 0.8em; display: inline-block;
    }

    /* ── Tool Usage Tags ───────────────────────────────────── */
    .tool-tag {
        background: linear-gradient(135deg, #4A90D9, #357ABD);
        color: white; padding: 5px 14px; border-radius: 20px;
        font-size: 0.8em; font-weight: 600; display: inline-block;
        margin: 3px 4px;
    }

    /* ── Section Containers ────────────────────────────────── */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #E0E0E0;
        margin: 1.5rem 0 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(74, 144, 217, 0.3);
    }

    /* ── Query Buttons ─────────────────────────────────────── */
    .stButton > button {
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    /* ── Sidebar Styling ───────────────────────────────────── */
    .sidebar-section {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="main-header">
    <h1>{APP_TITLE}</h1>
    <p>{APP_SUBTITLE}</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    # Dataset configuration
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("### 📁 Dataset")
    dataset_names = [d["name"] for d in AVAILABLE_DATASETS]
    default_idx = dataset_names.index(DEFAULT_DATASET_NAME) if DEFAULT_DATASET_NAME in dataset_names else 0
    selected_dataset = st.selectbox(
        "Dataset",
        options=dataset_names,
        index=default_idx,
        help="IBM archive variants or SAML-D (17 typology labels + geo data).",
    )
    dataset_meta = DATASET_BY_NAME[selected_dataset]
    csv_path = dataset_meta["trans_path"]
    st.caption(dataset_meta.get("description", ""))
    st.caption(f"**Size:** {dataset_meta.get('size_label', '—')} · **Intensity:** {dataset_meta.get('intensity', '—')}")

    with st.expander("Advanced path override"):
        csv_path = st.text_input(
            "Transactions CSV path",
            value=csv_path,
            help="Override the path for the selected dataset variant.",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # LLM configuration
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("### 🤖 LLM Settings")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Enter your OpenAI API key. Also supports .env file.",
    )
    model_name = st.selectbox(
        "Model",
        options=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        index=0,
        help="Select the OpenAI model for the agent.",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Status indicators
    st.markdown("---")
    st.markdown("### 📊 System Status")

    if "df" in st.session_state and st.session_state.df is not None:
        ds_label = st.session_state.get("dataset_name", "Loaded dataset")
        fmt = st.session_state.get("dataset_format", "—")
        st.success(f"✅ {ds_label}: {len(st.session_state.df):,} transactions ({fmt})")
        st.info(f"🔗 Graph: {st.session_state.G.number_of_nodes():,} nodes, "
                f"{st.session_state.G.number_of_edges():,} edges")
    else:
        st.warning("⏳ Dataset not loaded yet")

    if api_key:
        st.success("🔑 API key configured")
    else:
        st.error("🔑 API key required")

    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666; font-size: 0.8em;'>"
        "Built for Hackathon 2026<br>AI-Powered AML Detection</p>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING (Cached)
# ═══════════════════════════════════════════════════════════════════════════════


@st.cache_resource(show_spinner=False)
def _load_data(path: str):
    """Load and cache the AML dataset and graph."""
    return load_aml_data(path)


@st.cache_data(show_spinner=False)
def _load_accounts_cached(path: str) -> Optional[pd.DataFrame]:
    return load_accounts_data(path)


@st.cache_data(show_spinner=False)
def _load_patterns_cached(path: str) -> Dict[str, Any]:
    return load_patterns_data(path)


# Load data button / auto-load
if "df" not in st.session_state:
    st.session_state.df = None
    st.session_state.G = None
    st.session_state.dataset_format = None
    st.session_state.dataset_name = None
    st.session_state.accounts_df = None
    st.session_state.patterns_data = None
    st.session_state.metrics_collector = MetricsCollector()

col_load1, col_load2 = st.columns([3, 1])
with col_load1:
    if st.session_state.df is None:
        st.info("👆 Click **Load Dataset** or ensure the CSV path is correct in the sidebar.")
with col_load2:
    if st.button("📂 Load Dataset", use_container_width=True):
        try:
            with st.spinner("Loading dataset and building transaction graph…"):
                df, G, fmt = _load_data(csv_path)
                st.session_state.df = df
                st.session_state.G = G
                st.session_state.dataset_format = fmt
                st.session_state.dataset_name = selected_dataset
                accounts_path = dataset_meta.get("accounts_path")
                patterns_path = dataset_meta.get("patterns_path")
                st.session_state.accounts_df = (
                    _load_accounts_cached(accounts_path) if accounts_path else None
                )
                st.session_state.patterns_data = (
                    _load_patterns_cached(patterns_path) if patterns_path else {}
                )
            st.success("Dataset loaded successfully!")
            st.rerun()
        except FileNotFoundError as e:
            st.error(f"❌ {str(e)}")
        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET OVERVIEW METRICS
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.df is not None:
    df = st.session_state.df
    G = st.session_state.G
    ds_name = st.session_state.get("dataset_name", "Dataset")
    ds_fmt = st.session_state.get("dataset_format", "")

    st.markdown(
        f"**Active dataset:** {ds_name} "
        f"({'SAML-D — typology + geo' if ds_fmt == DATASET_FORMAT_SAML else 'IBM Synthetic AML'})"
    )

    # Quick metrics row
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{format_number(len(df))}</div>
            <div class="label">Total Transactions</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{format_currency(float(df['amount'].sum()))}</div>
            <div class="label">Total Volume</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{format_number(G.number_of_nodes())}</div>
            <div class="label">Unique Accounts</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        flagged_pct = (df["is_laundering"].sum() / len(df)) * 100 if len(df) else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="value">{flagged_pct:.2f}%</div>
            <div class="label">Flagged Laundering</div>
        </div>
        """, unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="value" style="font-size:1.1rem;">{ds_fmt.upper() if ds_fmt else "—"}</div>
            <div class="label">Format</div>
        </div>
        """, unsafe_allow_html=True)

    overview_tab, accounts_tab = st.tabs(["📈 Overview", "🏦 Accounts (IBM)"])

    with overview_tab:
        if ds_fmt == DATASET_FORMAT_SAML and "laundering_type" in df.columns:
            st.markdown("**Laundering typology distribution (flagged transactions)**")
            typ_series = (
                df.loc[df["is_laundering"] == 1, "laundering_type"]
                .value_counts()
                .head(20)
            )
            typ_series = typ_series[~typ_series.index.astype(str).str.startswith("Normal")]
            if len(typ_series) > 0:
                colors = [
                    LAUNDERING_TYPOLOGY_COLORS.get(str(t), "#4A90D9")
                    for t in typ_series.index
                ]
                fig_typ = go.Figure(data=[go.Bar(
                    x=typ_series.index.astype(str),
                    y=typ_series.values,
                    marker_color=colors,
                )])
                fig_typ.update_layout(
                    plot_bgcolor="#0E1117",
                    paper_bgcolor="#0E1117",
                    font=dict(color="#E0E0E0"),
                    height=360,
                    margin=dict(l=40, r=20, t=20, b=120),
                    xaxis_tickangle=-45,
                )
                st.plotly_chart(fig_typ, use_container_width=True)
            else:
                st.info("No non-normal laundering typologies in the sample.")

        payment_dist = df["payment_format"].value_counts().head(8)
        if len(payment_dist) > 0:
            st.markdown("**Payment format mix**")
            fig_pay = go.Figure(data=[go.Bar(
                x=payment_dist.index.astype(str),
                y=payment_dist.values,
                marker_color="#4A90D9",
            )])
            fig_pay.update_layout(
                plot_bgcolor="#0E1117",
                paper_bgcolor="#0E1117",
                font=dict(color="#E0E0E0"),
                height=280,
                margin=dict(l=40, r=20, t=20, b=40),
            )
            st.plotly_chart(fig_pay, use_container_width=True)

    with accounts_tab:
        acc_df = st.session_state.get("accounts_df")
        if acc_df is not None and len(acc_df) > 0:
            st.markdown(f"**{len(acc_df):,}** account records from IBM `_accounts.csv`")
            st.dataframe(acc_df.head(500), use_container_width=True, hide_index=True)
            st.caption("Showing first 500 rows.")
        else:
            st.info(
                "Account metadata is available for IBM archive datasets that include "
                "`_accounts.csv`. SAML-D does not ship a separate accounts file."
            )

    st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">💬 Query the AML Agent</div>', unsafe_allow_html=True)

# Sample query buttons
st.markdown("**Quick Queries:**")
query_cols = st.columns(len(SAMPLE_QUERIES))
for idx, sq in enumerate(SAMPLE_QUERIES):
    with query_cols[idx]:
        if st.button(sq["label"], key=f"sample_{idx}", use_container_width=True):
            st.session_state.current_query = sq["query"]

# Text input
query_input = st.text_area(
    "Enter your query",
    value=st.session_state.get("current_query", ""),
    height=80,
    placeholder="Ask the AML agent anything about the transaction data…",
    label_visibility="collapsed",
)

# Run button
run_col1, run_col2, run_col3 = st.columns([1, 2, 1])
with run_col2:
    run_query = st.button(
        "🚀 Run Agent Query",
        use_container_width=True,
        type="primary",
        disabled=(st.session_state.df is None),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK GRAPH VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════════════


def build_network_graph(
    edges: List[Dict],
    title: str,
    graph_type: str = "smurfing",
    flagged_accounts: Optional[List[str]] = None,
) -> go.Figure:
    """Build an interactive Plotly network graph from edge data.

    Args:
        edges: List of dicts with 'source', 'target', 'amount' keys.
        title: Graph title.
        graph_type: Type of graph ('smurfing' or 'cycle').
        flagged_accounts: List of account IDs to highlight as targets.

    Returns:
        Plotly Figure with network visualization.
    """
    if not edges:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            annotations=[{
                "text": "No edges to visualize",
                "xref": "paper", "yref": "paper",
                "showarrow": False, "font": {"size": 16},
            }],
        )
        return fig

    # Build a subgraph for layout
    sub_G = nx.DiGraph()
    for edge in edges[:100]:  # Limit for performance
        sub_G.add_edge(edge["source"], edge["target"], amount=edge.get("amount", 0))

    # Compute layout
    try:
        pos = nx.spring_layout(sub_G, k=2.0, iterations=50, seed=42)
    except Exception:
        pos = nx.kamada_kawai_layout(sub_G)

    flagged_set = set(flagged_accounts) if flagged_accounts else set()

    # ── Edge traces ───────────────────────────────────────────────────────
    edge_x, edge_y = [], []
    edge_hover = []
    for edge in edges[:100]:
        if edge["source"] in pos and edge["target"] in pos:
            x0, y0 = pos[edge["source"]]
            x1, y1 = pos[edge["target"]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(
            width=1.5,
            color=EDGE_COLORS.get(graph_type, EDGE_COLORS["normal"]),
        ),
        hoverinfo="none",
        mode="lines",
        opacity=0.5,
    )

    # ── Node traces ───────────────────────────────────────────────────────
    node_x, node_y, node_text, node_colors, node_sizes = [], [], [], [], []

    for node in sub_G.nodes():
        if node not in pos:
            continue
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        deg = sub_G.degree(node)
        # Truncate long node names for display
        display_name = str(node)[-12:] if len(str(node)) > 12 else str(node)

        if node in flagged_set:
            node_colors.append(NODE_COLORS["target"])
            node_sizes.append(max(18, min(35, 10 + deg * 2)))
            node_text.append(f"🚨 {display_name}<br>Degree: {deg}")
        elif graph_type == "cycle":
            node_colors.append(NODE_COLORS["cycle"])
            node_sizes.append(max(14, min(28, 8 + deg * 2)))
            node_text.append(f"🔄 {display_name}<br>Degree: {deg}")
        else:
            node_colors.append(NODE_COLORS["source"])
            node_sizes.append(max(10, min(22, 6 + deg * 2)))
            node_text.append(f"{display_name}<br>Degree: {deg}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        hoverinfo="text",
        hovertext=node_text,
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=1.5, color="#FFFFFF"),
            opacity=0.9,
        ),
    )

    # ── Figure layout ─────────────────────────────────────────────────────
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=16, color="#E0E0E0"),
        ),
        showlegend=False,
        hovermode="closest",
        plot_bgcolor="#0E1117",
        paper_bgcolor="#0E1117",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=50, b=20),
        height=500,
        font=dict(color="#E0E0E0"),
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS RENDERING
# ═══════════════════════════════════════════════════════════════════════════════


def render_eda_results(data: Dict[str, Any]) -> None:
    """Render EDA results with formatted metrics and tables."""
    summary = data.get("summary", {})

    st.markdown('<div class="section-header">📊 Exploratory Data Analysis Results</div>',
                unsafe_allow_html=True)

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Transactions", format_number(summary.get("total_transactions", 0)))
    with c2:
        st.metric("Total Volume", format_currency(summary.get("total_volume_usd", 0)))
    with c3:
        st.metric("Avg Amount", format_currency(summary.get("average_amount_usd", 0)))
    with c4:
        st.metric("Flagged Count", format_number(summary.get("flagged_laundering_count", 0)))
    with c5:
        ratio = summary.get("flagged_laundering_ratio", 0)
        st.metric("Flagged Ratio", f"{ratio:.2%}")

    # Tables
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Top 5 Senders**")
        senders = data.get("top_5_senders", [])
        if senders:
            st.dataframe(pd.DataFrame(senders), use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("**Top 5 Receivers**")
        receivers = data.get("top_5_receivers", [])
        if receivers:
            st.dataframe(pd.DataFrame(receivers), use_container_width=True, hide_index=True)

    # Payment format distribution
    payment_dist = data.get("payment_format_distribution", [])
    if payment_dist:
        st.markdown("**Payment Format Distribution**")
        pdf = pd.DataFrame(payment_dist)
        fig = go.Figure(data=[go.Bar(
            x=pdf.get("format", pdf.columns[0]),
            y=pdf.get("count", pdf.columns[-1]),
            marker_color=["#4A90D9", "#FF6B35", "#4CAF50", "#FFD700", "#9C27B0"],
        )])
        fig.update_layout(
            plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
            font=dict(color="#E0E0E0"), height=300,
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    lt_dist = data.get("laundering_type_distribution", [])
    if lt_dist:
        st.markdown("**Laundering Type Distribution (top flagged)**")
        ldf = pd.DataFrame(lt_dist)
        fig_lt = go.Figure(data=[go.Bar(
            x=ldf.get("type", ldf.columns[0]),
            y=ldf.get("count", ldf.columns[-1]),
            marker_color="#FF6B35",
        )])
        fig_lt.update_layout(
            plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
            font=dict(color="#E0E0E0"), height=300,
            margin=dict(l=40, r=20, t=20, b=80),
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig_lt, use_container_width=True)


def render_risk_table(accounts: List[Dict[str, Any]], title: str) -> None:
    """Render a risk results table with color-coded badges."""
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

    if not accounts:
        st.info("No suspicious accounts detected with the current parameters.")
        return

    # Build display DataFrame
    rows = []
    for acc in accounts[:30]:  # Limit display
        level = acc.get("risk_level", "LOW")
        badge_class = f"risk-{level.lower()}"
        rows.append({
            "Account": acc.get("account", "N/A"),
            "Risk Score": acc.get("risk_score", 0),
            "Risk Level": level,
            "Explanation": acc.get("explanation", "")[:150] + "…" if len(acc.get("explanation", "")) > 150 else acc.get("explanation", ""),
            "Action": acc.get("recommended_action", "N/A"),
        })

    display_df = pd.DataFrame(rows)

    # Color the risk score column
    def color_risk(val):
        if val >= 75:
            return "background-color: rgba(255, 75, 75, 0.3); color: #FF4B4B; font-weight: bold"
        elif val >= 50:
            return "background-color: rgba(255, 165, 0, 0.3); color: #FFA500; font-weight: bold"
        return "background-color: rgba(76, 175, 80, 0.3); color: #4CAF50; font-weight: bold"

    def color_level(val):
        colors = {"HIGH": "#FF4B4B", "MEDIUM": "#FFA500", "LOW": "#4CAF50"}
        return f"color: {colors.get(val, '#FFF')}; font-weight: bold"

    styled = display_df.style.map(
        color_risk, subset=["Risk Score"]
    ).map(
        color_level, subset=["Risk Level"]
    )

    st.dataframe(styled, use_container_width=True, hide_index=True, height=400)


def render_entity_profile(data: Dict[str, Any]) -> None:
    """Render single entity lookup results."""
    st.markdown('<div class="section-header">🔍 Entity Profile</div>',
                unsafe_allow_html=True)

    if data.get("status") == "NOT_FOUND":
        st.warning(data.get("message", "Account not found."))
        return

    profile = data.get("profile", {})
    risk = data.get("risk_assessment", {})

    # Profile metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("In-Degree", profile.get("in_degree", 0))
    with c2:
        st.metric("Out-Degree", profile.get("out_degree", 0))
    with c3:
        st.metric("Total Received", format_currency(profile.get("total_received_usd", 0)))
    with c4:
        st.metric("Total Sent", format_currency(profile.get("total_sent_usd", 0)))

    # Risk assessment
    risk_score = risk.get("risk_score", 0)
    risk_level = risk.get("risk_level", "LOW")
    risk_color = RISK_COLORS.get(risk_level, "#FFF")

    st.markdown(f"""
    <div style="background: linear-gradient(145deg, #1A1A2E, #16213E);
                border-radius: 12px; padding: 1.5rem; margin: 1rem 0;
                border-left: 4px solid {risk_color};">
        <h3 style="margin: 0; color: {risk_color};">
            Risk Score: {risk_score}/100 — {risk_level}
        </h3>
        <p style="color: #B0C4DE; margin: 0.5rem 0 0;">
            Recommended Action: <strong>{risk.get("recommended_action", "N/A")}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Risk factors
    st.markdown("**Risk Factors:**")
    for factor in risk.get("risk_factors", []):
        st.markdown(f"- ⚠️ {factor}")

    # Additional profile details
    with st.expander("📋 Full Profile Details"):
        st.json(data)


def render_typology_results(data: Dict[str, Any]) -> None:
    """Render Typology Analyzer breakdown."""
    st.markdown(
        '<div class="section-header">🗺️ Laundering Typology Analysis</div>',
        unsafe_allow_html=True,
    )

    summary = data.get("summary", {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Laundering txns", format_number(summary.get("total_laundering_transactions", 0)))
    with c2:
        st.metric("Unique typologies", summary.get("unique_typologies", 0))
    with c3:
        st.metric("High-risk types", summary.get("high_risk_typologies_count", 0))
    with c4:
        st.metric("Explicit labels", "Yes" if data.get("has_explicit_typology_labels") else "No")

    ibm_pat = data.get("ibm_patterns_summary")
    if ibm_pat:
        st.info(
            f"IBM Patterns.txt: **{ibm_pat.get('total_attempts', 0)}** ground-truth attempts "
            f"({len(ibm_pat.get('typology_counts', {}))} typology kinds)."
        )

    breakdown = data.get("typology_breakdown", [])
    if not breakdown:
        st.warning("No typology breakdown available for this dataset.")
        return

    rows = []
    for row in breakdown[:30]:
        rows.append({
            "Typology": row.get("typology"),
            "Count": row.get("count"),
            "% of laundering": row.get("pct_of_laundering"),
            "Volume (USD)": row.get("total_volume_usd"),
            "Risk": row.get("risk_level"),
            "Description": (row.get("description") or "")[:120],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    chart_rows = [
        r for r in breakdown
        if r.get("count") and not str(r.get("typology", "")).startswith("Flagged via")
    ][:20]
    if chart_rows:
        labels = [str(r["typology"]) for r in chart_rows]
        counts = [r["count"] for r in chart_rows]
        colors = [LAUNDERING_TYPOLOGY_COLORS.get(l, "#4A90D9") for l in labels]
        fig = go.Figure(data=[go.Bar(x=labels, y=counts, marker_color=colors)])
        fig.update_layout(
            title="Typology frequency",
            plot_bgcolor="#0E1117",
            paper_bgcolor="#0E1117",
            font=dict(color="#E0E0E0"),
            height=380,
            margin=dict(l=40, r=20, t=40, b=120),
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig, use_container_width=True)


def render_geo_risk_results(data: Dict[str, Any]) -> None:
    """Render Geo Risk Analyzer cross-border results."""
    st.markdown(
        '<div class="section-header">🌍 Geographic Risk Analysis</div>',
        unsafe_allow_html=True,
    )

    if not data.get("has_geo_data"):
        st.warning(data.get("note", "Geographic data not available for this dataset."))
        return

    summary = data.get("summary", {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Cross-border txns", format_number(summary.get("cross_border_transactions", 0)))
    with c2:
        st.metric("Cross-border %", f"{summary.get('cross_border_pct', 0):.2f}%")
    with c3:
        st.metric("CB laundering", format_number(summary.get("cross_border_laundering_count", 0)))
    with c4:
        st.metric("Countries (approx.)", summary.get("unique_countries", 0))

    corridors = data.get("top_corridors", [])
    if corridors:
        st.markdown("**Top cross-border corridors**")
        cdf = pd.DataFrame(corridors)
        fig = go.Figure(data=[go.Bar(
            x=cdf["corridor"],
            y=cdf["transaction_count"],
            marker_color=[
                RISK_COLORS.get(r, "#4A90D9") for r in cdf.get("risk_level", [])
            ] if "risk_level" in cdf.columns else "#9C27B0",
            text=cdf.get("laundering_ratio"),
            hovertemplate="%{x}<br>Txns: %{y}<extra></extra>",
        )])
        fig.update_layout(
            plot_bgcolor="#0E1117",
            paper_bgcolor="#0E1117",
            font=dict(color="#E0E0E0"),
            height=360,
            margin=dict(l=40, r=20, t=20, b=120),
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig, use_container_width=True)

    countries = data.get("country_risk_summary", [])
    if countries:
        st.markdown("**Country exposure (laundering volume)**")
        country_df = pd.DataFrame(countries)
        fig2 = go.Figure(data=[go.Bar(
            x=country_df["country"],
            y=country_df["total_laundering_transactions"],
            marker_color="#FF6B35",
        )])
        fig2.update_layout(
            plot_bgcolor="#0E1117",
            paper_bgcolor="#0E1117",
            font=dict(color="#E0E0E0"),
            height=320,
            margin=dict(l=40, r=20, t=20, b=80),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(country_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if run_query and query_input and st.session_state.df is not None:
    st.markdown("---")
    st.markdown('<div class="section-header">🤖 Agent Execution</div>',
                unsafe_allow_html=True)

    with st.spinner("🔄 Agent is analyzing your query…"):
        try:
            # Create agent
            executor = create_aml_agent(
                df=st.session_state.df,
                G=st.session_state.G,
                api_key=api_key,
                model_name=model_name,
                dataset_format=st.session_state.get("dataset_format") or "ibm",
                patterns_data=st.session_state.get("patterns_data"),
            )

            # Run query
            result = run_agent_query(executor, query_input)

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            result = None

    if result and not result.get("error"):
        # ── Execution Summary ─────────────────────────────────────────────
        st.markdown("### 📋 Execution Summary")

        tools_used = result.get("tools_used", [])
        
        # Log to metrics
        st.session_state.metrics_collector.log_query(query_input, tools_used)

        summary_col1, summary_col2 = st.columns(2)
        with summary_col1:
            st.markdown("**Query:**")
            st.info(query_input)
        with summary_col2:
            st.markdown("**Tools Invoked:**")
            if tools_used:
                tags = " ".join(
                    f'<span class="tool-tag">{t}</span>' for t in tools_used
                )
                st.markdown(tags, unsafe_allow_html=True)
            else:
                st.markdown("_No tools were invoked._")

        # ── Agent Response ────────────────────────────────────────────────
        st.markdown("### 💡 Agent Analysis")
        st.markdown(result.get("output", "No response."))

        # ── Tool-Specific Visualizations ──────────────────────────────────
        for tool_out in result.get("tool_outputs", []):
            tool_name = tool_out.get("tool", "")
            data = tool_out.get("output", {})

            if not isinstance(data, dict):
                continue

            if tool_name == "Automated_EDA":
                render_eda_results(data)

            elif tool_name == "Smurfing_Detector":
                flagged = data.get("flagged_accounts", [])
                render_risk_table(flagged, "🕵️ Smurfing Detection — Flagged Accounts")

                # Network graph
                edges = data.get("subgraph_edges", [])
                if edges:
                    flagged_ids = [a["account"] for a in flagged[:20]]
                    fig = build_network_graph(
                        edges=edges,
                        title="Smurfing Network — Fan-In Pattern Visualization",
                        graph_type="smurfing",
                        flagged_accounts=flagged_ids,
                    )
                    st.plotly_chart(fig, use_container_width=True)

            elif tool_name == "Cycle_Detector":
                cycles = data.get("detected_cycles", [])
                if cycles:
                    # Render cycles as risk table
                    cycle_accounts = []
                    for c in cycles:
                        cycle_accounts.append({
                            "account": f"Cycle #{c.get('cycle_id', '?')}",
                            "risk_score": c.get("risk_score", 95),
                            "risk_level": c.get("risk_level", "HIGH"),
                            "explanation": c.get("explanation", ""),
                            "recommended_action": c.get("recommended_action", "FILE SAR REPORT"),
                        })
                    render_risk_table(cycle_accounts, "🔄 Cycle Detection — Layering Networks")

                    # Network graph
                    edges = data.get("cycle_edges", [])
                    if edges:
                        all_cycle_nodes = []
                        for c in cycles:
                            all_cycle_nodes.extend(c.get("accounts_involved", []))
                        fig = build_network_graph(
                            edges=edges,
                            title="Circular Layering Network — Cycle Visualization",
                            graph_type="cycle",
                            flagged_accounts=all_cycle_nodes,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No circular money loops detected in the current dataset.")

            elif tool_name == "Single_Entity_Lookup":
                render_entity_profile(data)

            elif tool_name == "Typology_Analyzer":
                render_typology_results(data)

            elif tool_name == "Geo_Risk_Analyzer":
                render_geo_risk_results(data)

        # ── Efficiency Metrics ────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="section-header">📊 Efficiency Metrics & Cost Impact</div>',
                    unsafe_allow_html=True)
        
        # Collect risk data from tool outputs for metrics
        for tool_out in result.get("tool_outputs", []):
            data = tool_out.get("output", {})
            if isinstance(data, dict):
                # Extract alerts for metrics
                if "flagged_accounts" in data:
                    for acc in data.get("flagged_accounts", []):
                        st.session_state.metrics_collector.log_alert(
                            account_id=acc.get("account", "UNKNOWN"),
                            risk_score=acc.get("risk_score", 0),
                            risk_level=acc.get("risk_level", "LOW"),
                        )
        
        # Display efficiency dashboard
        dashboard = format_efficiency_dashboard(
            st.session_state.metrics_collector,
            len(st.session_state.df),
            st.session_state.get("dataset_name", "Loaded Dataset"),
        )
        st.code(dashboard, language="text")

        # ── Raw Output Expander ───────────────────────────────────────────
        with st.expander("🔧 Raw Agent Output (Debug)"):
            st.json({
                "tools_used": tools_used,
                "tool_outputs": [
                    {
                        "tool": t.get("tool"),
                        "input": str(t.get("input", "")),
                        "output_preview": str(t.get("output", ""))[:500],
                    }
                    for t in result.get("tool_outputs", [])
                ],
            })

    elif result and result.get("error"):
        st.error(result.get("output", "An error occurred."))


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666; font-size: 0.8em;'>"
    "🛡️ AI-Powered AML Agent | Built with Streamlit, LangChain, NetworkX & Plotly | "
    "Hackathon 2026</p>",
    unsafe_allow_html=True,
)
