"""
Generate a sample AML transaction dataset in IBM Synthetic AML format.

Produces exactly 2000 rows with:
- ~1800 normal transactions (Is Laundering=0)
- ~100 structuring/smurfing transactions (Is Laundering=1)
- ~60 cycle/layering transactions (Is Laundering=1)
- ~40 fan-out transactions (Is Laundering=1)

Uses seed=42 for reproducibility.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta


def generate_normal_transactions(
    rng: np.random.Generator, n: int
) -> pd.DataFrame:
    """Generate normal (non-laundering) transactions.

    Args:
        rng: NumPy random generator for reproducibility.
        n: Number of normal rows to generate.

    Returns:
        DataFrame of normal transactions with Is Laundering=0.
    """
    banks = ["Chase", "HSBC", "Citibank", "Barclays", "Deutsche", "BNP", "UBS", "Wells"]
    currencies = ["USD", "EUR", "GBP"]
    currency_weights = [0.70, 0.20, 0.10]
    formats_ = ["Wire", "ACH", "Cheque", "Credit Card", "Bitcoin", "Cash"]
    format_weights = [0.40, 0.30, 0.15, 0.10, 0.03, 0.02]

    # Timestamps: Jan 1 2024 – Mar 31 2024
    start = datetime(2024, 1, 1)
    end = datetime(2024, 3, 31, 23, 59)
    total_minutes = int((end - start).total_seconds() / 60)
    offsets = rng.integers(0, total_minutes, size=n)
    timestamps = [start + timedelta(minutes=int(o)) for o in offsets]

    from_banks = rng.choice(banks, size=n)
    to_banks = rng.choice(banks, size=n)
    accounts = rng.integers(1000, 10000, size=n).astype(str)
    accounts1 = rng.integers(1000, 10000, size=n).astype(str)

    # Amounts: normal dist, mean=5000, std=3000, clipped to [50, 50000]
    amounts = rng.normal(5000, 3000, size=n)
    amounts = np.clip(amounts, 50, 50000).round(2)

    pay_currencies = rng.choice(currencies, size=n, p=currency_weights)
    rec_currencies = pay_currencies.copy()  # same currency for normal txns
    payment_formats = rng.choice(formats_, size=n, p=format_weights)

    return pd.DataFrame({
        "Timestamp": [t.strftime("%Y/%m/%d %H:%M") for t in timestamps],
        "From Bank": from_banks,
        "Account": accounts,
        "To Bank": to_banks,
        "Account.1": accounts1,
        "Amount Received": amounts,
        "Receiving Currency": rec_currencies,
        "Amount Paid": amounts,
        "Payment Currency": pay_currencies,
        "Payment Format": payment_formats,
        "Is Laundering": 0,
    })


def generate_structuring_transactions(
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate structuring / smurfing pattern transactions.

    5 target receiver accounts each receive 15-25 small transactions
    from different senders, all under $10,000, clustered in 1-3 day windows.

    Returns:
        DataFrame of structuring transactions with Is Laundering=1.
    """
    banks = ["Chase", "HSBC", "Citibank", "Barclays", "Deutsche", "BNP", "UBS", "Wells"]
    target_accounts = ["8001", "8002", "8003", "8004", "8005"]
    formats_ = ["Cash", "ACH"]
    format_weights = [0.55, 0.45]

    rows: list[dict] = []
    for target in target_accounts:
        n_txns = rng.integers(15, 26)  # 15-25 transactions
        # Cluster start: random day in Jan-Mar 2024
        cluster_start = datetime(2024, 1, 15) + timedelta(days=int(rng.integers(0, 60)))
        cluster_span_minutes = int(rng.integers(1, 4)) * 24 * 60  # 1-3 days in minutes
        target_bank = rng.choice(banks)

        for _ in range(n_txns):
            offset = int(rng.integers(0, cluster_span_minutes))
            ts = cluster_start + timedelta(minutes=offset)
            amount = round(rng.uniform(2000, 9500), 2)
            sender_account = str(rng.integers(1000, 7000))
            sender_bank = rng.choice(banks)
            fmt = rng.choice(formats_, p=format_weights)

            rows.append({
                "Timestamp": ts.strftime("%Y/%m/%d %H:%M"),
                "From Bank": sender_bank,
                "Account": sender_account,
                "To Bank": target_bank,
                "Account.1": target,
                "Amount Received": amount,
                "Receiving Currency": "USD",
                "Amount Paid": amount,
                "Payment Currency": "USD",
                "Payment Format": fmt,
                "Is Laundering": 1,
            })

    return pd.DataFrame(rows)


