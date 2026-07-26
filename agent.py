"""
agent.py — Dynamic LangChain Agent Orchestrator for AML Analysis.

This module wraps the graph_engine analysis functions as LangChain Tools
and creates a dynamic agent that:
  1. Parses natural language queries from compliance officers
  2. Extracts intent, entities, and filters
  3. Selectively invokes ONLY the tools needed to answer the query
  4. Returns structured, explainable results
"""

import json
import os
import re
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
    load_aml_data,
    single_entity_lookup,
)
from src.utils import DATASET_FORMAT_SAML, get_logger

logger = get_logger(__name__)


class SimpleAction:
    def __init__(self, tool_name: str, tool_input: Any):
        self.tool = tool_name
        self.tool_input = tool_input


class SimpleExecutor:
    """Rule-based executor used when LangChain's agent runtime is unavailable."""

    def __init__(self, tools: List[Any]):
        self.tools = tools

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = str(inputs.get("input", ""))
        lowered = query.lower()

        selected_tools: List[Any] = []
        tool_inputs: List[Tuple[str, Any]] = []

        if any(k in lowered for k in ["overview", "baseline", "statistics", "summary", "eda"]):
            selected_tools.append(next(t for t in self.tools if t.name == "Automated_EDA"))
            tool_inputs.append(("Automated_EDA", ""))

        if any(k in lowered for k in ["smurf", "structur", "fan-in", "fan in", "under $10,000", "under 10000", "threshold", "small deposit"]):
            selected_tools.append(next(t for t in self.tools if t.name == "Smurfing_Detector"))
            tool_inputs.append(("Smurfing_Detector", {"min_fan_in": 5, "amount_cap": 10000.0}))

        if any(k in lowered for k in ["cycle", "loop", "layer", "circular", "round-tripping"]):
            selected_tools.append(next(t for t in self.tools if t.name == "Cycle_Detector"))
            tool_inputs.append(("Cycle_Detector", {"min_length": 3, "max_length": 5}))

        if any(k in lowered for k in ["account", "customer", "entity", "profile"]):
            account_match = re.search(r"(?:account|customer|entity)\s*[:#-]?\s*([A-Za-z0-9_-]+)", query, re.I)
            if account_match:
                account_id = account_match.group(1)
                selected_tools.append(next(t for t in self.tools if t.name == "Single_Entity_Lookup"))
                tool_inputs.append(("Single_Entity_Lookup", account_id))

        if any(k in lowered for k in ["typology", "breakdown", "category", "pattern"]):
            selected_tools.append(next(t for t in self.tools if t.name == "Typology_Analyzer"))
            tool_inputs.append(("Typology_Analyzer", ""))

        if any(k in lowered for k in ["geo", "geographic", "country", "cross-border", "cross border", "corridor", "jurisdiction", "international"]):
            selected_tools.append(next(t for t in self.tools if t.name == "Geo_Risk_Analyzer"))
            tool_inputs.append(("Geo_Risk_Analyzer", ""))

        if not selected_tools:
            selected_tools = [next(t for t in self.tools if t.name == "Automated_EDA")]
            tool_inputs.append(("Automated_EDA", ""))

        intermediate_steps = []
        tool_outputs = []
        output_lines = [f"Processed query: {query}", f"Selected {len(selected_tools)} tool(s)."]

        for tool, tool_input in tool_inputs:
            tool_obj = next(t for t in self.tools if t.name == tool)
            
            if hasattr(tool_obj, "invoke"):
                output = tool_obj.invoke(tool_input if isinstance(tool_input, str) else json.dumps(tool_input))
            elif hasattr(tool_obj, "func"):
                output = tool_obj.func(tool_input)
            else:
                output = str(tool_obj)

            intermediate_steps.append((SimpleAction(tool, tool_input), output))
            tool_outputs.append({"tool": tool, "input": tool_input, "output": output})
            output_lines.append(f"- {tool}: completed")

        return {
            "output": "\n".join(output_lines),
            "intermediate_steps": intermediate_steps,
            "tools_used": [step[0].tool for step in intermediate_steps],
            "tool_outputs": tool_outputs,
        }


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
6. For laundering typology breakdowns (Smurfing, Fan-In, Cycle, etc.) → use Typology_Analyzer
7. For cross-border flows, corridors, and geographic risk → use Geo_Risk_Analyzer
   (only meaningful when the loaded dataset includes bank location columns, e.g. SAML-D)
8. Always provide clear, actionable explanations with your findings.
9. When reporting risk scores, explain what factors contributed to the score.
10. If the user asks about a specific account, extract the account ID from their query.
11. If Geo_Risk_Analyzer returns has_geo_data=false, explain that geo analysis requires SAML-D.

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
    """Create Tool instances wrapping graph_engine functions."""

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
        except (json.JSONDecodeError, AttributeError):
            pass
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
        except (json.JSONDecodeError, AttributeError):
            pass
        return detect_cycles_tool(G, min_length=min_length, max_length=max_length)

    def _run_entity_lookup(account_id: str) -> str:
        return single_entity_lookup(G, df, str(account_id).strip())

    def _run_typology(_input: str = "") -> str:
        return detect_typology_tool(df, patterns_data=patterns_data)

    def _run_geo_risk(_input: str = "") -> str:
        return geo_risk_tool(df)

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
    """Create a dynamic LangChain agent or fallback executor for AML analysis."""
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
        return SimpleExecutor(tools)

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
    """Execute a natural language query through the AML agent."""
    if hasattr(executor, "invoke"):
        return executor.invoke({"input": query})
    raise ValueError("Invalid executor passed to run_agent_query")