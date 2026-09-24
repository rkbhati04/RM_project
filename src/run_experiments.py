import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
import warnings

warnings.filterwarnings('ignore')

DATA_PATH = Path("data/processed/dataset.csv")

# Exclude metadata, identifiers, and label-leaking network properties
EXCLUDE_COLS = [
    'network', 'resolver', 'protocol', 'workload', 'domain', 'repeat',
    'pcap_path', 'latency_s', 'status', 'note', 'server_ips', 'timestamp',
    'src_ip', 'dst_ip', 'src_port', 'dst_port', 'transport_protocol'
]

def load_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Cannot find dataset at {DATA_PATH}. Run extract_features.py first.")
    return pd.read_csv(DATA_PATH)

def prepare_features(df):
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    return df[feature_cols].fillna(0)

def split_by_repeat_or_group(df, target_col, test_size=0.2, seed=42):
    """
    For domain fingerprinting: split by repeat (train on repeats 0,1; test on repeat 2)
    so exact capture sessions are never shared, but all domains are present in train.
    Fallback to GroupShuffleSplit if repeats are insufficient.
    """
    if 'repeat' in df.columns and df['repeat'].nunique() > 1:
        max_rep = df['repeat'].max()
        train_mask = df['repeat'] < max_rep
        test_mask = df['repeat'] == max_rep
        
        X = prepare_features(df)
        y = df[target_col]
        return X[train_mask], X[test_mask], y[train_mask], y[test_mask]
    else:
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        X = prepare_features(df)
        y = df[target_col]
        groups = df['domain'] if 'domain' in df.columns else df.index
        train_idx, test_idx = next(gss.split(X, y, groups))
        return X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]

def evaluate(y_true, y_pred, name="Model", n_classes=50):
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average='macro')
    baseline = 1.0 / n_classes if n_classes > 1 else 0.5
    print(f"[{name}] Accuracy: {acc:.4f} | Macro-F1: {macro_f1:.4f} | Random Baseline: {baseline:.4f}")
    return acc, macro_f1

# --- E1: Protocol Identification (RQ1) ---
def run_e1(df):
    print("\n==================================================")
    print("E1: Protocol Identification (DoH vs DoH/3 vs DoQ)")
    print("==================================================")
    df_e1 = df[df['resolver'].isin(['adguard', 'quad9'])].copy()
    
    X_train, X_test, y_train, y_test = split_by_repeat_or_group(df_e1, target_col='protocol')
    
    rf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    evaluate(y_test, rf_preds, name="Random Forest (3-Way)", n_classes=3)
    print("Confusion Matrix (doh, doh3, doq):\n", confusion_matrix(y_test, rf_preds, labels=['doh', 'doh3', 'doq']))
    
    # Focused Sub-Test: DoH/3 vs DoQ
    df_quic = df_e1[df_e1['protocol'].isin(['doh3', 'doq'])].copy()
    X_tr_q, X_te_q, y_tr_q, y_te_q = split_by_repeat_or_group(df_quic, target_col='protocol')
    rf_q = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    rf_q.fit(X_tr_q, y_tr_q)
    evaluate(y_te_q, rf_q.predict(X_te_q), name="Random Forest (DoH/3 vs DoQ)", n_classes=2)

# --- E2: Domain Fingerprinting per Protocol (RQ2) ---
def run_e2(df):
    print("\n==================================================")
    print("E2: Domain Fingerprinting per Protocol")
    print("==================================================")
    protocols = [p for p in df['protocol'].unique() if p in ['doh', 'doh3', 'doq']]
    
    for proto in sorted(protocols):
        df_p = df[df['protocol'] == proto].copy()
        if len(df_p) < 20:
            continue
            
        X_train, X_test, y_train, y_test = split_by_repeat_or_group(df_p, target_col='domain')
        
        # Encode string domains to contiguous integers for XGBoost
        le = LabelEncoder()
        y_train_enc = le.fit_transform(y_train)
        
        # Filter test set to domains present during training
        test_mask = y_test.isin(le.classes_)
        X_test_filt = X_test[test_mask]
        y_test_filt = y_test[test_mask]
        y_test_enc = le.transform(y_test_filt)
        
        xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric='mlogloss')
        xgb.fit(X_train, y_train_enc)
        preds = xgb.predict(X_test_filt)
        
        n_cls = len(le.classes_)
        evaluate(y_test_enc, preds, name=f"XGBoost ({proto.upper()})", n_classes=n_cls)

