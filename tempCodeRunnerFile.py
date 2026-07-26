"""
agent1.py — Script to run AML Graph Engine functions directly in VS Code 
without invoking LangChain or OpenAI LLM API credits.
"""

from src.graph_engine import (
    load_aml_data,
    detect_smurfing_tool,
    detect_cycles_tool,
    eda_tool,
    single_entity_lookup,
)

def main():
    # 1. Set the path to your AML dataset CSV
    dataset_path = r"C:\Users\User\Desktop\cs\Hackathon\data\SAML-D.csv"  # <-- UPDATE THIS to your dataset path

    print("Loading transaction dataset and building graph...")
    # Load data into DataFrame (df) and NetworkX Graph (G)
    df, G, dataset_format, patterns_data = load_aml_data(dataset_path)

    print("\n" + "=" * 50)
    print("RUNNING SMURFING / STRUCTURING DETECTION (Under $10,000)")
    print("=" * 50)

    # 2. Call the smurfing detection function directly (0 API credits used)
    smurfing_results = detect_smurfing_tool(
        G, 
        min_fan_in=5,          # Minimum fan-in sources
        amount_cap=10000.0     # Cap amount at $10,000
    )

    print(smurfing_results)

    # -------------------------------------------------------------
    # Optional: Uncomment any of the lines below to run other tools!
    # -------------------------------------------------------------
    
    # --- Run EDA Summary ---
    # print(eda_tool(df))

    # --- Run Circular Flow / Cycle Detection ---
    # print(detect_cycles_tool(G, min_length=3, max_length=5))

    # --- Look up a Specific Account ID ---
    # print(single_entity_lookup(G, df, account_id="ACCOUNT_ID_HERE"))


if __name__ == "__main__":
    main()