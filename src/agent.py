"""
agent.py — Dynamic LangChain Agent Orchestrator for AML Analysis.

This module wraps the graph_engine analysis functions as LangChain Tools
and creates a dynamic agent that:
  1. Parses natural language queries from compliance officers
  2. Extracts intent, entities, filters (date range, amount, pattern type)
  3. Selectively invokes ONLY the tools needed to answer the query
  4. Returns structured, explainable results with execution summaries
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# Base Tool Wrapper (Ensures 'Tool' is ALWAYS defined in scope)
# ---------------------------------------------------------------------------
class SimpleTool:
    """Fallback tool wrapper when LangChain is not installed or using local rule engine."""
    def __init__(self, name: str, func: Any, description: str):
        self.name = name
        self.func = func
        self.description = description

    def invoke(self, input_value: Any = "") -> str:
        if isinstance(input_value, dict):
            return self.func(json.dumps(input_value))
        return self.func(str(input_value) if input_value is not None else "")


# ---------------------------------------------------------------------------
# Robust LangChain & Tool Imports
# ---------------------------------------------------------------------------
LLM_AVAILABLE = False

try:
    from langchain.agents import AgentExecutor, create_openai_tools_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_openai import ChatOpenAI
    LLM_AVAILABLE = True
except Exception:  # pragma: no cover
    AgentExecutor = None
    create_openai_tools_agent = None
    ChatPromptTemplate = None
    MessagesPlaceholder = None
    ChatOpenAI = None
    LLM_AVAILABLE = False

# Safe Tool Import Strategy: Try modern langchain_core StructuredTool first
Tool = None
try:
    from langchain_core.tools import StructuredTool
    # Helper constructor function to match standard Tool interface
    def create_langchain_tool(name: str, func: Any, description: str):
        return StructuredTool.from_function(func=func, name=name, description=description)
    Tool = create_langchain_tool
except Exception:
    try:
        from langchain.tools import Tool as _LangchainTool
        Tool = _LangchainTool
    except Exception:
        # Fallback to SimpleTool so Tool is NEVER None
        Tool = SimpleTool


from src.graph_engine import (
    detect_cycles_tool,
    detect_smurfing_tool,
    detect_typology_tool,
    eda_tool,
    geo_risk_tool,
    single_entity_lookup,
)
from src.feature_engineering import feature_engineering_tool
from src.anomaly_detection import anomaly_detection_tool
from src.risk_classifier import risk_classification_tool
from src.explanation_engine import (
    generate_explanation,
    generate_batch_explanation,
    generate_execution_summary,
)
from src.utils import DATASET_FORMAT_SAML, get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# INTENT PARSING & FILTER EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

def parse_query_intent(query: str) -> Dict[str, Any]:
    """Parse a natural language query to extract intent, filters, and entities.

    Extracts:
        - intent_type: The primary action/analysis type
        - entity_id: Specific account/customer ID if mentioned
        - date_range: Date filter if mentioned (e.g., 'last 30 days')
        - amount_filter: Amount threshold if mentioned
        - pattern_type: Specific AML pattern mentioned
        - keywords: Relevant keywords found

    Args:
        query: Natural language query string.

    Returns:
        Dictionary with parsed intent components.
    """
    lowered = query.lower()
    intent = {
        "raw_query": query,
        "intent_type": "general",
        "entity_id": None,
        "date_range": None,
        "amount_filter": None,
        "pattern_type": None,
        "keywords": [],
        "tools_to_invoke": [],
    }

    # --- Extract entity ID ---
    # Try multiple patterns for account/customer/entity IDs
    entity_patterns = [
        r"(?:account|customer|entity|id)\s*[:#\-]?\s*([A-Za-z0-9_\-]+)",
        r"(?:is|check|lookup|investigate)\s+(?:account|customer)?\s*([A-Za-z0-9_\-]{3,})\b",
        r"\b([0-9]{4,}[A-Za-z]+[0-9]*)\b",  # Mixed alphanumeric IDs like 8000EBD30
        r"\b([A-Za-z]+[0-9]{4,})\b",          # IDs like ACC1234
    ]
    for pattern in entity_patterns:
        match = re.search(pattern, query, re.I)
        if match:
            candidate = match.group(1)
            # Filter out common words that aren't IDs
            if candidate.lower() not in {"the", "this", "that", "from", "with", "about",
                                         "last", "past", "days", "transactions", "suspicious",
                                         "high", "risk", "low", "medium", "under", "over"}:
                intent["entity_id"] = candidate
                intent["intent_type"] = "entity_lookup"
                break

    # --- Extract date range ---
    date_patterns = [
        (r"last\s+(\d+)\s+days?", "days"),
        (r"past\s+(\d+)\s+days?", "days"),
        (r"last\s+(\d+)\s+weeks?", "weeks"),
        (r"last\s+(\d+)\s+months?", "months"),
        (r"since\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})", "since"),
        (r"between\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+and\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})", "between"),
    ]
    for pattern, unit in date_patterns:
        match = re.search(pattern, lowered)
        if match:
            now = datetime.now()
            if unit == "days":
                start = now - timedelta(days=int(match.group(1)))
                intent["date_range"] = {"start": start.isoformat(), "end": now.isoformat(), "description": f"last {match.group(1)} days"}
            elif unit == "weeks":
                start = now - timedelta(weeks=int(match.group(1)))
                intent["date_range"] = {"start": start.isoformat(), "end": now.isoformat(), "description": f"last {match.group(1)} weeks"}
            elif unit == "months":
                start = now - timedelta(days=int(match.group(1)) * 30)
                intent["date_range"] = {"start": start.isoformat(), "end": now.isoformat(), "description": f"last {match.group(1)} months"}
            elif unit == "since":
                intent["date_range"] = {"start": match.group(1), "end": now.isoformat(), "description": f"since {match.group(1)}"}
            elif unit == "between":
                intent["date_range"] = {"start": match.group(1), "end": match.group(2), "description": f"between {match.group(1)} and {match.group(2)}"}
            break

    # --- Extract amount filter ---
    amount_patterns = [
        (r"under\s+\$?([\d,]+)", "under"),
        (r"below\s+\$?([\d,]+)", "under"),
        (r"less\s+than\s+\$?([\d,]+)", "under"),
        (r"over\s+\$?([\d,]+)", "over"),
        (r"above\s+\$?([\d,]+)", "over"),
        (r"more\s+than\s+\$?([\d,]+)", "over"),
        (r"(\d+)\+\s*transactions?", "min_count"),
    ]
    for pattern, filter_type in amount_patterns:
        match = re.search(pattern, lowered)
        if match:
            value = float(match.group(1).replace(",", ""))
            intent["amount_filter"] = {"type": filter_type, "value": value}
            break

    # --- Determine pattern type and intent ---
    if any(k in lowered for k in ["smurf", "structur", "fan-in", "fan in", "small deposit"]):
        intent["pattern_type"] = "structuring"
        if intent["intent_type"] == "general":
            intent["intent_type"] = "pattern_detection"
        intent["keywords"].extend(["structuring", "smurfing"])

    if any(k in lowered for k in ["cycle", "loop", "layer", "circular", "round-tripping", "round tripping"]):
        intent["pattern_type"] = "layering"
        if intent["intent_type"] == "general":
            intent["intent_type"] = "pattern_detection"
        intent["keywords"].extend(["layering", "cycles"])

    if any(k in lowered for k in ["typology", "breakdown", "category"]):
        if intent["intent_type"] == "general":
            intent["intent_type"] = "typology_analysis"
        intent["keywords"].append("typology")

    if any(k in lowered for k in ["geo", "geographic", "country", "cross-border", "cross border",
                                    "corridor", "jurisdiction", "international"]):
        if intent["intent_type"] == "general":
            intent["intent_type"] = "geo_analysis"
        intent["keywords"].append("geographic")

    if any(k in lowered for k in ["anomal", "suspicious", "unusual", "outlier", "detect", "flag"]):
        if intent["intent_type"] == "general":
            intent["intent_type"] = "anomaly_detection"
        intent["keywords"].append("anomaly")

    if any(k in lowered for k in ["feature", "engineer", "variable", "metric"]):
        if intent["intent_type"] == "general":
            intent["intent_type"] = "feature_engineering"
        intent["keywords"].append("features")

    if any(k in lowered for k in ["risk", "classify", "score", "rating"]):
        intent["keywords"].append("risk")

    if any(k in lowered for k in ["overview", "baseline", "statistics", "summary", "eda", "explore", "analyse", "analyze"]):
        if intent["intent_type"] == "general":
            intent["intent_type"] = "eda"
        intent["keywords"].append("eda")

    # --- Build tool invocation plan ---
    intent["tools_to_invoke"] = _plan_tools(intent)

    return intent


def _plan_tools(intent: Dict[str, Any]) -> List[str]:
    """Determine which tools to invoke based on parsed intent.

    Args:
        intent: Parsed intent dictionary from parse_query_intent.

    Returns:
        Ordered list of tool names to invoke.
    """
    tools = []
    intent_type = intent["intent_type"]

    if intent_type == "entity_lookup":
        tools.append("Single_Entity_Lookup")
        # Also run anomaly detection for the entity if asked about suspicion
        if "anomaly" in intent["keywords"] or "suspicious" in intent.get("raw_query", "").lower():
            tools.append("Anomaly_Detector")

    elif intent_type == "pattern_detection":
        if intent["pattern_type"] == "structuring":
            tools.append("Feature_Engineer")
            tools.append("Smurfing_Detector")
        elif intent["pattern_type"] == "layering":
            tools.append("Cycle_Detector")
        else:
            tools.append("Feature_Engineer")
            tools.append("Anomaly_Detector")

    elif intent_type == "anomaly_detection":
        tools.append("Feature_Engineer")
        tools.append("Anomaly_Detector")
        tools.append("Risk_Classifier")

    elif intent_type == "feature_engineering":
        tools.append("Feature_Engineer")

    elif intent_type == "typology_analysis":
        tools.append("Typology_Analyzer")

    elif intent_type == "geo_analysis":
        tools.append("Geo_Risk_Analyzer")

    elif intent_type == "eda":
        tools.append("Automated_EDA")

    else:
        # General / unclear — run EDA as default
        tools.append("Automated_EDA")

    return tools


def apply_date_filter(df: pd.DataFrame, date_range: Optional[Dict[str, str]]) -> pd.DataFrame:
    """Apply date range filter to a DataFrame.

    Args:
        df: Transaction DataFrame with 'timestamp' column.
        date_range: Dict with 'start' and 'end' ISO date strings, or None.

    Returns:
        Filtered DataFrame, or original if no filter or timestamp column missing.
    """
    if not date_range or "timestamp" not in df.columns:
        return df

    try:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        start = pd.to_datetime(date_range["start"])
        end = pd.to_datetime(date_range["end"])
        mask = (ts >= start) & (ts <= end)
        filtered = df[mask]
        if len(filtered) == 0:
            logger.warning("Date filter returned 0 rows; using full dataset.")
            return df
        logger.info("Date filter applied: %d → %d rows", len(df), len(filtered))
        return filtered
    except Exception as e:
        logger.warning("Failed to apply date filter: %s", e)
        return df


class SimpleAction:
    def __init__(self, tool_name: str, tool_input: Any):
        self.tool = tool_name
        self.tool_input = tool_input


class SimpleExecutor:
    """Rule-based executor used when LangChain's agent runtime is unavailable.

    Parses user queries using keyword matching and regex to determine which
    tools to invoke. Supports date filtering, entity extraction, and
    dynamic tool selection.
    """

    def __init__(self, tools: List[Any], df: pd.DataFrame = None, G: nx.DiGraph = None):
        self.tools = tools
        self.df = df
        self.G = G

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = str(inputs.get("input", ""))

        # Step 1: Parse intent
        intent = parse_query_intent(query)
        logger.info("Parsed intent: type=%s, entity=%s, date=%s, pattern=%s",
                     intent["intent_type"], intent["entity_id"],
                     intent.get("date_range", {}).get("description") if intent.get("date_range") else None,
                     intent["pattern_type"])

        # Step 2: Apply date filter to data if needed
        if intent["date_range"] and self.df is not None:
            filtered_df = apply_date_filter(self.df, intent["date_range"])
            date_note = f" (filtered to {intent['date_range']['description']})"
        else:
            filtered_df = self.df
            date_note = ""

        # Step 3: Select tools based on intent
        planned_tools = intent["tools_to_invoke"]

        # Step 4: Execute tools
        intermediate_steps = []
        tool_outputs = []
        execution_log = []

        for tool_name in planned_tools:
            tool_obj = next((t for t in self.tools if t.name == tool_name), None)
            if not tool_obj:
                logger.warning("Tool '%s' not found, skipping.", tool_name)
                execution_log.append({"tool": tool_name, "status": "SKIPPED", "reason": "Tool not registered"})
                continue

            # Prepare input based on tool type
            tool_input = self._prepare_tool_input(tool_name, intent)

            try:
                if hasattr(tool_obj, "invoke"):
                    output = tool_obj.invoke(tool_input if isinstance(tool_input, str) else json.dumps(tool_input))
                elif hasattr(tool_obj, "func"):
                    output = tool_obj.func(tool_input)
                else:
                    output = str(tool_obj)

                intermediate_steps.append((SimpleAction(tool_name, tool_input), output))
                tool_outputs.append({"tool": tool_name, "input": tool_input, "output": output})
                execution_log.append({"tool": tool_name, "status": "SUCCESS"})
                logger.info("Tool %s completed successfully.", tool_name)

            except Exception as e:
                error_msg = f"Error running {tool_name}: {str(e)}"
                logger.error(error_msg)
                execution_log.append({"tool": tool_name, "status": "ERROR", "error": str(e)})
                tool_outputs.append({"tool": tool_name, "input": tool_input, "output": json.dumps({"status": "ERROR", "error": str(e)})})

        # Step 5: Generate execution summary
        exec_summary = generate_execution_summary(
            query=query,
            intent=intent,
            tools_invoked=[t["tool"] for t in execution_log],
            results_summary={"tool_count": len(planned_tools), "success_count": sum(1 for t in execution_log if t["status"] == "SUCCESS")}
        )

        # Build output text
        output_lines = [
            f"═══ AML Agent Execution Summary ═══",
            f"Query: {query}{date_note}",
            f"Intent: {intent['intent_type']}",
            f"Pattern: {intent['pattern_type'] or 'N/A'}",
            f"Entity: {intent['entity_id'] or 'N/A'}",
            f"Date Filter: {intent['date_range']['description'] if intent.get('date_range') else 'None'}",
            f"Tools invoked: {', '.join(planned_tools)}",
            f"",
        ]
        for log_entry in execution_log:
            status_icon = "✅" if log_entry["status"] == "SUCCESS" else "❌" if log_entry["status"] == "ERROR" else "⏭️"
            output_lines.append(f"  {status_icon} {log_entry['tool']}: {log_entry['status']}")

        return {
            "output": "\n".join(output_lines),
            "intermediate_steps": intermediate_steps,
            "tools_used": [step[0].tool for step in intermediate_steps],
            "tool_outputs": tool_outputs,
            "execution_summary": exec_summary,
            "parsed_intent": intent,
        }

    def _prepare_tool_input(self, tool_name: str, intent: Dict[str, Any]) -> Any:
        """Prepare the appropriate input for each tool based on parsed intent.

        Args:
            tool_name: Name of the tool being invoked.
            intent: Parsed intent dictionary.

        Returns:
            Tool-specific input value.
        """
        if tool_name == "Single_Entity_Lookup":
            return intent.get("entity_id", "")

        elif tool_name == "Smurfing_Detector":
            params = {"min_fan_in": 5, "amount_cap": 10000.0}
            if intent.get("amount_filter") and intent["amount_filter"]["type"] == "under":
                params["amount_cap"] = intent["amount_filter"]["value"]
            return params

        elif tool_name == "Cycle_Detector":
            return {"min_length": 3, "max_length": 5}

        elif tool_name == "Anomaly_Detector":
            return {"method": "hybrid"}

        elif tool_name == "Feature_Engineer":
            return ""

        elif tool_name == "Risk_Classifier":
            return ""

        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an expert Anti-Money Laundering (AML) compliance analyst agent.
Your job is to help compliance officers investigate suspicious transaction patterns
using a suite of specialized analysis tools.

IMPORTANT RULES:
1. You must DYNAMICALLY select the appropriate tool(s) based on the user's query.
   Do NOT run all tools — only invoke what is specifically needed.
2. For general statistics or overview questions → use Automated_EDA
3. For structuring/smurfing/fan-in pattern detection → use Smurfing_Detector
4. For circular money loops or layering detection → use Cycle_Detector
5. For investigating a specific account → use Single_Entity_Lookup
6. For laundering typology breakdowns → use Typology_Analyzer
7. For cross-border flows and geographic risk → use Geo_Risk_Analyzer
8. For creating AML features (frequency, velocity, deviation) → use Feature_Engineer
9. For ML-based anomaly detection → use Anomaly_Detector
10. For final risk classification with scoring → use Risk_Classifier
11. Always provide clear, actionable explanations with your findings.
12. When reporting risk scores, explain what factors contributed to the score.
13. If the user asks about a specific account, extract the account ID from their query.
14. If Geo_Risk_Analyzer returns has_geo_data=false, explain that geo analysis requires SAML-D.

After running tools, synthesize the results into a clear compliance report format.
Include risk levels, recommended actions, and key findings.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def _create_tools(
    df: pd.DataFrame,
    G: nx.DiGraph,
    dataset_format: str = "ibm",
    patterns_data: Optional[Dict[str, Any]] = None,
    use_simple_tools: bool = False,
) -> list:
    """Create Tool instances wrapping all analysis functions.

    Creates 9 tools: 6 original graph-based tools + 3 new tools
    (Feature Engineering, Anomaly Detection, Risk Classification).
    """

    def _run_eda(_input: str = "") -> str:
        return eda_tool(df)

    def _run_smurfing(input_str: str = "") -> str:
        min_fan_in = 5
        amount_cap = 10000.0
        try:
            if input_str and isinstance(input_str, str):
                params = json.loads(input_str)
                min_fan_in = params.get("min_fan_in", 5)
                amount_cap = params.get("amount_cap", 10000.0)
            elif isinstance(input_str, dict):
                min_fan_in = input_str.get("min_fan_in", 5)
                amount_cap = input_str.get("amount_cap", 10000.0)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Smurfing param parse failed (%s); using defaults.", e)
        return detect_smurfing_tool(G, min_fan_in=min_fan_in, amount_cap=amount_cap)

    def _run_cycles(input_str: str = "") -> str:
        min_length = 3
        max_length = 5
        try:
            if input_str and isinstance(input_str, str):
                params = json.loads(input_str)
                min_length = params.get("min_length", 3)
                max_length = params.get("max_length", 5)
            elif isinstance(input_str, dict):
                min_length = input_str.get("min_length", 3)
                max_length = input_str.get("max_length", 5)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Cycle param parse failed (%s); using defaults.", e)
        return detect_cycles_tool(G, min_length=min_length, max_length=max_length)

    def _run_entity_lookup(account_id: str) -> str:
        return single_entity_lookup(G, df, str(account_id).strip())

    def _run_typology(_input: str = "") -> str:
        return detect_typology_tool(df, patterns_data=patterns_data)

    def _run_geo_risk(_input: str = "") -> str:
        return geo_risk_tool(df)

    def _run_feature_engineering(_input: str = "") -> str:
        return feature_engineering_tool(df)

    def _run_anomaly_detection(input_str: str = "") -> str:
        method = "hybrid"
        try:
            if input_str and isinstance(input_str, str):
                params = json.loads(input_str)
                method = params.get("method", "hybrid")
        except (json.JSONDecodeError, AttributeError):
            pass
        return anomaly_detection_tool(df, G, method=method)

    def _run_risk_classification(_input: str = "") -> str:
        # Run anomaly detection first to get scores, then classify
        anomaly_result_str = anomaly_detection_tool(df, G, method="hybrid")
        try:
            anomaly_result = json.loads(anomaly_result_str)
        except (json.JSONDecodeError, TypeError):
            anomaly_result = {}
        return risk_classification_tool(anomaly_result)

    geo_note = (
        "Cross-border corridor and country-level laundering risk. "
        if dataset_format == DATASET_FORMAT_SAML
        else "Note: current dataset has no geographic locations; tool will return unavailable. "
    )

    # Select the tool factory dynamically
    tool_factory = SimpleTool if use_simple_tools else Tool

    tools = [
        tool_factory(
            name="Automated_EDA",
            func=_run_eda,
            description=(
                "Run Exploratory Data Analysis on the full AML transaction dataset. "
                "Returns baseline statistics: total transactions, total volume (USD), "
                "average transaction amount, flagged laundering ratio, top 5 active "
                "senders/receivers, and payment format distribution. "
                "Use this tool when the user asks about general statistics, overviews, "
                "dataset summaries, average amounts, or baseline metrics."
            ),
        ),
        tool_factory(
            name="Smurfing_Detector",
            func=_run_smurfing,
            description=(
                "Detect structuring/smurfing (fan-in) patterns in the transaction graph. "
                "Identifies accounts receiving many small transfers (under a threshold) "
                "from multiple distinct sources — a classic money laundering technique. "
                "Returns flagged accounts with risk scores, explanations, and "
                "recommended escalation actions. "
                "Use this tool when the user asks about structuring, smurfing, "
                "fan-in patterns, many small deposits, or transactions under reporting "
                "thresholds like $10,000."
            ),
        ),
        tool_factory(
            name="Cycle_Detector",
            func=_run_cycles,
            description=(
                "Detect circular money loops (A→B→C→A) indicating layering networks. "
                "Uses graph cycle detection algorithms to find directed cycles of "
                "length 3-5. Circular flows are a strong indicator of sophisticated "
                "money laundering through layering. "
                "Returns detected cycles with high risk scores (≥90), path details, "
                "flow estimates, and SAR filing recommendations. "
                "Use this tool when the user asks about circular transactions, "
                "money loops, layering, round-tripping, or cyclic patterns."
            ),
        ),
        tool_factory(
            name="Single_Entity_Lookup",
            func=_run_entity_lookup,
            description=(
                "Inspect a specific account for suspicious activity indicators. "
                "Computes in-degree, out-degree, transaction volumes, counterparty "
                "counts, laundering flags, and participation in cycles. "
                "Returns a detailed account profile with risk assessment. "
                "Use this tool when the user asks about a SPECIFIC account ID, "
                "customer, or entity. Extract the account ID from the query "
                "and pass it as input."
            ),
        ),
        tool_factory(
            name="Typology_Analyzer",
            func=_run_typology,
            description=(
                "Analyse laundering typology distribution and risk levels. "
                "For SAML-D: uses explicit Laundering_type labels (17 categories). "
                "For IBM datasets: supplements with Patterns.txt ground truth when available. "
                "Use when the user asks about typologies, pattern categories, Smurfing vs "
                "Fan-In breakdown, or laundering scheme distribution."
            ),
        ),
        tool_factory(
            name="Geo_Risk_Analyzer",
            func=_run_geo_risk,
            description=(
                geo_note
                + "Returns cross-border vs domestic counts, top corridors, and per-country "
                "laundering exposure. Use when the user asks about geographic risk, "
                "cross-border flows, jurisdictions, or international corridors."
            ),
        ),
        # ─── NEW TOOLS ───────────────────────────────────────────────────
        tool_factory(
            name="Feature_Engineer",
            func=_run_feature_engineering,
            description=(
                "Create AML-specific features from transaction data for analysis. "
                "Computes 12 features including: transaction frequency, average amount, "
                "amount standard deviation, rolling sums, velocity (txns/day), "
                "amount deviation from mean, rapid cash-out flags, round amount ratio, "
                "night transaction ratio, counterparty concentration (Herfindahl index), "
                "max single transaction, and dormancy reactivation flags. "
                "Use this tool when the user asks about features, metrics, patterns, "
                "or when preparing data for anomaly detection."
            ),
        ),
        tool_factory(
            name="Anomaly_Detector",
            func=_run_anomaly_detection,
            description=(
                "Run ML-based and statistical anomaly detection on transaction data. "
                "Supports three methods: 'ml' (Isolation Forest), 'statistical' "
                "(Z-score + IQR), or 'hybrid' (ensemble of both). "
                "Returns flagged accounts with risk scores, ML scores, statistical "
                "scores, risk factors, and recommended actions. "
                "Use this tool when the user asks about anomalies, suspicious activity, "
                "outliers, unusual patterns, or wants ML-based detection."
            ),
        ),
        tool_factory(
            name="Risk_Classifier",
            func=_run_risk_classification,
            description=(
                "Perform comprehensive risk classification combining ML anomaly scores, "
                "graph analysis signals, and business rules. Produces final risk levels "
                "(HIGH/MEDIUM/LOW) with score breakdowns and escalation recommendations. "
                "Use this tool when the user asks about risk scores, risk classification, "
                "risk ratings, or wants a complete risk assessment."
            ),
        ),
    ]

    return tools


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_aml_agent(
    df: pd.DataFrame,
    G: nx.DiGraph,
    api_key: str,
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
    dataset_format: str = "ibm",
    patterns_data: Optional[Dict[str, Any]] = None,
) -> Any:
    """Create a dynamic LangChain agent or fallback executor for AML analysis.

    Args:
        df: Transaction DataFrame.
        G: NetworkX directed graph of transactions.
        api_key: OpenAI API key (empty string triggers fallback mode).
        model_name: LLM model name.
        temperature: LLM temperature.
        dataset_format: 'ibm' or 'saml'.
        patterns_data: Optional patterns metadata dict.

    Returns:
        AgentExecutor (LLM mode) or SimpleExecutor (fallback mode).
    """
    logger.info("Creating AML agent with model=%s …", model_name)

    # Check if we should fall back to rule-based execution
    use_fallback = not api_key or not LLM_AVAILABLE or ChatOpenAI is None or create_openai_tools_agent is None

    # Create tools according to fallback status
    tools = _create_tools(
        df, 
        G, 
        dataset_format=dataset_format, 
        patterns_data=patterns_data, 
        use_simple_tools=use_fallback
    )

    if use_fallback:
        logger.warning("No valid OpenAI configuration or LangChain tool definition available; using local rule-based executor.")
        return SimpleExecutor(tools, df=df, G=G)

    # Initialize LLM
    llm = ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=api_key,
    )

    # Build prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create agent with OpenAI tools binding
    agent = create_openai_tools_agent(llm, tools, prompt)

    # Wrap in executor with error handling
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True,
    )

    logger.info("AML agent created successfully with %d tools", len(tools))
    return executor


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent_query(
    executor: Any,
    query: str,
) -> Dict[str, Any]:
    """Execute a natural language query through the AML agent.

    Args:
        executor: AgentExecutor or SimpleExecutor instance.
        query: Natural language query string.

    Returns:
        Dictionary with 'output', 'intermediate_steps', 'tools_used',
        'tool_outputs', and optionally 'execution_summary' and 'parsed_intent'.
    """
    if hasattr(executor, "invoke"):
        return executor.invoke({"input": query})
    raise ValueError("Invalid executor passed to run_agent_query")