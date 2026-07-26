"""
utils.py — Helper utilities for the AML Agent system.

Provides logging formatters, risk badge generation, color maps,
shared constants, dataset registry, and laundering typology metadata
used across the application.
"""

from __future__ import annotations

import csv
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# ─── Logging Configuration ───────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a consistently formatted logger.

    Args:
        name: Logger name (typically __name__ of the calling module).
        level: Logging level threshold.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ─── Risk Score Utilities ────────────────────────────────────────────────────

RISK_THRESHOLDS = {
    "HIGH": 75,
    "MEDIUM": 50,
    "LOW": 0,
}

RISK_COLORS = {
    "HIGH": "#FF4B4B",
    "MEDIUM": "#FFA500",
    "LOW": "#4CAF50",
}

RISK_BADGE_CSS = {
    "HIGH": (
        "background: linear-gradient(135deg, #FF4B4B, #CC0000);"
        "color: white; padding: 4px 12px; border-radius: 12px;"
        "font-weight: 700; font-size: 0.85em;"
    ),
    "MEDIUM": (
        "background: linear-gradient(135deg, #FFA500, #CC8400);"
        "color: white; padding: 4px 12px; border-radius: 12px;"
        "font-weight: 700; font-size: 0.85em;"
    ),
    "LOW": (
        "background: linear-gradient(135deg, #4CAF50, #2E7D32);"
        "color: white; padding: 4px 12px; border-radius: 12px;"
        "font-weight: 700; font-size: 0.85em;"
    ),
}


def classify_risk(score: float) -> str:
    """Classify a numeric risk score (0-100) into a risk level.

    Args:
        score: Numeric risk score between 0 and 100.

    Returns:
        Risk level string: 'HIGH', 'MEDIUM', or 'LOW'.
    """
    if score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif score >= RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def risk_badge_html(level: str) -> str:
    """Generate an HTML badge for the given risk level.

    Args:
        level: Risk level string ('HIGH', 'MEDIUM', 'LOW').

    Returns:
        HTML span element with styled risk badge.
    """
    style = RISK_BADGE_CSS.get(level, RISK_BADGE_CSS["LOW"])
    return f'<span style="{style}">{level}</span>'


# ─── Formatting Helpers ──────────────────────────────────────────────────────


def format_currency(value: float) -> str:
    """Format a float as USD currency string.

    Args:
        value: Numeric dollar amount.

    Returns:
        Formatted string like '$1,234.56'.
    """
    return f"${value:,.2f}"


def format_number(value: int | float) -> str:
    """Format a number with comma separators.

    Args:
        value: Numeric value.

    Returns:
        Formatted string like '1,234,567'.
    """
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}"


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: Input string.
        max_length: Maximum character count before truncation.

    Returns:
        Truncated string with '...' appended if needed.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


# ─── Execution Log Entry ─────────────────────────────────────────────────────


def create_execution_log_entry(
    step: int,
    tool_name: str,
    status: str,
    detail: str = "",
) -> Dict[str, Any]:
    """Create a structured execution log entry.

    Args:
        step: Step number in the execution sequence.
        tool_name: Name of the tool invoked.
        status: Execution status ('SUCCESS', 'ERROR', 'SKIPPED').
        detail: Additional detail or error message.

    Returns:
        Dictionary with log entry fields.
    """
    return {
        "step": step,
        "tool": tool_name,
        "status": status,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    }


# ─── Graph Visualization Colors ──────────────────────────────────────────────

NODE_COLORS = {
    "target": "#FF4B4B",       # Red — flagged / suspicious target
    "source": "#4A90D9",       # Blue — source accounts
    "cycle": "#FF6B35",        # Orange — part of a cycle
    "default": "#A0A0A0",      # Gray — neutral
    "highlight": "#FFD700",    # Gold — entity lookup focus
}

EDGE_COLORS = {
    "suspicious": "#FF4B4B",
    "normal": "#CCCCCC",
    "cycle": "#FF6B35",
    "smurfing": "#4A90D9",
    "cross_border": "#9C27B0",
}


# ─── Laundering Typology Colors ──────────────────────────────────────────────
# Maps both SAML-D typology labels and IBM Patterns.txt categories to colors

