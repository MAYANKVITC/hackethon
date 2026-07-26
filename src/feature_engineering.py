import json
import pandas as pd
import numpy as np
from src.utils import get_logger

logger = get_logger(__name__)

def feature_engineering_tool(df: pd.DataFrame, features: list[str] | None = None) -> str:
    """
    Feature Engineering Tool for AML analysis.
    Creates AML-specific features from transaction data.
    """
    logger.info("Starting feature engineering...")
    df = df.copy()
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    computed_features = []
    
    if features is None:
        features = [
            'transaction_frequency', 'avg_transaction_amount', 'amount_std_deviation',
            'rolling_sum_7d', 'velocity', 'amount_deviation_from_mean', 'rapid_cashout_flag',
            'round_amount_ratio', 'night_transaction_ratio', 'counterparty_concentration',
            'max_single_transaction', 'dormancy_reactivation'
        ]
        
    sender_groups = df.groupby('sender_id')
    
    # We will build a feature dataframe for senders
    senders = pd.DataFrame(index=df['sender_id'].unique())
    
    # 1. transaction_frequency
    if 'transaction_frequency' in features:
        senders['transaction_frequency'] = sender_groups.size()
        computed_features.append('transaction_frequency')
        
    # 2. avg_transaction_amount
    if 'avg_transaction_amount' in features and 'amount' in df.columns:
        senders['avg_transaction_amount'] = sender_groups['amount'].mean()
        computed_features.append('avg_transaction_amount')
        
    # 3. amount_std_deviation
    if 'amount_std_deviation' in features and 'amount' in df.columns:
        senders['amount_std_deviation'] = sender_groups['amount'].std().fillna(0)
        computed_features.append('amount_std_deviation')
        
    # 4. rolling_sum_7d
    if 'rolling_sum_7d' in features and 'timestamp' in df.columns and 'amount' in df.columns:
        df_sorted = df.sort_values(by=['sender_id', 'timestamp']).set_index('timestamp')
        rolling_max = df_sorted.groupby('sender_id')['amount'].rolling('7D').sum().groupby('sender_id').max()
        senders['rolling_sum_7d'] = rolling_max
        computed_features.append('rolling_sum_7d')
        
    # 5. velocity
    if 'velocity' in features and 'timestamp' in df.columns:
        days_active = sender_groups['timestamp'].apply(lambda x: (x.max() - x.min()).days + 1)
        days_active = days_active.replace(0, 1)
        senders['velocity'] = sender_groups.size() / days_active
        computed_features.append('velocity')
        
    # 6. amount_deviation_from_mean
    if 'amount_deviation_from_mean' in features and 'amount' in df.columns:
        df['amount_deviation'] = df.groupby('sender_id')['amount'].transform(lambda x: abs(x - x.mean()))
        senders['amount_deviation_from_mean'] = df.groupby('sender_id')['amount_deviation'].max().fillna(0)
        computed_features.append('amount_deviation_from_mean')
        
    # 7. rapid_cashout_flag
    if 'rapid_cashout_flag' in features and 'timestamp' in df.columns:
        df_sorted = df.sort_values(by=['sender_id', 'timestamp']).set_index('timestamp')
        hourly_counts = df_sorted.groupby('sender_id')['amount'].rolling('1h').count()
        max_hourly = hourly_counts.groupby('sender_id').max()
        senders['rapid_cashout_flag'] = (max_hourly > 3).astype(int)
        computed_features.append('rapid_cashout_flag')
        
    # 8. round_amount_ratio
    if 'round_amount_ratio' in features and 'amount' in df.columns:
        df['is_round'] = (df['amount'] % 1000 == 0).astype(int)
        senders['round_amount_ratio'] = df.groupby('sender_id')['is_round'].mean()
        computed_features.append('round_amount_ratio')
        
    # 9. night_transaction_ratio
    if 'night_transaction_ratio' in features and 'timestamp' in df.columns:
        df['is_night'] = ((df['timestamp'].dt.hour >= 22) | (df['timestamp'].dt.hour < 6)).astype(int)
        senders['night_transaction_ratio'] = df.groupby('sender_id')['is_night'].mean()
        computed_features.append('night_transaction_ratio')
        
    # 10. counterparty_concentration
    if 'counterparty_concentration' in features and 'receiver_id' in df.columns:
        def herfindahl(series):
            counts = series.value_counts(normalize=True)
            return (counts ** 2).sum()
        senders['counterparty_concentration'] = df.groupby('sender_id')['receiver_id'].apply(herfindahl)
        computed_features.append('counterparty_concentration')
        
    # 11. max_single_transaction
    if 'max_single_transaction' in features and 'amount' in df.columns:
        senders['max_single_transaction'] = sender_groups['amount'].max()
        computed_features.append('max_single_transaction')
        
    # 12. dormancy_reactivation
    if 'dormancy_reactivation' in features and 'timestamp' in df.columns:
        df_sorted = df.sort_values(by=['sender_id', 'timestamp'])
        df_sorted['prev_time'] = df_sorted.groupby('sender_id')['timestamp'].shift(1)
        df_sorted['time_diff'] = (df_sorted['timestamp'] - df_sorted['prev_time']).dt.days
        has_dormancy = df_sorted.groupby('sender_id')['time_diff'].max() > 30
        senders['dormancy_reactivation'] = has_dormancy.astype(int)
        computed_features.append('dormancy_reactivation')
        
    senders = senders.fillna(0)
    
    summary_stats = {}
    for col in computed_features:
        if pd.api.types.is_numeric_dtype(senders[col]):
            summary_stats[col] = {
                'mean': float(senders[col].mean()),
                'std': float(senders[col].std()),
                'min': float(senders[col].min()),
                'max': float(senders[col].max())
            }
            
    numeric_df = senders[computed_features].select_dtypes(include=[np.number])
    if not numeric_df.empty:
        normalized = (numeric_df - numeric_df.mean()) / (numeric_df.std().replace(0, 1))
        anomaly_score = normalized.sum(axis=1)
        top_accounts = anomaly_score.nlargest(10).index.tolist()
    else:
        top_accounts = senders.index[:10].tolist()
        
    out_dict = {
        'status': 'SUCCESS',
        'features_created': computed_features,
        'feature_count': len(computed_features),
        'summary_statistics': summary_stats,
        'top_anomalous_accounts': top_accounts,
        'feature_matrix_sample': senders.head().reset_index().rename(columns={'index': 'sender_id'}).to_dict(orient='records')
    }
    
    return json.dumps(out_dict)
