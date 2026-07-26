import json
from src.utils import classify_risk, get_logger

logger = get_logger(__name__)

def risk_classification_tool(anomaly_results: dict, graph_results: dict | None = None) -> str:
    """
    Standalone Risk Classification Tool.
    Takes anomaly detection output and optionally graph analysis output.
    """
    logger.info("Running risk classification...")
    
    if isinstance(anomaly_results, str):
        try:
            anomaly_results = json.loads(anomaly_results)
        except:
            anomaly_results = {}
            
    if isinstance(graph_results, str):
        try:
            graph_results = json.loads(graph_results)
        except:
            graph_results = {}
            
    flagged = anomaly_results.get('flagged_accounts', [])
    graph_data = graph_results if graph_results else {}
    
    classified_accounts = []
    distribution = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    escalation = {'immediate_sar': 0, 'enhanced_monitoring': 0, 'standard_monitoring': 0}
    
    for account_data in flagged:
        account = account_data['account']
        base_score = account_data.get('risk_score', 0)
        risk_factors = account_data.get('risk_factors', [])
        
        graph_adj = 0
        rule_adj = 0
        
        acc_graph = graph_data.get(account, {})
        if acc_graph.get('in_cycle', False):
            graph_adj += 20
            risk_factors.append("Involved in cycle/ring")
        if acc_graph.get('fan_in_pattern', False):
            graph_adj += 15
            risk_factors.append("Fan-in pattern detected")
        if acc_graph.get('betweenness_centrality', 0) > 0.1:
            graph_adj += 10
            risk_factors.append("High betweenness centrality")
            
        if account_data.get('total_outflow', 0) > 1000000:
            rule_adj += 10
            risk_factors.append("Total outflow > $1M")
        if account_data.get('cross_border_ratio', 0) > 0.5:
            rule_adj += 10
            risk_factors.append("High cross-border volume")
        if account_data.get('night_transaction_ratio', 0) > 0.4:
            rule_adj += 5
            risk_factors.append("High night transaction ratio")
            
        final_score = min(100, max(0, base_score + graph_adj + rule_adj))
        risk_level = classify_risk(final_score)
        
        if risk_level == 'HIGH':
            rec_action = 'immediate_sar'
        elif risk_level == 'MEDIUM':
            rec_action = 'enhanced_monitoring'
        else:
            rec_action = 'standard_monitoring'
            
        distribution[risk_level] += 1
        escalation[rec_action] += 1
        
        classified_accounts.append({
            'account': account,
            'base_score': base_score,
            'graph_adjustment': graph_adj,
            'rule_adjustment': rule_adj,
            'final_score': final_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'recommended_action': rec_action
        })
        
    out_dict = {
        'status': 'SUCCESS',
        'total_classified': len(classified_accounts),
        'risk_distribution': distribution,
        'classified_accounts': classified_accounts,
        'escalation_summary': escalation
    }
    
    return json.dumps(out_dict)