TYPOLOGY_COLORS: Dict[str, str] = {
    # SAML-D categories
    "Smurfing":              "#FF4B4B",
    "Structuring":           "#FF6B35",
    "Fan_In":                "#4A90D9",
    "Fan_Out":               "#9C27B0",
    "Cycle":                 "#FFD700",
    "Bipartite":             "#4CAF50",
    "Scatter-Gather":        "#FF8C00",
    "Gather-Scatter":        "#00BCD4",
    "Layered_Fan_In":        "#E91E63",
    "Layered_Fan_Out":       "#673AB7",
    "Stacked_Bipartite":     "#2196F3",
    "Stacked Bipartite":     "#2196F3",
    "Over-Invoicing":        "#F44336",
    "Single_large":          "#FF5722",
    "Cash_Withdrawal":       "#795548",
    "Deposit-Send":          "#607D8B",
    "Behavioural_Change_1":  "#8BC34A",
    "Behavioural_Change_2":  "#CDDC39",
    # IBM Patterns categories
    "FAN-IN":                "#4A90D9",
    "FAN-OUT":               "#9C27B0",
    "CYCLE":                 "#FFD700",
    "BIPARTITE":             "#4CAF50",
    "GATHER-SCATTER":        "#00BCD4",
    "SCATTER-GATHER":        "#FF8C00",
    "STACK":                 "#E91E63",
    "RANDOM":                "#607D8B",
    # Normal / fallback
    "Normal":                "#78909C",
}

TYPOLOGY_RISK_MAP: Dict[str, str] = {
    "Smurfing":              "HIGH",
    "Structuring":           "HIGH",
    "Cycle":                 "HIGH",
    "Layered_Fan_In":        "HIGH",
    "Layered_Fan_Out":       "HIGH",
    "Stacked_Bipartite":     "HIGH",
    "Stacked Bipartite":     "HIGH",
    "Over-Invoicing":        "HIGH",
    "Bipartite":             "MEDIUM",
    "Fan_In":                "MEDIUM",
    "Fan_Out":               "MEDIUM",
    "Scatter-Gather":        "MEDIUM",
    "Gather-Scatter":        "MEDIUM",
    "Single_large":          "MEDIUM",
    "Cash_Withdrawal":       "LOW",
    "Deposit-Send":          "LOW",
    "Behavioural_Change_1":  "MEDIUM",
    "Behavioural_Change_2":  "MEDIUM",
    # IBM
    "FAN-IN":                "MEDIUM",
    "FAN-OUT":               "MEDIUM",
    "CYCLE":                 "HIGH",
    "BIPARTITE":             "MEDIUM",
    "GATHER-SCATTER":        "MEDIUM",
    "SCATTER-GATHER":        "MEDIUM",
    "STACK":                 "HIGH",
    "RANDOM":                "LOW",
}

TYPOLOGY_DESCRIPTIONS: Dict[str, str] = {
    "Smurfing":
        "Breaking large sums into many small deposits to evade reporting thresholds.",
    "Structuring":
        "Deliberately structuring transactions to avoid regulatory detection limits.",
    "Fan_In":
        "Multiple accounts funneling money into a single destination account.",
    "Fan_Out":
        "Single account distributing funds to many destination accounts.",
    "Cycle":
        "Circular money flows (A→B→C→A) to obscure the audit trail.",
    "Bipartite":
        "Two groups of accounts trading funds back and forth to layer money.",
    "Scatter-Gather":
        "Funds scattered across many accounts then aggregated into one.",
    "Gather-Scatter":
        "Funds aggregated first, then scattered to many final destinations.",
    "Layered_Fan_In":
        "Multi-hop fan-in pattern with intermediate layering accounts.",
    "Layered_Fan_Out":
        "Multi-hop fan-out pattern with intermediate layering accounts.",
    "Stacked Bipartite":
        "Multiple bipartite layers stacked to further obscure money flows.",
    "Stacked_Bipartite":
        "Multiple bipartite layers stacked to further obscure money flows.",
    "Over-Invoicing":
        "Inflating invoice amounts to justify large cross-border transfers.",
    "Single_large":
        "Single large transaction designed to appear legitimate.",
    "Cash_Withdrawal":
        "Suspicious pattern of cash withdrawals to introduce untraceable funds.",
    "Deposit-Send":
        "Cash deposited then immediately forwarded elsewhere.",
    "Behavioural_Change_1":
        "Sudden change in transaction behaviour deviating from historical norms.",
    "Behavioural_Change_2":
        "Secondary behavioural anomaly pattern with different timing characteristics.",
    # IBM
    "FAN-IN":   "Multiple sources sending to one target (aggregation).",
    "FAN-OUT":  "One source distributing to multiple targets.",
    "CYCLE":    "Directed cycle — money flows back to origin.",
    "BIPARTITE":"Two-group alternating transaction pattern.",
    "GATHER-SCATTER": "Gather then scatter across multiple hops.",
    "SCATTER-GATHER": "Scatter then gather across multiple hops.",
    "STACK":    "Stacked/layered transaction chains.",
    "RANDOM":   "Random transaction pattern used as noise cover.",
}