# --- E3: Feature Importance & Group Ablation (RQ3) ---
def run_e3(df):
    print("\n==================================================")
    print("E3: Feature Importance & Group Ablation")
    print("==================================================")
    X_train, X_test, y_train, y_test = split_by_repeat_or_group(df, target_col='domain')
    
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    
    # Filter test set for domains evaluated during training
    test_mask = y_test.isin(rf.classes_)
    X_test_f = X_test[test_mask]
    y_test_f = y_test[test_mask]
    
    n_cls = len(rf.classes_)
    base_acc, _ = evaluate(y_test_f, rf.predict(X_test_f), name="Baseline Full Feature Set", n_classes=n_cls)
    
    importances = pd.Series(rf.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print("\nTop 10 Most Important Features:\n", importances.head(10))
    
    ablation_groups = {
        'Packet Sizes': [c for c in X_train.columns if 'bytes' in c or 'up_' in c or 'down_' in c],
        'Timing & IAT': [c for c in X_train.columns if 'iat' in c or 'duration' in c or 't_first_down' in c],
        'Bursts': [c for c in X_train.columns if 'burst' in c],
        'First-20 Packets': [c for c in X_train.columns if c.startswith('pkt_')]
    }
    
    print("\n--- Feature Group Ablation ---")
    for group_name, cols in ablation_groups.items():
        remaining_cols = [c for c in X_train.columns if c not in cols]
        rf_abl = RandomForestClassifier(n_estimators=100, random_state=42)
        rf_abl.fit(X_train[remaining_cols], y_train)
        acc, _ = evaluate(y_test_f, rf_abl.predict(X_test_f[remaining_cols]), name=f"Without [{group_name}]", n_classes=n_cls)
        print(f"  --> Drop in Accuracy: {base_acc - acc:.4f}")

# --- E4: Cross-Resolver Transfer (RQ4) ---
def run_e4(df):
    print("\n==================================================")
    print("E4: Cross-Resolver Fingerprinting Transfer")
    print("==================================================")
    for train_res, test_res in [('adguard', 'quad9'), ('quad9', 'adguard')]:
        train_df = df[df['resolver'] == train_res].copy()
        test_df = df[df['resolver'] == test_res].copy()
        
        common_domains = set(train_df['domain']).intersection(set(test_df['domain']))
        train_df = train_df[train_df['domain'].isin(common_domains)]
        test_df = test_df[test_df['domain'].isin(common_domains)]
        
        X_train = prepare_features(train_df)
        y_train = train_df['domain']
        X_test = prepare_features(test_df)
        y_test = test_df['domain']
        
        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)
        
        test_mask = y_test.isin(rf.classes_)
        evaluate(y_test[test_mask], rf.predict(X_test[test_mask]), name=f"Train: {train_res.title()} -> Test: {test_res.title()}", n_classes=len(common_domains))

# --- E5: Global vs India Workload Analysis (RQ5) ---
def run_e5(df):
    print("\n==================================================")
    print("E5: Global vs India Workload Analysis")
    print("==================================================")
    # Workload Binary Classification
    X_train, X_test, y_train, y_test = split_by_repeat_or_group(df, target_col='workload')
    rf_wl = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_wl.fit(X_train, y_train)
    evaluate(y_test, rf_wl.predict(X_test), name="Workload Classification (Global vs India)", n_classes=2)
    
    # Per-Workload Domain Fingerprinting
    for wl in ['global', 'india']:
        df_wl = df[df['workload'] == wl].copy()
        X_tr, X_te, y_tr, y_te = split_by_repeat_or_group(df_wl, target_col='domain')
        
        rf_dom = RandomForestClassifier(n_estimators=100, random_state=42)
        rf_dom.fit(X_tr, y_tr)
        
        test_mask = y_te.isin(rf_dom.classes_)
        evaluate(y_te[test_mask], rf_dom.predict(X_te[test_mask]), name=f"Domain Fingerprinting [{wl.title()} Workload]", n_classes=len(df_wl['domain'].unique()))

if __name__ == "__main__":
    df = load_data()
    run_e1(df)
    run_e2(df)
    run_e3(df)
    run_e4(df)
    run_e5(df)