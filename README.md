# 🛡️ AEGIS — AI-Powered AML Agent Platform

**AEGIS** (AI-Enhanced Guardian for Intelligent Surveillance) is an agentic Anti-Money Laundering (AML) platform built for automated exploratory data analysis, transaction pattern detection, ML anomaly scoring, and explainable risk classification.

---

## 🌟 Key Features & Architecture

AEGIS implements a **query-adaptive agentic pipeline** (not a fixed sequential pipeline):

1. **Query Intent & Filter Extraction**: Parses natural language queries to extract intent type, specific account/entity IDs, date ranges (e.g. "last 30 days"), amount filters (e.g. "under $10,000"), and target AML pattern types.
2. **Dynamic Tool Planning**: Dynamically selects and invokes *only* the tools necessary to answer the specific query.
3. **Multi-Tool Capabilities (9 Specialized Tools)**:
   - 📊 **Automated_EDA**: Baseline transaction statistics, total volume, top senders/receivers, payment format mix.
   - 🕵️ **Smurfing_Detector**: Fan-in structuring pattern detection for transactions under reporting thresholds.
   - 🔄 **Cycle_Detector**: Directed cycle detection (lengths 3–5) for circular money loops (layering networks).
   - 🔍 **Single_Entity_Lookup**: On-demand account inspection with in/out degree, volume, and 2-hop ego network cycle check.
   - 🗺️ **Typology_Analyzer**: Laundering typology breakdown (17 SAML-D categories / IBM ground truth patterns).
   - 🌍 **Geo_Risk_Analyzer**: Cross-border transaction corridors and country-level laundering exposure.
   - ⚙️ **Feature_Engineer**: On-demand AML features (frequency, velocity, rolling 7d sums, amount deviation, rapid cash-out flags, round amount ratio, night transaction ratio, Herfindahl counterparty index, dormancy reactivation).
   - 🔬 **Anomaly_Detector**: Hybrid ML (Isolation Forest) + Statistical (Z-score & IQR) anomaly detection with ensemble scoring.
   - 📊 **Risk_Classifier**: Composite risk scoring combining ML anomaly signals, graph topological adjustments, and business rules into HIGH/MEDIUM/LOW risk classifications with recommended escalation actions.
4. **Human-Readable Explanations**: Context-aware natural language narratives explaining why transactions/accounts were flagged, tied directly to the user's query.
5. **Execution Summaries**: Transparent reporting showing what intent was detected, which filters were applied, which tools were invoked, and why.

---

## 📁 Repository Structure

```
hackethon/
├── app.py                      # Main Streamlit Web Application
├── aegis_app_mockup.py         # Alternative Glassmorphic UI Prototype (Mockup)
├── requirements.txt            # Python dependencies (NetworkX ≥3.2, Scikit-Learn, LangChain, Streamlit)
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
│
├── src/                        # Core Python Package
│   ├── __init__.py             # Package initializer
│   ├── agent.py                # LangChain Agent Orchestrator & Intent Parser
│   ├── graph_engine.py         # NetworkX Graph Analysis Engine & Detection Tools
│   ├── feature_engineering.py  # Standalone AML Feature Engineering Tool
│   ├── anomaly_detection.py    # Hybrid ML + Statistical Anomaly Detector
│   ├── risk_classifier.py      # Composite Risk Classification Tool
│   ├── explanation_engine.py   # Natural Language Explanation Generator
│   ├── metrics.py              # Performance Metrics & Cost Savings Tracking
│   └── utils.py                # Shared utilities, constants, formatters & dataset registry
│
├── data/                       # Datasets
│   ├── sample_transactions.csv # Built-in sample dataset with injected AML patterns
│   └── generate_sample.py      # Reproducible dataset generator script
│
└── tests/                      # Automated Unit Test Suite
    ├── __init__.py
    └── test_tools.py           # 12 unit tests covering all tools, agent, and metrics
```

---

## 🚀 Quick Start for Reviewers / Judges

### 1. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run the Main Application
Launch the Streamlit app:
```bash
streamlit run app.py
```
The application will automatically load the built-in sample dataset (`data/sample_transactions.csv`) with injected structuring, circular layering, and fan-out laundering patterns.

### 3. (Optional) Configure OpenAI API Key
For full LLM agent orchestration, enter your OpenAI API Key in the application sidebar or set it in a `.env` file:
```ini
OPENAI_API_KEY=your_openai_api_key_here
```
*Note: If no API key is provided, the system automatically runs in local rule-based fallback mode using regex and keyword intent parsing.*

---

## 🧪 Run Automated Tests

To run the complete automated test suite (12 tests covering all modules):
```bash
python -m unittest tests/test_tools.py
```

---

## 💡 Example Queries to Try

1. **Structuring Detection**:
   `"Find structuring patterns in the last 30 days"`
   *(Triggers intent parsing, date filter, Feature Engineer, and Smurfing Detector)*

2. **Threshold Rule Query**:
   `"Which customers made 10+ transactions under $10,000?"`
   *(Extracts amount filter `$10,000` and runs targeted fan-in detection)*

3. **Single Entity Inspection**:
   `"Is account 8001 suspicious?"`
   *(Extracts account ID `8001`, performs 2-hop graph lookup, and runs anomaly check)*

4. **Circular Layering**:
   `"Find circular money loops indicating layering networks"`
   *(Invokes Cycle Detector for directed graph cycles)*

5. **ML Anomaly Detection**:
   `"Run ML anomaly detection to flag high risk accounts"`
   *(Runs Feature Engineer, Isolation Forest + Z-score ensemble, and Risk Classifier)*

---

## 📊 Summary of Fixes Applied

- ✅ **Fixed `ModuleNotFoundError`**: Created standard `src/` package structure.
- ✅ **Added Built-In Dataset**: Created reproducible dataset generator with realistic AML patterns.
- ✅ **Implemented ML Anomaly Detection**: Hybrid Isolation Forest + Statistical Z-Score/IQR ensemble.
- ✅ **Implemented Feature Engineering Tool**: Computes 12 model-ready AML features on demand.
- ✅ **Implemented Risk Classifier & Explanation Engine**: Standardized risk scoring and query-aware natural language narratives.
- ✅ **Implemented Filter & Intent Parsing**: Parses dates ("last 30 days"), amounts ("under $10,000"), entity IDs, and pattern types.
- ✅ **Fixed Bugs**: Resolved multi-hop cycle detection, country count math, node ID substring matching, rolling window deprecation warnings, and tautological metrics formulas.
- ✅ **Comprehensive Test Suite**: 12 automated unit tests passing 100%.