# ─── Dataset Registry ─────────────────────────────────────────────────────────

DATASET_FORMAT_IBM = "ibm"
DATASET_FORMAT_SAML = "saml"

DATASET_FORMATS: List[str] = [DATASET_FORMAT_IBM, DATASET_FORMAT_SAML]

# Registry of all available datasets: name → metadata dict
AVAILABLE_DATASETS: List[Dict[str, Any]] = [
    {
        "name": "Built-in Sample (Demo)",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "data/sample_transactions.csv",
        "accounts_path": None,
        "patterns_path": None,
        "size_label": "~2,000 transactions",
        "intensity": "Mixed (Demo)",
        "description": "Built-in sample dataset with injected AML patterns for demonstration.",
    },
    {
        "name": "IBM HI-Small (Default)",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "archive (2)/HI-Small_Trans.csv",
        "accounts_path": "archive (2)/HI-Small_accounts.csv",
        "patterns_path": "archive (2)/HI-Small_Patterns.txt",
        "size_label": "~5M transactions",
        "intensity": "High Intensity",
        "description": "IBM Synthetic AML — High Laundering Intensity, Small dataset.",
    },
    {
        "name": "IBM HI-Medium",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "archive (2)/HI-Medium_Trans.csv",
        "accounts_path": "archive (2)/HI-Medium_accounts.csv",
        "patterns_path": "archive (2)/HI-Medium_Patterns.txt",
        "size_label": "~medium",
        "intensity": "High Intensity",
        "description": "IBM Synthetic AML — High Laundering Intensity, Medium dataset.",
    },
    {
        "name": "IBM HI-Large",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "archive (2)/HI-Large_Trans.csv",
        "accounts_path": None,
        "patterns_path": "archive (2)/HI-Large_Patterns.txt",
        "size_label": "~large",
        "intensity": "High Intensity",
        "description": "IBM Synthetic AML — High Laundering Intensity, Large dataset.",
    },
    {
        "name": "IBM LI-Small",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "archive (2)/LI-Small_Trans.csv",
        "accounts_path": "archive (2)/LI-Small_accounts.csv",
        "patterns_path": "archive (2)/LI-Small_Patterns.txt",
        "size_label": "~small",
        "intensity": "Low Intensity",
        "description": "IBM Synthetic AML — Low Laundering Intensity, Small dataset.",
    },
    {
        "name": "IBM LI-Medium",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "archive (2)/LI-Medium_Trans.csv",
        "accounts_path": "archive (2)/LI-Medium_accounts.csv",
        "patterns_path": "archive (2)/LI-Medium_Patterns.txt",
        "size_label": "~medium",
        "intensity": "Low Intensity",
        "description": "IBM Synthetic AML — Low Laundering Intensity, Medium dataset.",
    },
    {
        "name": "IBM LI-Large",
        "format": DATASET_FORMAT_IBM,
        "trans_path": "archive (2)/LI-Large_Trans.csv",
        "accounts_path": "archive (2)/LI-Large_accounts.csv",
        "patterns_path": "archive (2)/LI-Large_Patterns.txt",
        "size_label": "~large",
        "intensity": "Low Intensity",
        "description": "IBM Synthetic AML — Low Laundering Intensity, Large dataset.",
    },
    {
        "name": "SAML-D (UK — Rich Typologies)",
        "format": DATASET_FORMAT_SAML,
        "trans_path": "data/SAML-D.csv",
        "accounts_path": None,
        "patterns_path": None,
        "size_label": "~9.5M transactions",
        "intensity": "Mixed",
        "description": (
            "Synthetic AML Dataset (UK-origin). Rich schema with 17 explicit "
            "laundering typology labels, multi-currency, and cross-border geo data."
        ),
    },
]

