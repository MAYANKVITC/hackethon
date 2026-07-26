import json
import pandas as pd
import numpy as np
import networkx as nx
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from src.utils import classify_risk, get_logger

logger = get_logger(__name__)

def anomaly_detection_tool(df: pd.DataFrame, G: nx.DiGraph, method: str = 'hybrid') -> str:
    """
    Hybrid ML + statistical anomaly detection module.
    """
    logger.info(f"Running anomaly detection using method: {method}")
    
    # 1. Extract features
    senders = df.groupby('sender_id')
    features = pd.DataFrame(index=df['sender_id'].unique())
    features['transaction_frequency'] = senders.size()
    features['avg_amount'] = senders['amount'].mean() if 'amount' in df.columns else 0
    features['amount_std'] = senders['amount'].std().fillna(0) if 'amount' in df.columns else 0
    
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    features['in_degree'] = features.index.map(lambda x: in_degrees.get(x, 0))
    features['out_degree'] = features.index.map(lambda x: out_degrees.get(x, 0))
    
    features = features.fillna(0)
    
    ml_scores = pd.Series(0, index=features.index, dtype=float)
    stat_scores = pd.Series(0, index=features.index, dtype=float)
    
    if method in ['ml', 'hybrid']:
        scaler = StandardScaler()
        scaled_feat = scaler.fit_transform(features)
        iso = IsolationForest(contamination=0.05, random_state=42)
        iso.fit(scaled_feat)
        scores = -iso.decision_function(scaled_feat)
        min_s, max_s = scores.min(), scores.max()
        ml_scores = pd.Series((scores - min_s) / (max_s - min_s + 1e-9) * 100, index=features.index)
        
    if method in ['statistical', 'hybrid']:
        z_scores = pd.DataFrame(index=features.index)
        for col in ['transaction_frequency', 'avg_amount', 'in_degree', 'out_degree']:
            mean_val = features[col].mean()
            std_val = features[col].std()
            if std_val > 0:
                z_scores[col] = (features[col] - mean_val) / std_val
            else:
                z_scores[col] = 0
                
        outlier_flags = pd.DataFrame(index=features.index)
        for col in ['transaction_frequency', 'avg_amount', 'in_degree', 'out_degree']:
            Q1 = features[col].quantile(0.25)
            Q3 = features[col].quantile(0.75)
            IQR = Q3 - Q1
            outlier_flags[col] = (features[col] > (Q3 + 1.5 * IQR)).astype(int)
            
        max_z = z_scores.abs().max(axis=1)
        min_z, max_z_val = max_z.min(), max_z.max()
        stat_scores = (max_z - min_z) / (max_z_val - min_z + 1e-9) * 100
        
    if method == 'hybrid':
        final_scores = 0.6 * ml_scores + 0.4 * stat_scores
    elif method == 'ml':
        final_scores = ml_scores
    else:
        final_scores = stat_scores
        
    flagged = []
    
    for account in features.index:
        r_score = float(final_scores.loc[account])
        risk_level = classify_risk(r_score)
        
        rf = []
        if ml_scores.loc[account] > 75: rf.append("High ML anomaly score")
        if stat_scores.loc[account] > 75: rf.append("Statistical outlier")
        if features.loc[account, 'transaction_frequency'] > features['transaction_frequency'].mean() + 2*features['transaction_frequency'].std():
            rf.append("Unusually high transaction frequency")
            
        if risk_level in ['HIGH', 'MEDIUM']:
            flagged.append({
                'account': account,
                'risk_score': r_score,
                'risk_level': risk_level,
                'ml_score': float(ml_scores.loc[account]),
                'statistical_score': float(stat_scores.loc[account]),
                'risk_factors': rf,
                'recommended_action': "Investigate immediately" if risk_level == 'HIGH' else "Enhanced monitoring"
            })
            
    flagged = sorted(flagged, key=lambda x: x['risk_score'], reverse=True)[:30]
    
    out_dict = {
        'status': 'SUCCESS',
        'method_used': method,
        'total_accounts_analyzed': len(features),
        'anomalies_detected': len(flagged),
        'anomaly_rate': float(len(flagged) / len(features) * 100) if len(features) > 0 else 0.0,
        'flagged_accounts': flagged,
        'model_parameters': {
            'contamination': 0.05,
            'random_state': 42,
            'method': method
        },
        'detection_summary': f"Detected {len(flagged)} anomalous accounts using {method} approach."
    }
    
    return json.dumps(out_dict)
