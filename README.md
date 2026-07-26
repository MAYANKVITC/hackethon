# Aegis | AML Intelligence Platform

**Aegis** is a fully-functional Streamlit-based AML (Anti-Money Laundering) investigation dashboard designed for compliance analysts. It provides an interactive platform for investigating suspicious transaction patterns using natural language queries, network graph visualization, and AI-assisted investigation workflows.

The platform features a **production-ready UI** built with a dark enterprise theme and glassmorphic design, running on **synthetic/mocked data** so it works standalone without requiring external APIs, databases, or LLM keys. All data is generated in-memory, making it perfect for:
- **Demonstrations** and proof-of-concept evaluations
- **Hackathon competitions** and prototyping
- **Training** and user onboarding
- **Testing** UI/UX workflows before integration with live data

The codebase is designed to be easily swapped with real data sources and actual LLM/agent implementations when wiring into production pipelines.

**Key Detection Capabilities:**
- **Structuring & Smurfing** - transactions deliberately kept below reporting thresholds
- **Layering** - circular fund transfers through intermediary entities and shell companies
- **Shell Company Networks** - entity networks used to obscure fund origins
- **Crypto Off-Ramps** - cryptocurrency conversion and rapid cash-out patterns
- **Cross-Border Risks** - rapid transfers across multiple jurisdictions with high-risk corridors

## What Aegis Provides

Aegis delivers a **complete AML investigation interface** with the following interactive sections:

**Multi-Tab Dashboard with 7 Core Sections:**

1. **Dashboard** - Executive overview and portfolio metrics
   - 6 KPI cards: Total Transactions, Suspicious Accounts, Estimated Laundering Exposure, High-Risk Alerts, AI Confidence, Active Investigations
   - Executive Summary card with risk level, top typologies, and recommended actions
   - Risk Distribution donut chart
   - Recent High-Risk Alerts table with progress columns

2. **AI Investigator** - Natural language query interface
   - Text input for analyst questions (e.g., "Show me accounts with layering patterns above $250K")
   - 4 built-in sample prompt buttons
   - AI Thinking Timeline showing 6-stage reasoning process with confidence scoring
   - Account profile card with risk visualization and actionable buttons (Generate SAR, Freeze Account, Continue Investigation)
   - Reasoning panel explaining identified risk factors

3. **Investigations** - Case management and tracking
   - Comprehensive table of all accounts under review (40 accounts in demo)
   - Columns: Account ID, Risk Score, Typology, Total Sent, Countries, Assigned Analyst, Status
   - Progress bar visualization for risk scores
   - CSV export functionality for offline analysis

4. **Graph Explorer** - Interactive network visualization
   - NetworkX-powered transaction flow graph
   - Visual encoding: node size = risk score, edge width = transaction amount, edge color = laundering probability
   - Live filters: Min Risk Score (0-100), Min Edge Amount ($0-$500K), Typology filter
   - Legend showing node risk levels (High/Medium/Low)
   - Hover tooltips with account details

5. **Analytics** - Portfolio-wide analytics dashboard
   - 6 interactive charts:
     - Typology Distribution (bar chart)
     - Payment Methods (pie chart: Wire, Crypto, Card, Cash, ACH)
     - Country Exposure (horizontal bar chart)
     - Hourly Activity (line area chart)
     - Risk Distribution (donut chart)
     - Monthly Trends (multi-line chart)

6. **Reports** - Compliance document generation
   - **Executive Report**: Portfolio summary with risk exposure and recommended actions
   - **Suspicious Activity Report (SAR)**: Regulator-ready SAR draft with account details, risk assessment, and compliance notes
   - **Investigation Summary**: Case file combining reasoning trail and graph context
   - **CSV Export**: Raw data export for downstream analysis

7. **Settings** - Platform configuration
   - General: Real-time alerts, Sound notifications, Auto-SAR generation
   - Model & Access: Model selection, Confidence threshold slider, Two-factor authentication toggle

**Sidebar Controls:**
- Dataset selector: SAML-D Synthetic v3, IBM AML Sim, Live Ingest
- LLM Model selector: Claude Sonnet, Claude Opus, GPT-4o
- API Key field (masked)
- Risk filters: High Risk, Medium, Cross-Border, Crypto, Shell Co.
- System Status: Graph Engine, LLM Gateway, Sanctions Feed sync status