# Lookup by display name
DATASET_BY_NAME: Dict[str, Dict[str, Any]] = {d["name"]: d for d in AVAILABLE_DATASETS}

DEFAULT_DATASETS: Dict[str, str] = {
    d["name"]: d["trans_path"] for d in AVAILABLE_DATASETS
}

LAUNDERING_TYPOLOGY_COLORS: Dict[str, str] = TYPOLOGY_COLORS

# ─── Sample Queries ──────────────────────────────────────────────────────────

SAMPLE_QUERIES: List[Dict[str, str]] = [
    {
        "label": "📊 Data Overview",
        "query": "Run exploratory data analysis on the baseline transactions.",
    },
    {
        "label": "🕵️ Smurfing Detection",
        "query": "Detect structuring or smurfing patterns with transactions under $10,000.",
    },
    {
        "label": "🔄 Circular Layering",
        "query": "Find circular money loops indicating layering networks.",
    },
    {
        "label": "🗺️ Typology Breakdown",
        "query": "Show a breakdown of all laundering typologies and their risk levels in this dataset.",
    },
    {
        "label": "🌍 Geo Risk Analysis",
        "query": "Analyse cross-border transaction flows and identify high-risk geographic corridors.",
    },
    {
        "label": "🔍 Entity Lookup",
        "query": "Check if account 8000EBD30 is suspicious.",
    },
]


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_CSV_PATH = "data/sample_transactions.csv"
DEFAULT_DATASET_NAME = "IBM HI-Small (Default)"
APP_TITLE = "🛡️ AI-Powered AML Agent"
APP_SUBTITLE = "Suspicious Activity Detection & Anti-Money Laundering — Multi-Dataset Edition"

# Maximum rows to sample for heavy operations (Medium/Large datasets)
GRAPH_SAMPLE_LIMIT = 2_000_000

# Country → ISO alpha-3 mapping for geo charts (common locations in datasets)
COUNTRY_ISO3: Dict[str, str] = {
    "UK": "GBR",
    "UAE": "ARE",
    "US": "USA",
    "Germany": "DEU",
    "France": "FRA",
    "China": "CHN",
    "Japan": "JPN",
    "Australia": "AUS",
    "Canada": "CAN",
    "India": "IND",
    "Brazil": "BRA",
    "Mexico": "MEX",
    "Russia": "RUS",
    "Nigeria": "NGA",
    "Switzerland": "CHE",
    "Luxembourg": "LUX",
    "Cayman Islands": "CYM",
    "British Virgin Islands": "VGB",
    "Panama": "PAN",
    "Singapore": "SGP",
    "Hong Kong": "HKG",
}


# ─── Sample Dataset Generator ────────────────────────────────────────────────


