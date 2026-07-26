import json
from src.utils import format_currency, get_logger

logger = get_logger(__name__)

def generate_explanation(account_id: str, risk_data: dict, query_context: str = '') -> str:
    """
    Generate a human-readable explanation for why an account is flagged.
    """
    logger.info(f"Generating explanation for account: {account_id}")
    
    if isinstance(risk_data, str):
        try:
            risk_data = json.loads(risk_data)
        except:
            risk_data = {}
            
    risk_score = risk_data.get('final_score', risk_data.get('risk_score', 0))
    risk_level = risk_data.get('risk_level', 'UNKNOWN')
    factors = risk_data.get('risk_factors', [])
    rec_action = risk_data.get('recommended_action', 'standard_monitoring')
    
    narrative_parts = []
    if query_context:
        narrative_parts.append(f"In response to your query regarding '{query_context}', we analyzed account {account_id}.")
    else:
        narrative_parts.append(f"Analysis complete for account {account_id}.")
        
    narrative_parts.append(f"This account has been classified as {risk_level} risk with a score of {risk_score:.1f}/100.")
    
    if factors:
        narrative_parts.append("The primary risk factors identified include: " + ", ".join(factors) + ".")
    else:
        narrative_parts.append("No specific anomalous risk factors were identified.")
        
    narrative_parts.append(f"Recommended action is {rec_action.replace('_', ' ')} based on the aggregated risk profile.")
    
    action_justification = "The risk score exceeds standard thresholds, necessitating this action."
    if risk_level == 'HIGH':
        action_justification = "Immediate SAR filing is recommended due to severe risk indicators suggesting potential illicit activity."
        
    out_dict = {
        'status': 'SUCCESS',
        'account_id': account_id,
        'risk_level': risk_level,
        'risk_score': risk_score,
        'narrative': " ".join(narrative_parts),
        'key_findings': factors,
        'recommended_action': rec_action,
        'action_justification': action_justification,
        'query_relevance': query_context if query_context else "General analysis"
    }
    
    return json.dumps(out_dict)

def generate_batch_explanation(flagged_accounts: list[dict], query_context: str = '') -> str:
    """
    Generate explanations for multiple accounts.
    """
    logger.info("Generating batch explanations...")
    explanations = []
    
    for account_data in flagged_accounts:
        acc_id = account_data.get('account', 'UNKNOWN')
        exp_str = generate_explanation(acc_id, account_data, query_context)
        explanations.append(json.loads(exp_str))
        
    return json.dumps({'status': 'SUCCESS', 'explanations': explanations})

def generate_execution_summary(query: str, intent: dict, tools_invoked: list[str], results_summary: dict) -> str:
    """
    Generate a query-aware execution summary.
    """
    logger.info("Generating execution summary...")
    
    flow = [f"1. Interpreted query intent as: {intent.get('primary_intent', 'general analysis')}"]
    for i, tool in enumerate(tools_invoked, 2):
        flow.append(f"{i}. Invoked {tool} to process data.")
        
    out_dict = {
        'status': 'SUCCESS',
        'user_query': query,
        'detected_intent': intent,
        'filters_applied': intent.get('filters', {}),
        'tools_invoked': tools_invoked,
        'execution_flow': flow,
        'results_overview': results_summary
    }
    
    return json.dumps(out_dict)