def generate_cycle_transactions(
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate cycle / layering pattern transactions.

    4 cycles of accounts where money circulates in loops, each
    repeated 3-5 times with Wire transfers of $10,000-$50,000.

    Returns:
        DataFrame of cycle transactions with Is Laundering=1.
    """
    cycles = [
        ["7001", "7002", "7003"],                    # 3-node cycle
        ["7004", "7005", "7006", "7007"],             # 4-node cycle
        ["7008", "7009", "7010"],                     # 3-node cycle
        ["7011", "7012", "7013", "7014", "7015"],     # 5-node cycle
    ]
    banks = ["Chase", "HSBC", "Citibank", "Barclays", "Deutsche", "BNP", "UBS", "Wells"]

    rows: list[dict] = []
    for cycle in cycles:
        n_rounds = int(rng.integers(3, 6))  # 3-5 repetitions
        # Each cycle starts on a different date
        cycle_start = datetime(2024, 1, 10) + timedelta(days=int(rng.integers(0, 70)))
        # Assign a fixed bank to each account in the cycle
        account_banks = {acc: rng.choice(banks) for acc in cycle}

        for round_idx in range(n_rounds):
            for i in range(len(cycle)):
                sender = cycle[i]
                receiver = cycle[(i + 1) % len(cycle)]
                amount = round(rng.uniform(10000, 50000), 2)
                # Stagger within the round
                ts = cycle_start + timedelta(
                    days=round_idx * 2,
                    hours=int(rng.integers(0, 12)),
                    minutes=int(rng.integers(0, 60)),
                )
                rows.append({
                    "Timestamp": ts.strftime("%Y/%m/%d %H:%M"),
                    "From Bank": account_banks[sender],
                    "Account": sender,
                    "To Bank": account_banks[receiver],
                    "Account.1": receiver,
                    "Amount Received": amount,
                    "Receiving Currency": "USD",
                    "Amount Paid": amount,
                    "Payment Currency": "USD",
                    "Payment Format": "Wire",
                    "Is Laundering": 1,
                })

    return pd.DataFrame(rows)


def generate_fanout_transactions(
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate fan-out pattern transactions.

    2 source accounts each send to 15-20 different receivers
    in short time windows, amounts $5,000-$15,000.

    Returns:
        DataFrame of fan-out transactions with Is Laundering=1.
    """
    banks = ["Chase", "HSBC", "Citibank", "Barclays", "Deutsche", "BNP", "UBS", "Wells"]
    sources = [("9001", "Chase"), ("9002", "HSBC")]
    formats_ = ["Wire", "ACH", "Credit Card"]

    rows: list[dict] = []
    for src_account, src_bank in sources:
        n_receivers = int(rng.integers(15, 21))  # 15-20 receivers
        window_start = datetime(2024, 2, 1) + timedelta(days=int(rng.integers(0, 45)))
        window_minutes = 48 * 60  # 2-day window

        for _ in range(n_receivers):
            receiver = str(rng.integers(1000, 7000))
            recv_bank = rng.choice(banks)
            amount = round(rng.uniform(5000, 15000), 2)
            offset = int(rng.integers(0, window_minutes))
            ts = window_start + timedelta(minutes=offset)
            fmt = rng.choice(formats_)

            rows.append({
                "Timestamp": ts.strftime("%Y/%m/%d %H:%M"),
                "From Bank": src_bank,
                "Account": src_account,
                "To Bank": recv_bank,
                "Account.1": receiver,
                "Amount Received": amount,
                "Receiving Currency": "USD",
                "Amount Paid": amount,
                "Payment Currency": "USD",
                "Payment Format": fmt,
                "Is Laundering": 1,
            })

    return pd.DataFrame(rows)


def main() -> None:
    """Generate the full dataset, save to CSV, and print verification stats."""
    rng = np.random.default_rng(seed=42)

    # --- Generate each pattern ---
    df_struct = generate_structuring_transactions(rng)
    df_cycle = generate_cycle_transactions(rng)
    df_fanout = generate_fanout_transactions(rng)

    n_laundering = len(df_struct) + len(df_cycle) + len(df_fanout)
    n_normal = 2000 - n_laundering
    df_normal = generate_normal_transactions(rng, n_normal)

    # --- Combine and shuffle ---
    df = pd.concat([df_normal, df_struct, df_cycle, df_fanout], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # --- Save ---
    out_path = Path(__file__).parent / "sample_transactions.csv"
    df.to_csv(out_path, index=False)

    # --- Verify ---
    df_check = pd.read_csv(out_path)
    print(f"Total rows: {len(df_check)}")
    print(f"Columns: {list(df_check.columns)}")
    print(f"\nIs Laundering distribution:\n{df_check['Is Laundering'].value_counts().to_string()}")
    print(f"\nFirst 5 rows:\n{df_check.head().to_string()}")


if __name__ == "__main__":
    main()