def generate_sample_dataset(
    output_path: str = "data/sample_transactions.csv",
    n_transactions: int = 2000,
    seed: int = 42,
) -> str:
    """Generate a realistic AML sample CSV file with injected laundering patterns.

    Creates transactions matching the IBM synthetic format with columns:
    Timestamp, From Bank, Account, To Bank, Account.1,
    Amount Received, Receiving Currency, Amount Paid, Payment Currency,
    Payment Format, Is Laundering.

    Injected patterns:
        - ~5 % structuring / smurfing (many small txns under $10 k to same receiver)
        - ~3 % cycle patterns (A → B → C → A)
        - ~2 % fan-out patterns (one source → many destinations)
        - ~90 % normal transactions

    Args:
        output_path: File path for the generated CSV.
        n_transactions: Approximate number of rows to produce.
        seed: Random seed for reproducibility.

    Returns:
        The absolute path to the generated CSV file.
    """
    rng = random.Random(seed)

    banks = [
        "First National", "HSBC", "Deutsche Bank", "JPMorgan",
        "Barclays", "Wells Fargo", "Citibank", "UBS",
        "BNP Paribas", "Standard Chartered",
    ]
    currencies = ["USD", "EUR", "GBP", "CHF", "JPY"]
    payment_formats = ["Wire", "ACH", "SWIFT", "Check", "Crypto"]

    def _rand_account() -> str:
        return f"{rng.randint(1000, 9999):04X}{rng.randint(0, 0xFFFFF):05X}"

    base_time = datetime(2024, 1, 1)
    rows: List[List[Any]] = []

    # Pre-generate some fixed accounts for pattern injection
    smurf_target = _rand_account()
    smurf_target_bank = rng.choice(banks)

    cycle_accounts = [_rand_account() for _ in range(5)]
    cycle_banks = [rng.choice(banks) for _ in range(5)]

    fan_source = _rand_account()
    fan_source_bank = rng.choice(banks)
    fan_destinations = [(_rand_account(), rng.choice(banks)) for _ in range(8)]

    # Counts per category
    n_smurf = int(n_transactions * 0.05)
    n_cycle = int(n_transactions * 0.03)
    n_fanout = int(n_transactions * 0.02)
    n_normal = n_transactions - n_smurf - n_cycle - n_fanout

    def _ts() -> str:
        offset = timedelta(seconds=rng.randint(0, 365 * 24 * 3600))
        return (base_time + offset).strftime("%Y/%m/%d %H:%M")

    # --- Normal transactions (~90 %) ---
    for _ in range(n_normal):
        amt = round(rng.uniform(50, 500_000), 2)
        cur = rng.choice(currencies)
        rows.append([
            _ts(), rng.choice(banks), _rand_account(),
            rng.choice(banks), _rand_account(),
            amt, cur, amt, cur,
            rng.choice(payment_formats), 0,
        ])

    # --- Structuring / Smurfing (~5 %) ---
    smurf_senders = [(_rand_account(), rng.choice(banks)) for _ in range(10)]
    for i in range(n_smurf):
        sender_acct, sender_bank = smurf_senders[i % len(smurf_senders)]
        amt = round(rng.uniform(1_000, 9_500), 2)  # under $10 k
        cur = "USD"
        rows.append([
            _ts(), sender_bank, sender_acct,
            smurf_target_bank, smurf_target,
            amt, cur, amt, cur,
            rng.choice(["ACH", "Wire"]), 1,
        ])

    # --- Cycle patterns (~3 %) --- A→B→C→D→E→A
    per_cycle_leg = max(1, n_cycle // len(cycle_accounts))
    for leg in range(len(cycle_accounts)):
        src_idx = leg
        dst_idx = (leg + 1) % len(cycle_accounts)
        for _ in range(per_cycle_leg):
            amt = round(rng.uniform(10_000, 100_000), 2)
            cur = rng.choice(["USD", "EUR"])
            rows.append([
                _ts(), cycle_banks[src_idx], cycle_accounts[src_idx],
                cycle_banks[dst_idx], cycle_accounts[dst_idx],
                amt, cur, amt, cur,
                "SWIFT", 1,
            ])

    # --- Fan-out patterns (~2 %) ---
    per_dest = max(1, n_fanout // len(fan_destinations))
    for dest_acct, dest_bank in fan_destinations:
        for _ in range(per_dest):
            amt = round(rng.uniform(5_000, 50_000), 2)
            cur = rng.choice(currencies)
            rows.append([
                _ts(), fan_source_bank, fan_source,
                dest_bank, dest_acct,
                amt, cur, amt, cur,
                rng.choice(payment_formats), 1,
            ])

    # Shuffle so patterns are interleaved
    rng.shuffle(rows)

    # Write CSV
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    header = [
        "Timestamp", "From Bank", "Account", "To Bank", "Account.1",
        "Amount Received", "Receiving Currency", "Amount Paid",
        "Payment Currency", "Payment Format", "Is Laundering",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)

    return os.path.abspath(output_path)
