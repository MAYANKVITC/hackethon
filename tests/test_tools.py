"""
tests/test_tools.py — Unit and integration tests for AEGIS AML Agent tools.
"""

import json
import os
import unittest
from pathlib import Path

import networkx as nx
import pandas as pd

from src.agent import (
    apply_date_filter,
    create_aml_agent,
    parse_query_intent,
    run_agent_query,
)
from src.anomaly_detection import anomaly_detection_tool
from src.explanation_engine import (
    generate_execution_summary,
    generate_explanation,
)
from src.feature_engineering import feature_engineering_tool
from src.graph_engine import (
    detect_cycles_tool,
    detect_smurfing_tool,
    eda_tool,
    load_aml_data,
    single_entity_lookup,
)
from src.metrics import MetricsCollector
from src.risk_classifier import risk_classification_tool
from src.utils import classify_risk, generate_sample_dataset


class TestAEGISAMLSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up test environment and dataset."""
        cls.sample_path = "data/sample_transactions.csv"
        if not Path(cls.sample_path).exists():
            generate_sample_dataset(cls.sample_path, n_transactions=500, seed=42)
        
        cls.df, cls.G, cls.fmt = load_aml_data(cls.sample_path)

    def test_sample_dataset_loading(self):
        """Verify sample dataset loads into DataFrame and NetworkX graph."""
        self.assertIsNotNone(self.df)
        self.assertIsNotNone(self.G)
        self.assertGreater(len(self.df), 0)
        self.assertGreater(self.G.number_of_nodes(), 0)

    def test_intent_parsing(self):
        """Test query intent parsing and filter extraction."""
        q1 = "Find structuring patterns in the last 30 days"
        intent1 = parse_query_intent(q1)
        self.assertEqual(intent1["intent_type"], "pattern_detection")
        self.assertEqual(intent1["pattern_type"], "structuring")
        self.assertIsNotNone(intent1["date_range"])

        q2 = "Which customers made 10+ transactions under $10,000?"
        intent2 = parse_query_intent(q2)
        self.assertIsNotNone(intent2["amount_filter"])
        self.assertEqual(intent2["amount_filter"]["type"], "under")
        self.assertEqual(intent2["amount_filter"]["value"], 10000.0)

        q3 = "Is account 8001 suspicious?"
        intent3 = parse_query_intent(q3)
        self.assertEqual(intent3["intent_type"], "entity_lookup")
        self.assertEqual(intent3["entity_id"], "8001")

    def test_eda_tool(self):
        """Test EDA tool functionality and output schema."""
        res_str = eda_tool(self.df)
        res = json.loads(res_str)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("summary", res)
        self.assertIn("total_transactions", res["summary"])

    def test_smurfing_detector_tool(self):
        """Test Smurfing/Structuring detection tool."""
        res_str = detect_smurfing_tool(self.G, min_fan_in=3, amount_cap=10000.0)
        res = json.loads(res_str)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("flagged_accounts", res)

    def test_cycle_detector_tool(self):
        """Test circular layering detection tool."""
        res_str = detect_cycles_tool(self.G, min_length=3, max_length=5)
        res = json.loads(res_str)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("detected_cycles", res)

    def test_single_entity_lookup_tool(self):
        """Test single entity lookup tool."""
        node = list(self.G.nodes())[0] if self.G.nodes() else "8001"
        res_str = single_entity_lookup(self.G, self.df, str(node))
        res = json.loads(res_str)
        self.assertIn(res.get("status"), ["FOUND", "NOT_FOUND"])

    def test_feature_engineering_tool(self):
        """Test Feature Engineering tool."""
        res_str = feature_engineering_tool(self.df)
        res = json.loads(res_str)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertGreater(res.get("feature_count", 0), 0)

    def test_anomaly_detection_tool(self):
        """Test ML + Statistical Anomaly Detection tool."""
        res_str = anomaly_detection_tool(self.df, self.G, method="hybrid")
        res = json.loads(res_str)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("flagged_accounts", res)

    def test_risk_classification_tool(self):
        """Test standalone Risk Classifier tool."""
        anomaly_res = json.loads(anomaly_detection_tool(self.df, self.G, method="hybrid"))
        res_str = risk_classification_tool(anomaly_res)
        res = json.loads(res_str)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("risk_distribution", res)

    def test_explanation_engine(self):
        """Test Explanation Engine narratives and summaries."""
        risk_data = {
            "risk_score": 85,
            "risk_level": "HIGH",
            "risk_factors": ["High transaction frequency", "Fan-in structuring"],
        }
        exp_str = generate_explanation("8001", risk_data, "Structuring query")
        exp = json.loads(exp_str)
        self.assertEqual(exp.get("status"), "SUCCESS")
        self.assertIn("narrative", exp)

        summary_str = generate_execution_summary(
            "Test query",
            {"intent_type": "pattern_detection"},
            ["Feature_Engineer", "Smurfing_Detector"],
            {"tool_count": 2},
        )
        summary = json.loads(summary_str)
        self.assertEqual(summary.get("status"), "SUCCESS")

    def test_agent_fallback_execution(self):
        """Test AML Agent in local rule-based fallback mode."""
        agent = create_aml_agent(self.df, self.G, api_key="", model_name="gpt-4o-mini")
        res = run_agent_query(agent, "Find structuring patterns in the last 30 days")
        self.assertIn("output", res)
        self.assertIn("tools_used", res)
        self.assertIn("Smurfing_Detector", res["tools_used"])

    def test_metrics_collector(self):
        """Test MetricsCollector and cost savings calculation."""
        mc = MetricsCollector()
        mc.log_query("Find structuring", ["Smurfing_Detector"])
        mc.log_alert("8001", 85, "HIGH")
        report = mc.get_efficiency_report()
        self.assertIn("queries_processed", report)
        savings = mc.estimate_cost_savings(total_transactions=len(self.df))
        self.assertIn("projected_annual_cost_saved", savings)


if __name__ == "__main__":
    unittest.main()
