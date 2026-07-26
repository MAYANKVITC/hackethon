"""
graph_engine.py — Data Loading, Graph Construction & AML Analysis Tools.

This module provides the core analytical backend for the AML agent.
It reads IBM Synthetic AML datasets OR the SAML-D dataset, normalises them
to a canonical schema, builds a directed transaction graph with NetworkX,
and exposes six analysis tools:

  1. eda_tool                  — Exploratory Data Analysis (baseline statistics)
  2. detect_smurfing_tool      — Fan-in structuring / smurfing detection
  3. detect_cycles_tool        — Circular layering / money loop detection
  4. single_entity_lookup      — On-demand single-account inspection
  5. detect_typology_tool      — Laundering typology breakdown & comparison
  6. geo_risk_tool             — Cross-border geographic risk analysis (SAML-D)

Dataset auto-detection:
  - IBM datasets have columns: Timestamp, From Bank, Account, To Bank, Amount Paid, Payment Format, Is Laundering
  - SAML-D has columns: Time, Date, Sender_account, Receiver_account, Amount, Payment_type, Is_laundering, Laundering_type, Sender_bank_location, Receiver_bank_location
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import pandas as pd

from src.utils import (
    DATASET_FORMAT_IBM,
    DATASET_FORMAT_SAML,
    GRAPH_SAMPLE_LIMIT,
    TYPOLOGY_DESCRIPTIONS,
    TYPOLOGY_RISK_MAP,
    classify_risk,
    format_currency,
    get_logger,
)

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA DETECTION & NORMALISATION
# ═══════════════════════════════════════════════════════════════════════════════


def _detect_format(df: pd.DataFrame) -> str:
    """Detect whether the loaded DataFrame is IBM or SAML-D format.

    Args:
        df: Raw DataFrame loaded from CSV.

    Returns:
        DATASET_FORMAT_IBM or DATASET_FORMAT_SAML constant.
    """
    if "Sender_account" in df.columns and "Receiver_account" in df.columns:
        return DATASET_FORMAT_SAML
    if "From Bank" in df.columns or "Account" in df.columns:
        return DATASET_FORMAT_IBM
    # Fallback: try to guess from presence of IBM-specific columns
    return DATASET_FORMAT_IBM


def _normalise_ibm(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise IBM-format DataFrame to canonical schema.

    IBM canonical columns:
        Timestamp, From Bank, Account, To Bank, Account.1,
        Amount Received, Receiving Currency, Amount Paid, Payment Currency,
        Payment Format, Is Laundering

    Returns DataFrame with canonical columns added.
    """
    required = {"From Bank", "Account", "To Bank", "Amount Paid", "Payment Format", "Is Laundering"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"IBM CSV missing columns: {missing}")

    df = df.copy()

    receiver_acct = (
        df["Account.1"] if "Account.1" in df.columns else df["Account"]
    )
    df["sender_id"] = df["From Bank"].astype(str) + "_" + df["Account"].astype(str)
    df["receiver_id"] = df["To Bank"].astype(str) + "_" + receiver_acct.astype(str)

    # Canonical columns
    df["timestamp"]       = pd.to_datetime(df["Timestamp"], errors="coerce") if "Timestamp" in df.columns else pd.NaT
    df["amount"]          = pd.to_numeric(df["Amount Paid"], errors="coerce").fillna(0.0)
    df["amount_received"] = pd.to_numeric(df.get("Amount Received", df["Amount Paid"]), errors="coerce").fillna(0.0)
    df["payment_format"]  = df["Payment Format"].astype(str)
    df["is_laundering"]   = df["Is Laundering"].astype(int)
    df["laundering_type"] = "UNKNOWN"   # IBM doesn't have per-row type labels
    df["sender_currency"] = df["Payment Currency"].astype(str) if "Payment Currency" in df.columns else "USD"
    df["receiver_currency"] = df["Receiving Currency"].astype(str) if "Receiving Currency" in df.columns else "USD"
    df["sender_location"] = "Unknown"
    df["receiver_location"] = "Unknown"
    df["dataset_format"]  = DATASET_FORMAT_IBM

    return df