## Core Features & Capabilities

**Visual Design & UX**
- **Dark Enterprise Theme** - glassmorphic UI with radial gradients and blur effects
- **Responsive Layout** - optimized for 1400px max-width, adapts to different screen sizes
- **Interactive Charts** - Plotly visualizations with smooth animations
- **Status Indicators** - real-time system status monitoring
- **Toast Notifications** - user action feedback and confirmations
- **Font Stack** - Inter (sans-serif) and JetBrains Mono (monospace) for code display

**Dashboard Analytics**
- KPI cards with delta indicators (up/down/neutral trends)
- Executive summary with recommended actions
- Risk distribution visualization (High/Medium/Low breakdown)
- Recent alerts table with progress bar columns
- All metrics update dynamically based on dataset

**AI Investigator Workflow**
- **6-Stage Timeline**: Intent Detection → Entity Extraction → Tool Selection → Graph Analysis → Risk Scoring → Recommendation
- **Confidence Scoring**: Each stage shows confidence percentage (82-97% range)
- **Account Profiling**: Risk score visualization, transaction metrics, typology classification
- **Action Buttons**: Generate SAR, Freeze Account, Continue Investigation
- **Reasoning Panel**: 5 bullet points explaining risk factors and recommendations
- **SAR Generation**: Auto-populated draft with account details, risk assessment, filing notes, and download functionality

**Network Graph Analysis**
- **NetworkX Integration**: Graph construction with 26 nodes and weighted edges
- **Visual Encoding**: 
  - Node size: 10-36px (scaled by risk score)
  - Edge width: 0.8-5px (scaled by transaction amount)
  - Edge color: Red (>66% laundering prob), Orange (35-66%), Green (<35%)
- **Interactive Filtering**:
  - Risk score range (0-100)
  - Minimum edge amount ($0-500K)
  - Typology filter (All, Layering, Smurfing, Shell Company, Trade-Based ML, Crypto Mixing, Structuring)
- **Hover Information**: Account ID, Risk Level, Typology, Transaction amount, Country

**Report Generation**
- **Executive Report**: Portfolio summary with totals, risk levels, and recommendations
- **SAR Draft**: Regulator-ready format with institution name, filing date, subject account, activity summary, risk assessment, and compliance notes
- **Case Summary**: Investigation file with reasoning trail and recommended next steps
- **Download Buttons**: Text file export for all reports

**Data Management**
- **Synthetic Account Generation**: 40 accounts with seed-based randomization
- **Risk Classification**: High (70+), Medium (40-69), Low (<40)
- **Typologies**: 6 categories (Layering, Smurfing, Shell Company, Trade-Based ML, Crypto Mixing, Structuring)
- **Analysts**: 5 pre-defined analysts for assignment
- **Statuses**: Open, Escalated, SAR Filed, Under Review, Closed
- **Countries**: 10 jurisdictions (UAE, Cayman Islands, Singapore, Switzerland, Panama, Cyprus, Malta, Hong Kong, UK, US)