def _normalise_saml(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise SAML-D-format DataFrame to canonical schema.

    SAML-D canonical columns:
        Time, Date, Sender_account, Receiver_account, Amount,
        Payment_currency, Received_currency, Sender_bank_location,
        Receiver_bank_location, Payment_type, Is_laundering, Laundering_type

    Returns DataFrame with canonical columns added.
    """
    required = {"Sender_account", "Receiver_account", "Amount", "Is_laundering"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"SAML-D CSV missing columns: {missing}")

    df = df.copy()

    # Build timestamp from separate Date + Time columns
    if "Date" in df.columns and "Time" in df.columns:
        df["timestamp"] = pd.to_datetime(
            df["Date"].astype(str) + " " + df["Time"].astype(str), errors="coerce"
        )
    elif "Date" in df.columns:
        df["timestamp"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        df["timestamp"] = pd.NaT

    df["sender_id"]         = df["Sender_account"].astype(str)
    df["receiver_id"]       = df["Receiver_account"].astype(str)
    df["amount"]            = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    df["amount_received"]   = df["amount"]   # SAML-D has one Amount column
    df["payment_format"]    = df["Payment_type"].astype(str) if "Payment_type" in df.columns else "Unknown"
    df["is_laundering"]     = df["Is_laundering"].astype(int)
    df["laundering_type"]   = df["Laundering_type"].astype(str) if "Laundering_type" in df.columns else "UNKNOWN"
    df["sender_currency"]   = df["Payment_currency"].astype(str) if "Payment_currency" in df.columns else "Unknown"
    df["receiver_currency"] = df["Received_currency"].astype(str) if "Received_currency" in df.columns else "Unknown"
    df["sender_location"]   = df["Sender_bank_location"].astype(str) if "Sender_bank_location" in df.columns else "Unknown"
    df["receiver_location"] = df["Receiver_bank_location"].astype(str) if "Receiver_bank_location" in df.columns else "Unknown"
    df["dataset_format"]    = DATASET_FORMAT_SAML

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING & GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════


def load_aml_data(
    csv_path: str,
    sample_limit: Optional[int] = GRAPH_SAMPLE_LIMIT,
) -> Tuple[pd.DataFrame, nx.DiGraph, str]:
    """Load an AML dataset (IBM or SAML-D), normalise it, and build a directed graph.

    Auto-detects the dataset format from column names, then:
      - Normalises columns to a canonical schema
      - Optionally samples large datasets for graph construction performance
      - Builds a NetworkX DiGraph where edges = transactions

    Args:
        csv_path: Filesystem path to the transactions CSV file.
        sample_limit: Maximum rows to include in the graph. None = no limit.

    Returns:
        Tuple of (normalised DataFrame, DiGraph, dataset_format string).

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If required columns are missing.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at '{csv_path}'. "
            "Please ensure the dataset path is correct."
        )

    logger.info("Loading dataset from %s …", csv_path)
    df_raw = pd.read_csv(csv_path, low_memory=False)
    logger.info("Raw shape: %d rows × %d cols", *df_raw.shape)

    # ── Detect format & normalise ─────────────────────────────────────────
    fmt = _detect_format(df_raw)
    logger.info("Detected dataset format: %s", fmt)

    if fmt == DATASET_FORMAT_SAML:
        df = _normalise_saml(df_raw)
    else:
        df = _normalise_ibm(df_raw)

    # ── Construct directed graph ──────────────────────────────────────────
    logger.info("Building directed transaction graph …")

    # Optionally sample for performance on huge datasets
    df_graph = df if sample_limit is None or len(df) <= sample_limit else df.sample(
        n=sample_limit, random_state=42
    )
    if len(df) > len(df_graph):
        logger.warning(
            "Graph built from sampled %d / %d rows for performance.",
            len(df_graph), len(df),
        )

    G = nx.DiGraph()

    # Vectorised edge construction (much faster than iterrows)
    edge_records = df_graph[
        ["sender_id", "receiver_id", "amount", "payment_format", "is_laundering",
         "laundering_type", "sender_location", "receiver_location", "sender_currency"]
    ].to_dict(orient="records")

    for rec in edge_records:
        G.add_edge(
            rec["sender_id"],
            rec["receiver_id"],
            amount=float(rec["amount"]),
            payment_format=str(rec["payment_format"]),
            is_laundering=int(rec["is_laundering"]),
            laundering_type=str(rec["laundering_type"]),
            sender_location=str(rec["sender_location"]),
            receiver_location=str(rec["receiver_location"]),
            currency=str(rec["sender_currency"]),
        )

    logger.info(
        "Graph built: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges()
    )
    return df, G, fmt


def load_accounts_data(accounts_path: str) -> Optional[pd.DataFrame]:
    """Load IBM accounts metadata (bank name, entity name).

    Args:
        accounts_path: Path to the _accounts.csv file.

    Returns:
        DataFrame with account metadata, or None if file not found.
    """
    path = Path(accounts_path)
    if not path.exists():
        logger.warning("Accounts file not found: %s", accounts_path)
        return None
    df = pd.read_csv(accounts_path)
    logger.info("Accounts loaded: %d records", len(df))
    return df