**Performance & Styling**
- **CSS Injection**: Custom glass-card design system
- **Color System**: Risk-based (Red: #f0475b, Orange: #f5a623, Green: #2ed598), Blue accent (#2e6bff), Cyan highlight (#22d3ee)
- **Caching**: `@st.cache_data` for synthetic data generation
- **Responsive Metrics**: st.metric widgets with custom styling

## Architecture & Code Structure

Aegis is built with a clean, modular Streamlit architecture:

```
aegis_app.py (830 lines)
├── CSS & Styling
│   └── Dark enterprise theme, glassmorphic cards, responsive layout
├── Configuration
│   ├── Constants (Countries, Typologies, Analysts, Statuses, Colors)
│   ├── Risk color mapping (High/Medium/Low)
│   └── Timeline stages and sample prompts
├── Data Generation
│   ├── generate_accounts(n=40, seed=42) — synthetic account data
│   └── Helper: fmt_money() — currency formatting
├── UI Components
│   ├── inject_css() — style injection
│   ├── render_sidebar() — dataset/model/filter controls
│   ├── render_dashboard() — KPI cards, exec summary, risk chart, alerts
│   ├── render_ai_investigator() — query interface, timeline, results, SAR
│   ├── render_investigations() — account table with export
│   ├── render_graph_explorer() — NetworkX graph with filters
│   ├── render_analytics() — 6-chart portfolio dashboard
│   ├── render_reports() — report generation buttons
│   └── render_settings() — configuration toggles
├── Graph Analysis
│   ├── build_network() — NetworkX graph with weighted edges
│   └── Visual encoding: node size, edge width, edge color
├── Report Generation
│   ├── run_ai_investigation() — timeline stage simulation
│   └── render_sar_text() — SAR draft template
└── Main Loop
    └── main() — tab orchestration and state management
```

**Key Design Principles:**
- **Modular Functions** - Each UI section is a self-contained render function
- **Session State** - `st.session_state` for investigation results and SAR visibility
- **Synthetic Data** - `@st.cache_data` for performance (seed-based randomization)
- **Swappable Backend** - Functions like `generate_accounts()` and `run_ai_investigation()` are designed to be replaced with real data/LLM calls

**Data Flow:**
1. User interacts with sidebar controls or tabs
2. Streamlit re-runs the entire script (Streamlit's execution model)
3. UI renders based on `st.session_state` and user inputs
4. Results cached until inputs change
5. Action buttons update session state and trigger re-runs

## File structure

```text
Hackathon/
├── app.py                          # Streamlit frontend and dashboard UI
├── requirements.txt               # Python package requirements
├── .env.example                   # Sample environment file for API keys
├── README.md                      # Project documentation
├── src/
│   ├── __init__.py
│   ├── agent.py                   # Query routing, tool selection, and executor wrapper
│   ├── graph_engine.py            # Data loading, graph construction, AML analysis tools
│   └── utils.py                   # Shared constants, formatting helpers, logging, and metadata
├── data/
│   └── SAML-D.csv                 # Sample SAML-D dataset
└── archive (2)/
    ├── HI-Small_Trans.csv
    ├── HI-Small_accounts.csv
    ├── HI-Small_Patterns.txt
    ├── HI-Medium_Trans.csv
    ├── LI-Small_Trans.csv
    └── ...
```

## How the workflow works

1. Data loading
   - The app loads a transaction CSV file and detects whether it is IBM or SAML-D format.
   - The raw data is normalized into a common schema with fields such as sender, receiver, amount, timestamp, payment format, and laundering flags.

2. Graph construction
   - Transactions are converted into a directed graph where each edge represents a transfer from one account to another.
   - This graph is used for cycle detection, fan-in analysis, and relationship-based investigation.

3. Query execution
   - The user submits a natural language prompt.
   - The agent decides which analysis tool(s) are relevant.
   - The selected tools run and return structured findings.

4. Result rendering
   - The Streamlit dashboard displays summaries, risk tables, and plots.
   - Suspicious accounts and suspicious subgraphs are highlighted.

## Technology Stack

**Frontend & UI:**
- **Streamlit** - Complete web app framework with multi-page tabs
- **Custom CSS** - Glassmorphic dark theme injected via `st.markdown(unsafe_allow_html=True)`
- **Plotly** - Interactive charts (bar, pie, area, line, scatter plots)
- **Font Libraries** - Inter (sans-serif), JetBrains Mono (monospace) via Google Fonts

**Graph & Network Analysis:**
- **NetworkX** - Graph construction, node/edge manipulation, layout algorithms (spring layout)

**Data Processing:**
- **pandas** - DataFrame manipulation, data aggregation, sorting
- **NumPy** - Numerical operations (random generation, array operations)

**Python Builtin Libraries:**
- `time` - Simulated delays in AI investigation steps
- `random` - Synthetic data generation and randomization
- `datetime` - Timestamp generation for reports

**Deployment:**
- **Streamlit Server** - Built-in dev server or Streamlit Cloud
- **Dependencies**: pandas, numpy, plotly, networkx (from `requirements.txt`)

## Quick Start

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Windows, macOS, or Linux

### Installation & Running

**1. Install dependencies:**

```bash
pip install streamlit pandas numpy plotly networkx
```

Or use requirements.txt if available:

```bash
pip install -r requirements.txt
```

**2. Run the app:**

```bash
streamlit run aegis_app.py
```

The app will open in your browser at: `http://localhost:8501/`

**3. (Optional) Configure for production data:**

Aegis runs with **synthetic/mocked data by default**. To swap in real data, modify these functions in `aegis_app.py`:

- `generate_accounts(n=40, seed=42)` — Replace with your real account data source
- `run_ai_investigation(query, df)` — Replace with actual LLM/agent calls (e.g., Claude, GPT-4o via LangChain)
- `build_network()` — Replace with real transaction graph from your data pipeline

**Example swap for production data:**

```python
# Replace this:
df = generate_accounts()

# With this:
df = pd.read_csv("your_accounts.csv")
# or
df = fetch_from_database()
```

## Using Aegis

### Tab Navigation

Aegis provides 7 main tabs (visible at the top of the app):

** Dashboard**
- **KPI Cards** (6 metrics): Total Transactions, Suspicious Accounts, Estimated Laundering, High-Risk Alerts, AI Confidence, Active Investigations
- **Executive Summary**: Dataset info, overall risk level, top typology, exposure estimate, account count
- **Recommended Actions**: Actionable guidance based on portfolio risk
- **Risk Distribution Chart**: Pie chart showing High/Medium/Low breakdown
- **Recent Alerts Table**: Top 8 flagged accounts with progress bars

** AI Investigator**
- **Query Input Field**: Enter natural language questions
- **Sample Prompts**: 4 pre-built buttons for common queries
- **AI Thinking Timeline**: 6-stage reasoning process (Intent Detection → Entity Extraction → Tool Selection → Graph Analysis → Risk Scoring → Recommendation)
- **Investigation Results**: Only shown after query submission
  - Account Profile Card (risk score visualization, transaction metrics, typology)
  - Action Buttons: Generate SAR, Freeze Account, Continue Investigation
  - Reasoning Panel: 5 risk factors with confidence score and recommendations
- **SAR Draft Preview**: Generated SAR text with download button (generates on "Generate SAR" click)

**Investigations**
- **Accounts Table**: All 40 accounts with columns:
  - Account ID, Risk Score (progress bar), Typology, Total Sent, Countries, Assigned Analyst, Status
- **Height**: 560px scrollable view
- **Export Button**: Download full dataset as CSV for external analysis
- **Sorting**: Risk score sorting (highest risk first)

** Graph Explorer**
- **Left Panel (Filters)**:
  - Min Risk Score slider (0-100)
  - Min Edge Amount slider ($0-$500K)
  - Typology filter dropdown (All, Layering, Smurfing, Shell Company, Trade-Based ML, Crypto Mixing, Structuring)
  - Legend showing node colors
- **Main Area**: Interactive Plotly graph showing:
  - Nodes: size = risk score, color = risk level
  - Edges: width = transaction amount, color = laundering probability
  - Hover info: Account details on mouse-over
  - Height: 560px canvas

**Analytics**
- **6 Charts** (responsive grid layout):
  1. Typology Distribution (bar chart)
  2. Payment Methods (pie: Wire 34%, Crypto 26%, Card 18%, Cash 12%, ACH 10%)
  3. Country Exposure (horizontal bar, top 7 countries)
  4. Hourly Activity (area chart, 24-hour pattern)
  5. Risk Distribution (donut chart)
  6. Monthly Trends (multi-line: Flagged Volume vs Cases Closed)

**Reports**
- **3 Report Templates** (equal columns):
  1. **Executive Report** - Portfolio summary button → generates report with key findings
  2. **Suspicious Activity Report** - Top flagged account SAR → generates using highest risk account
  3. **Investigation Summary** - Case file button → generates reasoning trail + next steps
- **CSV Export**: Full dataset download button at bottom

**Settings**
- **General (Left Column)**:
  - Real-time alert stream toggle (ON by default)
  - Sound notifications toggle (OFF by default)
  - Auto-generate SAR draft on high risk toggle (OFF by default)
- **Model & Access (Right Column)**:
  - Model dropdown (Claude Sonnet 4.6, Claude Opus 4.8, GPT-4o)
  - Confidence threshold slider (0-100, default 75)
  - Two-factor authentication toggle (ON by default)

### Sidebar Controls

**Dataset Selector**
- SAML-D Synthetic v3 (2.1M txns) — default selection
- IBM AML Sim — HI-Small
- Live Ingest — Core Banking

**LLM Model Selector**
- Claude Sonnet 4.6 (recommended)
- Claude Opus 4.8
- GPT-4o

**API Key Field**
- Password-masked display
- Read-only in demo mode (shows: `sk-ant-••••••••••••8f2a`)

**Risk Filters** (multiselect, "High Risk" selected by default)
- High Risk
- Medium
- Cross-Border
- Crypto
- Shell Co.

**System Status**
- Graph Engine — Online 
- LLM Gateway — Online 
- Sanctions Feed — Sync 4m ago 

## Data & Implementation Details

### Synthetic Data Generation

All data in Aegis is **generated in-memory** using `generate_accounts(n=40, seed=42)`:

**Account Data (40 accounts):**
- **Account ID**: ACC-88200 through ACC-88239
- **Risk Score**: Random 20-98 (classified as High/Medium/Low)
- **Typologies**: Layering, Smurfing, Shell Company, Trade-Based ML, Crypto Mixing, Structuring
- **Transaction Amounts**: Sent ($15K-$2.1M), Received ($10K-$1.9M)
- **Countries**: UAE, Cayman Is., Singapore, Switzerland, Panama, Cyprus, Malta, Hong Kong, UK, US
- **Countries Count**: 1-9 jurisdictions per account
- **Assigned Analysts**: 5 pre-defined analysts (J. Alvarez, R. Chen, M. Osei, S. Novak, A. Khan)
- **Status**: Open, Escalated, SAR Filed, Under Review, Closed

**Graph Data (NetworkX):**
- **Nodes**: Top 26 accounts (by risk score)
- **Edges**: 1-3 random edges per node
- **Edge Attributes**: 
  - Amount: $5K-$480K per transaction
  - Probability: 0.1-0.98 (laundering probability)

**AI Investigation Timeline** (6 stages):
1. Intent Detection — Classifying query as targeted risk investigation
2. Entity Extraction — Identifying accounts, amounts, date ranges
3. Tool Selection — Routing to graph traversal + risk scoring models
4. Graph Analysis — Traversing transaction network for layering paths
5. Risk Scoring — Computing composite risk score from behavioral features
6. Recommendation — Drafting next-action guidance for analyst

Each stage shows random confidence: 82-97%

### Report Templates

**SAR (Suspicious Activity Report) Template:**
```
SAR NARRATIVE — ACCOUNT [ID]
Filing Institution: [Institution Name]
Prepared by: AI Investigator (reviewed by Senior Analyst)
Date: [YYYY-MM-DD]

SUBJECT: [Account] exhibits a pattern of [typology]
consistent with known money laundering typologies.

SUMMARY OF ACTIVITY:
The subject account sent [amount] and received [amount]
across [countries] jurisdictions.

RISK ASSESSMENT: [LEVEL] (Score: [score]/100, Model Confidence: [confidence]%)

RECOMMENDED ACTION:
File SAR with the relevant regulator within the compliance deadline.
```

**Executive Report Template:**
```
EXECUTIVE SUMMARY REPORT
Generated: [timestamp]

Overall Risk Level: HIGH
Total Accounts Reviewed: [count]
High-Risk Accounts: [count]
Estimated Laundering Exposure: $18.42M
Top Typology: [typology]

KEY FINDINGS:
- [count] accounts flagged as high risk
- Recommend SAR filing review for top-risk accounts
```

### Color Coding System

```python
RISK_COLORS = {
    "High": "#f0475b",      # Red
    "Medium": "#f5a623",    # Orange
    "Low": "#2ed598"        # Green
}

ACCENT_COLORS = {
    "Blue": "#2e6bff",      # Primary blue
    "Cyan": "#22d3ee"       # Highlight cyan
}

GLASS_DARK_THEME = {
    "Background-0": "#05070c",
    "Background-1": "#0a0e18",
    "Background-2": "#0f1524",
    "Background-3": "#141c30",
    "Text-0": "#eef2fa",
    "Text-1": "#aab3c5",
    "Text-2": "#6b7488",
    "Glass": "rgba(255,255,255,0.035)",
}
```

## Synthetic vs. Production Data

### Current Implementation (Synthetic/Demo Mode)

Aegis ships with **fully synthetic data generation** for demonstration purposes:

**Advantages:**
- Runs immediately without external dependencies
- Reproducible results (seed-based)
- Perfect for UI/UX testing and demos
- No API keys or database credentials required
- Ideal for hackathons and training

**Limitations (intentional for demo):**
- Data is randomly generated, not real transactions
- No actual money laundering patterns
- AI investigation workflow is simulated (timeline-only, not real LLM reasoning)
- Graph edges are random, not based on actual transaction flows

### Production Data Integration

To integrate real data, replace these three functions in `aegis_app.py`:

**1. Replace `generate_accounts()`:**

```python
# OLD (synthetic):
@st.cache_data
def generate_accounts(n=40, seed=42):
    # Random generation...
    return df

# NEW (real data):
@st.cache_data
def generate_accounts(n=40, seed=42):
    # Option A: Load from CSV
    df = pd.read_csv("transactions.csv")
    
    # Option B: Query from database
    df = pd.read_sql("SELECT * FROM accounts", conn)
    
    # Option C: API call
    df = fetch_from_api("/accounts?limit=40")
    
    return df
```

**2. Replace `run_ai_investigation()`:**

```python
# OLD (simulated):
def run_ai_investigation(query, df):
    for title, desc in TIMELINE_STAGES:
        # Fake delays...
        time.sleep(0.5)

# NEW (real LLM):
def run_ai_investigation(query, df):
    from anthropic import Anthropic
    client = Anthropic()
    
    # Call Claude with tools
    response = client.messages.create(
        model="claude-3.5-sonnet",
        max_tokens=1024,
        tools=[...],  # Define AML tools
        messages=[{"role": "user", "content": query}],
    )
    
    # Process response...
```

**3. Replace `build_network()`:**

```python
# OLD (random edges):
for i in range(n):
    j = rng.randint(0, len(subset) - 1)
    amount = rng.randint(5_000, 480_000)

# NEW (real transactions):
transactions = df.query("sender in @subset['account_id']")
for _, txn in transactions.iterrows():
    G.add_edge(txn['sender'], txn['receiver'], 
               amount=txn['amount'], 
               prob=compute_risk_score(txn))
```

### Example: Loading from CSV

```python
@st.cache_data
def generate_accounts():
    df = pd.read_csv("accounts.csv")
    
    # Ensure required columns
    required = ["account_id", "total_sent", "total_received", 
                "risk_score", "typology", "country"]
    assert all(col in df.columns for col in required)
    
    # Risk classification
    df["risk_level"] = pd.cut(df["risk_score"], 
        bins=[0, 40, 70, 100], 
        labels=["Low", "Medium", "High"])
    
    return df.sort_values("risk_score", ascending=False)
```

## Design Philosophy & Notable Features

**Streamlit Best Practices Demonstrated:**
- Modular function-based rendering (one function per tab)
- CSS injection for custom styling without using experimental features
- Session state management for multi-step workflows (investigation → SAR generation)
- Caching with `@st.cache_data` for performance
- Responsive layout using `st.columns()` for grid systems
- Safe HTML rendering with `unsafe_allow_html=True` for custom designs

**Data Visualization Patterns:**
- Plotly with disabled mode bar and custom height/margin settings
- Progress columns for numeric indicators
- KPI cards with up/down/neutral delta indicators
- Donut and pie charts for risk distribution
- Bar charts for categorical analysis
- Area charts for temporal trends
- Network graph with node/edge visual encoding

**UX/UI Innovations:**
- Glassmorphic design using low-opacity backgrounds and blur effects
- Dark enterprise theme with carefully chosen color palette
- Status indicators for real-time system monitoring
- Toast notifications for action feedback
- Gradient accents (conic-gradient for brand mark, linear-gradient for buttons)
- Responsive typography (monospace for metrics and IDs, sans-serif for body)

## Troubleshooting

### Streamlit doesn't start

If you get a `ModuleNotFoundError`, install dependencies:

```bash
pip install streamlit pandas numpy plotly networkx
```

### Port 8501 is already in use

Run on a different port:

```bash
streamlit run aegis_app.py --server.port 8502
```

### App runs but no data appears

- Check that synthetic data generation isn't raising errors
- Verify session state initialization in `main()`
- Clear Streamlit cache: `streamlit cache clear`

### Graphs not rendering

- Ensure Plotly is installed: `pip install plotly`
- Check browser developer console for JavaScript errors
- Try disabling dark mode in browser if visualization looks broken

### Performance issues with 40 accounts

- The demo is designed for 40 accounts; adjust `n=40` in `generate_accounts(n=40)` if needed
- NetworkX spring layout can be slow with 100+ nodes; consider different layout algorithms
- Cache larger dataframes with `@st.cache_data` when loading real data

## Files & Structure

```
Hackathon/
├── aegis_app.py                 # Main Streamlit application (830 lines)
│   ├── CSS injection & styling
│   ├── Constants (countries, typologies, colors)
│   ├── Synthetic data generator
│   ├── Sidebar component
│   ├── 7 Tab components (Dashboard, Investigator, etc.)
│   ├── Network graph builder (NetworkX)
│   ├── Report generators (SAR, Executive, Summary)
│   └── Main tab orchestrator
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── app.py                       # Original Streamlit app (if different)
└── data/                        # Data directory (for CSV integration)
    └── SAML-D.csv              # Sample SAML-D dataset (optional)
```

## Next Steps & Integration Guide

### For Hackathon Judges & Reviewers

**To evaluate Aegis:**

1. **Install & Run** (2 minutes):
   ```bash
   pip install streamlit pandas numpy plotly networkx
   streamlit run aegis_app.py
   ```

2. **Explore Each Tab** (5 minutes):
   - Dashboard: KPIs and executive summary
   - AI Investigator: Enter a query or click a sample prompt
   - Investigations: Browse account table and export CSV
   - Graph Explorer: Adjust filters and explore network
   - Analytics: View portfolio-wide trends
   - Reports: Generate and download documents
   - Settings: Adjust configuration

3. **Note the Design**:
   - Dark glassmorphic theme with enterprise polish
   - Smooth animations and transitions
   - Responsive layout across screen sizes
   - Color-coded risk indicators

### For Production Integration

**Phase 1: Replace Data Source (1-2 days)**
- Modify `generate_accounts()` to load real transaction data
- Validate schema matches expected columns
- Add data quality checks and error handling

**Phase 2: Integrate LLM Reasoning (2-3 days)**
- Replace `run_ai_investigation()` with actual LangChain agent
- Define AML tools using Claude/GPT-4o tool_use schema
- Implement proper error handling and timeout logic

**Phase 3: Connect Real Graphs (1-2 days)**
- Replace `build_network()` with real transaction graph
- Optimize NetworkX layouts for larger datasets (500+ nodes)
- Add caching strategies for performance

**Phase 4: Add Database Backend (3-5 days)**
- Connect to PostgreSQL/MongoDB for persistence
- Implement audit logging for compliance
- Add user authentication and role-based access

**Phase 5: Deploy & Monitor (1-2 days)**
- Package as Docker container or Streamlit Cloud
- Set up monitoring and alerting
- Create operations runbook

### Estimated Timeline to Production: 2-3 weeks

## Summary

**Aegis** is a **production-ready AML Intelligence Platform UI** built with Streamlit that demonstrates:

**Comprehensive AML Investigation Interface** with 7 specialized tabs
**Enterprise-Grade UI/UX** with dark glassmorphic design
**Interactive Network Visualization** using NetworkX and Plotly  
**Multi-Stage AI Reasoning** workflow with confidence scores
**Compliance Document Generation** (SAR, Executive Reports, Case Files)
**Portfolio Analytics Dashboard** with 6 interactive charts
**Modular Architecture** designed for easy data/LLM integration
**Zero External Dependencies** (runs with synthetic data by default)

**Best For:**
- **Hackathons** - Complete, working demo in one file
- **Training & Demos** - Interactive AML investigation showcase
- **Proof-of-Concept** - Quickly test UI before full development
- **MVP Development** - Foundation for production AML platform

**Technology Stack:**
- Frontend: Streamlit + Plotly + Custom CSS
- Graph Analytics: NetworkX
- Data Processing: pandas, NumPy

**Getting Started:**
```bash
pip install streamlit pandas numpy plotly networkx
streamlit run aegis_app.py
```

The app opens at `http://localhost:8501/` with full functionality, synthetic data, and ready-to-customize components for your AML use case.