def load_patterns_data(patterns_path: str) -> Dict[str, Any]:
    """Parse IBM Patterns.txt for ground-truth laundering attempt metadata.

    The file contains blocks like:
        BEGIN LAUNDERING ATTEMPT - FAN-OUT:  Max 16-degree Fan-Out
        <transaction rows>
        END LAUNDERING ATTEMPT - FAN-OUT

    Args:
        patterns_path: Path to the _Patterns.txt file.

    Returns:
        Dict with typology counts and summary.
    """
    path = Path(patterns_path)
    if not path.exists():
        return {}

    typology_counts: Dict[str, int] = {}
    total_attempts = 0

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("BEGIN LAUNDERING ATTEMPT"):
                total_attempts += 1
                # Extract typology name: "BEGIN LAUNDERING ATTEMPT - FAN-OUT: ..."
                match = re.match(r"BEGIN LAUNDERING ATTEMPT - ([A-Z\-]+)", line)
                if match:
                    typology = match.group(1)
                    typology_counts[typology] = typology_counts.get(typology, 0) + 1

    return {
        "total_attempts": total_attempts,
        "typology_counts": typology_counts,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 1: EXPLORATORY DATA ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


def eda_tool(df: pd.DataFrame) -> str:
    """Generate baseline exploratory data analysis statistics.

    Computes:
      - Total number of transactions
      - Total transaction volume
      - Average transaction amount
      - Flagged-as-laundering ratio
      - Top 5 most active senders and receivers
      - Payment format distribution
      - Currency distribution (if multi-currency)
      - Laundering type distribution (if available)

    Args:
        df: Normalised transaction DataFrame (canonical columns).

    Returns:
        JSON-formatted string containing all EDA results.
    """
    logger.info("Running Exploratory Data Analysis …")

    total_txns = len(df)
    total_volume = float(df["amount"].sum())
    avg_amount = float(df["amount"].mean())
    flagged_count = int(df["is_laundering"].sum())
    flagged_ratio = flagged_count / total_txns if total_txns > 0 else 0.0
    dataset_fmt = str(df["dataset_format"].iloc[0]) if "dataset_format" in df.columns else "unknown"

    # Top 5 senders by transaction count
    top_senders = (
        df["sender_id"]
        .value_counts()
        .head(5)
        .reset_index()
        .rename(columns={"sender_id": "account", "count": "transactions"})
        .to_dict(orient="records")
    )

    # Top 5 receivers by transaction count
    top_receivers = (
        df["receiver_id"]
        .value_counts()
        .head(5)
        .reset_index()
        .rename(columns={"receiver_id": "account", "count": "transactions"})
        .to_dict(orient="records")
    )

    # Payment format distribution
    payment_dist = (
        df["payment_format"]
        .value_counts()
        .reset_index()
        .rename(columns={"payment_format": "format", "count": "count"})
        .to_dict(orient="records")
    )

    # Laundering type distribution (available in SAML-D and when known)
    laundering_type_dist = []
    if "laundering_type" in df.columns:
        laundering_type_dist = (
            df[df["is_laundering"] == 1]["laundering_type"]
            .value_counts()
            .reset_index()
            .rename(columns={"laundering_type": "type", "count": "count"})
            .head(20)
            .to_dict(orient="records")
        )

    # Currency distribution
    currency_dist = []
    if "sender_currency" in df.columns:
        currency_dist = (
            df["sender_currency"]
            .value_counts()
            .head(10)
            .reset_index()
            .rename(columns={"sender_currency": "currency", "count": "count"})
            .to_dict(orient="records")
        )

    # Cross-border stats (SAML-D)
    cross_border_count = 0
    if "sender_location" in df.columns and "receiver_location" in df.columns:
        cross_border_count = int(
            (df["sender_location"] != df["receiver_location"]).sum()
        )

    result = {
        "tool": "Automated_EDA",
        "dataset_format": dataset_fmt,
        "summary": {
            "total_transactions": total_txns,
            "total_volume_usd": round(total_volume, 2),
            "average_amount_usd": round(avg_amount, 2),
            "flagged_laundering_count": flagged_count,
            "flagged_laundering_ratio": round(flagged_ratio, 4),
            "cross_border_transactions": cross_border_count,
        },
        "top_5_senders": top_senders,
        "top_5_receivers": top_receivers,
        "payment_format_distribution": payment_dist,
        "laundering_type_distribution": laundering_type_dist,
        "currency_distribution": currency_dist,
    }

    logger.info(
        "EDA complete: %d transactions, volume=%s, flagged=%d",
        total_txns, format_currency(total_volume), flagged_count,
    )
    return json.dumps(result, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 2: SMURFING / STRUCTURING DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


def detect_smurfing_tool(
    G: nx.DiGraph,
    min_fan_in: int = 5,
    amount_cap: float = 10000.0,
) -> str:
    """Detect fan-in structuring (smurfing) patterns in the transaction graph.

    Scans all nodes for accounts receiving ≥ ``min_fan_in`` distinct
    transfers where each individual transaction is below ``amount_cap``.
    This pattern is a hallmark of "smurfing" — breaking large sums into
    many small deposits to evade reporting thresholds.

    Risk scoring formula:
      - Base score starts at 60
      - +2 per additional source beyond ``min_fan_in``
      - +10 if total aggregate exceeds 2× the amount_cap
      - +5 if all payments use the same payment format (unusual uniformity)
      - +5 for very high fan-in (2× min_fan_in)
      - +15 if laundering_type label confirms smurfing/structuring
      - Capped at 100

    Args:
        G: Directed transaction graph.
        min_fan_in: Minimum number of distinct senders to flag.
        amount_cap: Maximum individual transaction amount to consider.

    Returns:
        JSON-formatted string with flagged accounts, risk scores,
        explanations, and recommended actions.
    """
    logger.info(
        "Running smurfing detection (min_fan_in=%d, cap=%s) …",
        min_fan_in, format_currency(amount_cap),
    )

    flagged_accounts: List[Dict[str, Any]] = []
    subgraph_edges: List[Dict[str, str]] = []

    for node in G.nodes():
        in_edges = list(G.in_edges(node, data=True))
        if not in_edges:
            continue

        # Filter edges below amount cap
        small_transfers = [
            (u, v, d) for u, v, d in in_edges
            if d.get("amount", 0) < amount_cap
        ]

        distinct_senders = set(u for u, v, d in small_transfers)

        if len(distinct_senders) >= min_fan_in:
            total_amount = sum(d.get("amount", 0) for _, _, d in small_transfers)
            num_txns = len(small_transfers)
            formats = set(d.get("payment_format", "") for _, _, d in small_transfers)
            laundering_labels = set(d.get("laundering_type", "UNKNOWN") for _, _, d in small_transfers)

            # ── Dynamic risk scoring ──────────────────────────────────────
            risk_score = 60.0
            risk_score += min(20, 2 * (len(distinct_senders) - min_fan_in))
            if total_amount > 2 * amount_cap:
                risk_score += 10
            if len(formats) == 1:
                risk_score += 5
            if len(distinct_senders) >= min_fan_in * 2:
                risk_score += 5
            # Bonus if labels confirm smurfing/structuring
            confirmed_labels = {"Smurfing", "Structuring", "Fan_In", "FAN-IN"}
            if laundering_labels & confirmed_labels:
                risk_score += 15
            risk_score = min(100.0, risk_score)

            risk_level = classify_risk(risk_score)
            action = "FILE SAR REPORT" if risk_score >= 75 else "FLAG FOR REVIEW"

            known_typologies = [
                t for t in laundering_labels
                if t not in ("UNKNOWN", "Normal", "Normal_Fan_In", "Normal_Cash_Deposits",
                             "Normal_Fan_Out", "Normal_Small_Fan_Out")
            ]

            explanation = (
                f"Account '{node}' received {num_txns} transactions "
                f"(total {format_currency(total_amount)}) from "
                f"{len(distinct_senders)} distinct sources, all under "
                f"{format_currency(amount_cap)}. "
                f"This fan-in pattern is consistent with structuring/smurfing. "
                f"Payment formats used: {', '.join(formats)}."
            )
            if known_typologies:
                explanation += f" Confirmed laundering typologies: {', '.join(known_typologies)}."

            flagged_accounts.append({
                "account": node,
                "risk_score": round(risk_score, 1),
                "risk_level": risk_level,
                "distinct_senders": len(distinct_senders),
                "total_transactions": num_txns,
                "total_amount_usd": round(total_amount, 2),
                "confirmed_typologies": known_typologies,
                "explanation": explanation,
                "recommended_action": action,
            })

            # Collect edges for visualization (limit per node for performance)
            for u, v, d in small_transfers[:20]:
                subgraph_edges.append({
                    "source": u,
                    "target": v,
                    "amount": round(d.get("amount", 0), 2),
                })

    flagged_accounts.sort(key=lambda x: x["risk_score"], reverse=True)

    result = {
        "tool": "Smurfing_Detector",
        "typology": "Structuring / Smurfing (Fan-In)",
        "parameters": {
            "min_fan_in": min_fan_in,
            "amount_cap": amount_cap,
        },
        "total_flagged": len(flagged_accounts),
        "flagged_accounts": flagged_accounts[:50],
        "subgraph_edges": subgraph_edges[:300],
    }

    logger.info("Smurfing detection complete: %d accounts flagged", len(flagged_accounts))
    return json.dumps(result, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 3: CIRCULAR LAYERING / CYCLE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


def detect_cycles_tool(
    G: nx.DiGraph,
    min_length: int = 3,
    max_length: int = 5,
) -> str:
    """Detect circular money loops indicating layering networks.

    Uses ``nx.simple_cycles`` to identify directed cycles in the
    transaction graph. Cycles of length ≥ ``min_length`` and
    ≤ ``max_length`` are flagged as potential layering schemes (A→B→C→A).

    Args:
        G: Directed transaction graph.
        min_length: Minimum cycle length to report.
        max_length: Maximum cycle length to report.

    Returns:
        JSON-formatted string with detected cycles, risk scores,
        and visualization edges.
    """
    logger.info("Running cycle detection (length %d–%d) …", min_length, max_length)

    detected_cycles: List[Dict[str, Any]] = []
    cycle_edges: List[Dict[str, str]] = []
    cycle_count = 0
    max_cycles_to_report = 30

    try:
        for cycle in nx.simple_cycles(G, length_bound=max_length):
            if len(cycle) < min_length:
                continue

            cycle_count += 1
            if cycle_count > max_cycles_to_report:
                break

            # Estimate flow along the cycle path
            path_amounts: List[float] = []
            cycle_typologies: List[str] = []
            for i in range(len(cycle)):
                u = cycle[i]
                v = cycle[(i + 1) % len(cycle)]
                edge_data = G.get_edge_data(u, v, default={})
                path_amounts.append(edge_data.get("amount", 0.0))
                lt = edge_data.get("laundering_type", "UNKNOWN")
                if lt not in ("UNKNOWN", "Normal"):
                    cycle_typologies.append(lt)

            estimated_flow = min(path_amounts) if path_amounts else 0.0
            total_flow = sum(path_amounts)

            # Risk scoring
            risk_score = 90.0
            if len(cycle) >= 4:
                risk_score += 5
            if total_flow > 50000:
                risk_score += 5
            risk_score = min(100.0, risk_score)

            cycle_path_str = " → ".join(str(c)[-12:] for c in cycle) + " → " + str(cycle[0])[-12:]

            explanation = (
                f"Circular money loop detected ({len(cycle)} hops). "
                f"Estimated flow: {format_currency(estimated_flow)}, "
                f"total path volume: {format_currency(total_flow)}. "
                f"Circular transaction patterns are a strong indicator of "
                f"layering — a technique used to obscure the audit trail of illicit funds."
            )
            if cycle_typologies:
                explanation += f" Confirmed typologies: {', '.join(set(cycle_typologies))}."

            detected_cycles.append({
                "cycle_id": cycle_count,
                "cycle_path": cycle_path_str,
                "cycle_length": len(cycle),
                "estimated_flow_usd": round(estimated_flow, 2),
                "total_path_volume_usd": round(total_flow, 2),
                "confirmed_typologies": list(set(cycle_typologies)),
                "risk_score": round(risk_score, 1),
                "risk_level": "HIGH",
                "explanation": explanation,
                "recommended_action": "FILE SAR REPORT",
                "accounts_involved": [str(c) for c in cycle],
            })

            for i in range(len(cycle)):
                u = cycle[i]
                v = cycle[(i + 1) % len(cycle)]
                edge_data = G.get_edge_data(u, v, default={})
                cycle_edges.append({
                    "source": str(u),
                    "target": str(v),
                    "amount": round(edge_data.get("amount", 0.0), 2),
                })

    except Exception as e:
        logger.warning("Cycle detection encountered an issue: %s", str(e))

    result = {
        "tool": "Cycle_Detector",
        "typology": "Circular Layering",
        "parameters": {"min_length": min_length, "max_length": max_length},
        "total_cycles_found": len(detected_cycles),
        "note": f"Showing up to {max_cycles_to_report} cycles. Large graphs may contain many more.",
        "detected_cycles": detected_cycles,
        "cycle_edges": cycle_edges[:300],
    }

    logger.info("Cycle detection complete: %d cycles found", len(detected_cycles))
    return json.dumps(result, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 4: SINGLE ENTITY LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════


def single_entity_lookup(
    G: nx.DiGraph,
    df: pd.DataFrame,
    account_id: str,
) -> str:
    """Inspect a single account for suspicious indicators.

    Args:
        G: Directed transaction graph.
        df: Normalised transaction DataFrame.
        account_id: The account identifier to look up.

    Returns:
        JSON-formatted string with account profile and risk indicators.
    """
    logger.info("Looking up entity: %s", account_id)

    matching_nodes = [n for n in G.nodes() if account_id in str(n)]

    if not matching_nodes:
        return json.dumps({
            "tool": "Single_Entity_Lookup",
            "account_id": account_id,
            "status": "NOT_FOUND",
            "message": (
                f"Account '{account_id}' was not found in the transaction graph. "
                "Please verify the account ID and try again."
            ),
        }, indent=2)

    node = matching_nodes[0]

    in_edges = list(G.in_edges(node, data=True))
    out_edges = list(G.out_edges(node, data=True))

    total_received = sum(d.get("amount", 0) for _, _, d in in_edges)
    total_sent = sum(d.get("amount", 0) for _, _, d in out_edges)
    in_senders = set(u for u, _, _ in in_edges)
    out_receivers = set(v for _, v, _ in out_edges)

    flagged_in = sum(1 for _, _, d in in_edges if d.get("is_laundering", 0) == 1)
    flagged_out = sum(1 for _, _, d in out_edges if d.get("is_laundering", 0) == 1)
    total_flagged = flagged_in + flagged_out

    # Collect typologies (SAML-D)
    all_typologies = set()
    for _, _, d in in_edges + out_edges:
        lt = d.get("laundering_type", "UNKNOWN")
        if lt not in ("UNKNOWN", "Normal"):
            all_typologies.add(lt)

    formats_in = set(d.get("payment_format", "") for _, _, d in in_edges)
    formats_out = set(d.get("payment_format", "") for _, _, d in out_edges)
    locations_in = set(d.get("sender_location", "Unknown") for _, _, d in in_edges)
    locations_out = set(d.get("receiver_location", "Unknown") for _, _, d in out_edges)

    # ── Risk assessment ───────────────────────────────────────────────────
    risk_score = 0.0
    risk_factors: List[str] = []

    if total_flagged > 0:
        risk_score += 40
        risk_factors.append(f"{total_flagged} transactions flagged as laundering")

    if G.in_degree(node) >= 10:
        risk_score += 15
        risk_factors.append(f"High fan-in: {G.in_degree(node)} incoming connections")

    if G.out_degree(node) >= 10:
        risk_score += 15
        risk_factors.append(f"High fan-out: {G.out_degree(node)} outgoing connections")

    if total_received > 100000:
        risk_score += 10
        risk_factors.append(f"High inbound volume: {format_currency(total_received)}")

    if total_sent > 100000:
        risk_score += 10
        risk_factors.append(f"High outbound volume: {format_currency(total_sent)}")

    if all_typologies:
        risk_score += 10
        risk_factors.append(f"Associated laundering typologies: {', '.join(all_typologies)}")

    cross_border = (locations_in | locations_out) - {"Unknown"}
    if len(cross_border) > 2:
        risk_score += 5
        risk_factors.append(f"Cross-border activity across {len(cross_border)} jurisdictions")

    # Check if account appears in cycles
    try:
        has_cycle = any(
            node in cycle
            for cycle in nx.simple_cycles(
                G.subgraph(set(in_senders) | set(out_receivers) | {node}),
                length_bound=5,
            )
        )
        if has_cycle:
            risk_score += 20
            risk_factors.append("Participates in circular transaction patterns")
    except Exception:
        pass

    risk_score = min(100.0, risk_score)
    risk_level = classify_risk(risk_score)

    if not risk_factors:
        risk_factors.append("No significant risk indicators detected")

    action = "NO ACTION REQUIRED"
    if risk_score >= 75:
        action = "FILE SAR REPORT"
    elif risk_score >= 50:
        action = "FLAG FOR REVIEW"

    result = {
        "tool": "Single_Entity_Lookup",
        "account_id": node,
        "status": "FOUND",
        "profile": {
            "in_degree": G.in_degree(node),
            "out_degree": G.out_degree(node),
            "total_received_usd": round(total_received, 2),
            "total_sent_usd": round(total_sent, 2),
            "unique_senders": len(in_senders),
            "unique_receivers": len(out_receivers),
            "total_transactions": G.in_degree(node) + G.out_degree(node),
            "payment_formats_incoming": list(formats_in),
            "payment_formats_outgoing": list(formats_out),
            "locations_sending_from": list(locations_in),
            "locations_receiving_in": list(locations_out),
            "confirmed_typologies": list(all_typologies),
        },
        "risk_assessment": {
            "risk_score": round(risk_score, 1),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "flagged_transactions": total_flagged,
            "recommended_action": action,
        },
        "matching_accounts": matching_nodes[:10],
    }

    logger.info(
        "Entity lookup complete for %s: risk_score=%.1f (%s)",
        node, risk_score, risk_level,
    )
    return json.dumps(result, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 5: LAUNDERING TYPOLOGY ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════


def detect_typology_tool(
    df: pd.DataFrame,
    patterns_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Analyse the distribution and risk profile of all laundering typologies.

    For SAML-D datasets: uses the ``laundering_type`` column directly.
    For IBM datasets: shows distribution of payment formats as a proxy.

    Computes per-typology:
      - Transaction count and percentage
      - Total volume
      - Average amount
      - Risk level mapping

    Args:
        df: Normalised transaction DataFrame.

    Returns:
        JSON-formatted string with typology breakdown.
    """
    logger.info("Running Typology Analyzer …")

    dataset_fmt = str(df["dataset_format"].iloc[0]) if "dataset_format" in df.columns else "unknown"
    has_typology = (
        "laundering_type" in df.columns
        and df["laundering_type"].nunique() > 2
    )

    typology_results: List[Dict[str, Any]] = []
    ibm_patterns_summary: Optional[Dict[str, Any]] = None
    total_laundering = int(df["is_laundering"].sum())
    total_txns = len(df)

    if has_typology:
        # Use explicit laundering_type labels
        flagged_df = df[df["is_laundering"] == 1].copy()

        for typ, group in flagged_df.groupby("laundering_type"):
            if typ in ("UNKNOWN", "Normal"):
                continue
            count = len(group)
            volume = float(group["amount"].sum())
            avg_amt = float(group["amount"].mean())
            pct_of_laundering = (count / total_laundering * 100) if total_laundering > 0 else 0.0
            pct_of_all = (count / total_txns * 100) if total_txns > 0 else 0.0
            risk_level = TYPOLOGY_RISK_MAP.get(str(typ), "MEDIUM")
            description = TYPOLOGY_DESCRIPTIONS.get(str(typ), "Suspicious transaction pattern.")

            typology_results.append({
                "typology": str(typ),
                "count": count,
                "pct_of_laundering": round(pct_of_laundering, 2),
                "pct_of_all_transactions": round(pct_of_all, 4),
                "total_volume_usd": round(volume, 2),
                "average_amount_usd": round(avg_amt, 2),
                "risk_level": risk_level,
                "description": description,
            })

        # Sort by count descending
        typology_results.sort(key=lambda x: x["count"], reverse=True)

    else:
        # IBM fallback: use payment_format distribution for flagged transactions
        flagged_df = df[df["is_laundering"] == 1].copy()
        for fmt, group in flagged_df.groupby("payment_format"):
            count = len(group)
            volume = float(group["amount"].sum())
            typology_results.append({
                "typology": f"Flagged via {fmt}",
                "count": count,
                "pct_of_laundering": round(count / total_laundering * 100, 2) if total_laundering > 0 else 0,
                "pct_of_all_transactions": round(count / total_txns * 100, 4) if total_txns > 0 else 0,
                "total_volume_usd": round(volume, 2),
                "average_amount_usd": round(volume / count, 2) if count > 0 else 0,
                "risk_level": "MEDIUM",
                "description": f"Transactions flagged as laundering using {fmt} payment method.",
            })
        typology_results.sort(key=lambda x: x["count"], reverse=True)

    if (
        not has_typology
        and patterns_data
        and patterns_data.get("typology_counts")
    ):
        ibm_patterns_summary = {
            "source": "IBM Patterns.txt (ground-truth laundering attempts)",
            "total_attempts": patterns_data.get("total_attempts", 0),
            "typology_counts": patterns_data.get("typology_counts", {}),
        }
        for typ, count in patterns_data["typology_counts"].items():
            risk_level = TYPOLOGY_RISK_MAP.get(str(typ), "MEDIUM")
            description = TYPOLOGY_DESCRIPTIONS.get(str(typ), "IBM synthetic pattern attempt.")
            typology_results.append({
                "typology": str(typ),
                "count": int(count),
                "pct_of_laundering": None,
                "pct_of_all_transactions": None,
                "total_volume_usd": None,
                "average_amount_usd": None,
                "risk_level": risk_level,
                "description": description,
            })

    # High-risk summary
    high_risk_typologies = [t for t in typology_results if t["risk_level"] == "HIGH"]
    medium_risk_typologies = [t for t in typology_results if t["risk_level"] == "MEDIUM"]

    result = {
        "tool": "Typology_Analyzer",
        "dataset_format": dataset_fmt,
        "has_explicit_typology_labels": has_typology,
        "summary": {
            "total_transactions": total_txns,
            "total_laundering_transactions": total_laundering,
            "unique_typologies": len(typology_results),
            "high_risk_typologies_count": len(high_risk_typologies),
            "medium_risk_typologies_count": len(medium_risk_typologies),
        },
        "typology_breakdown": typology_results,
        "high_risk_typologies": [t["typology"] for t in high_risk_typologies],
        "ibm_patterns_summary": ibm_patterns_summary,
    }

    logger.info(
        "Typology analysis complete: %d typologies, %d laundering txns",
        len(typology_results), total_laundering,
    )
    return json.dumps(result, indent=2, default=str)


# Plan alias
detect_laundering_typology_tool = detect_typology_tool
# ═══════════════════════════════════════════════════════════════════════════════


def geo_risk_tool(df: pd.DataFrame) -> str:
    """Analyse cross-border transaction flows and geographic risk corridors.

    This tool uses ``sender_location`` and ``receiver_location`` columns,
    which are populated for SAML-D datasets. For IBM datasets it will
    return a note that geo data is unavailable.

    Computes:
      - Total cross-border vs domestic transaction counts
      - Top 10 cross-border corridors (sender → receiver country)
      - Per-country risk summary (outbound / inbound volume)
      - Cross-border laundering ratio per corridor

    Args:
        df: Normalised transaction DataFrame.

    Returns:
        JSON-formatted string with geographic risk analysis.
    """
    logger.info("Running Geographic Risk Analyzer …")

    dataset_fmt = str(df["dataset_format"].iloc[0]) if "dataset_format" in df.columns else "unknown"

    # Check if geo data is available
    has_geo = (
        "sender_location" in df.columns
        and "receiver_location" in df.columns
        and df["sender_location"].nunique() > 1
        and not (df["sender_location"] == "Unknown").all()
    )

    if not has_geo:
        return json.dumps({
            "tool": "Geo_Risk_Analyzer",
            "dataset_format": dataset_fmt,
            "has_geo_data": False,
            "note": (
                "Geographic location data is not available in this dataset. "
                "Load the SAML-D dataset to access cross-border flow analysis."
            ),
        }, indent=2)

    # ── Cross-border analysis ─────────────────────────────────────────────
    df_geo = df.copy()
    df_geo["is_cross_border"] = df_geo["sender_location"] != df_geo["receiver_location"]

    total_txns = len(df_geo)
    cross_border_count = int(df_geo["is_cross_border"].sum())
    domestic_count = total_txns - cross_border_count

    cross_border_laundering = int(
        df_geo[df_geo["is_cross_border"] & (df_geo["is_laundering"] == 1)].shape[0]
    )

    # ── Top corridors ─────────────────────────────────────────────────────
    df_cb = df_geo[df_geo["is_cross_border"]].copy()
    df_cb["corridor"] = df_cb["sender_location"] + " → " + df_cb["receiver_location"]

    corridor_stats = (
        df_cb.groupby("corridor")
        .agg(
            count=("amount", "count"),
            total_volume=("amount", "sum"),
            avg_amount=("amount", "mean"),
            laundering_count=("is_laundering", "sum"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
        .head(15)
    )

    corridor_results: List[Dict[str, Any]] = []
    for _, row in corridor_stats.iterrows():
        cnt = int(row["count"])
        laund = int(row["laundering_count"])
        laund_ratio = laund / cnt if cnt > 0 else 0.0
        risk_level = "HIGH" if laund_ratio > 0.005 else ("MEDIUM" if laund_ratio > 0.001 else "LOW")
        corridor_results.append({
            "corridor": str(row["corridor"]),
            "transaction_count": cnt,
            "total_volume_usd": round(float(row["total_volume"]), 2),
            "average_amount_usd": round(float(row["avg_amount"]), 2),
            "laundering_count": laund,
            "laundering_ratio": round(laund_ratio, 6),
            "risk_level": risk_level,
        })

    # ── Country-level risk ─────────────────────────────────────────────────
    sender_stats = (
        df_geo.groupby("sender_location")
        .agg(
            outbound_count=("amount", "count"),
            outbound_volume=("amount", "sum"),
            outbound_laundering=("is_laundering", "sum"),
        )
        .reset_index()
        .rename(columns={"sender_location": "country"})
    )

    receiver_stats = (
        df_geo.groupby("receiver_location")
        .agg(
            inbound_count=("amount", "count"),
            inbound_volume=("amount", "sum"),
            inbound_laundering=("is_laundering", "sum"),
        )
        .reset_index()
        .rename(columns={"receiver_location": "country"})
    )

    country_df = pd.merge(sender_stats, receiver_stats, on="country", how="outer").fillna(0)
    country_df["total_laundering"] = country_df["outbound_laundering"] + country_df["inbound_laundering"]
    country_df["total_volume"] = country_df["outbound_volume"] + country_df["inbound_volume"]
    country_df = country_df.sort_values("total_laundering", ascending=False).head(15)

    country_results: List[Dict[str, Any]] = []
    for _, row in country_df.iterrows():
        total_laund = int(row["total_laundering"])
        total_vol = float(row["total_volume"])
        country_results.append({
            "country": str(row["country"]),
            "outbound_transactions": int(row["outbound_count"]),
            "inbound_transactions": int(row["inbound_count"]),
            "total_volume_usd": round(total_vol, 2),
            "total_laundering_transactions": total_laund,
            "risk_level": "HIGH" if total_laund > 50 else ("MEDIUM" if total_laund > 10 else "LOW"),
        })

    result = {
        "tool": "Geo_Risk_Analyzer",
        "dataset_format": dataset_fmt,
        "has_geo_data": True,
        "summary": {
            "total_transactions": total_txns,
            "cross_border_transactions": cross_border_count,
            "domestic_transactions": domestic_count,
            "cross_border_pct": round(cross_border_count / total_txns * 100, 2) if total_txns > 0 else 0,
            "cross_border_laundering_count": cross_border_laundering,
            "unique_countries": int(
                df_geo["sender_location"].nunique() + df_geo["receiver_location"].nunique()
            ),
        },
        "top_corridors": corridor_results,
        "country_risk_summary": country_results,
    }

    logger.info(
        "Geo analysis complete: %d cross-border, %d corridors analysed",
        cross_border_count, len(corridor_results),
    )
    return json.dumps(result, indent=2, default=str)
