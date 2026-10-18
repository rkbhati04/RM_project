"""DoH/3 Privacy Analysis Runner (RQ1, RQ2, and RQ3).

Executes the DoH/3 focused experiments:
  RQ1: Domain Fingerprinting on DoH/3 (Multi-class Identification)
  RQ2: Traffic-Analysis Resistance across DoH/3 Resolvers
  RQ3: Feature Importance and Group Ablation Study

Usage:
    python src\\run_experiments.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
import warnings

warnings.filterwarnings('ignore')

DATA_PATH = Path("data/processed/dataset.csv")
EXCLUDE_COLS = [
    'network', 'resolver', 'protocol', 'workload', 'domain', 'repeat',
    'pcap_path', 'latency_s', 'status', 'note', 'server_ips', 'timestamp',
    'src_ip', 'dst_ip', 'src_port', 'dst_port', 'transport_protocol'
]


def load_doh3_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Cannot find dataset at {DATA_PATH}. Run extract_features.py first.")
    df = pd.read_csv(DATA_PATH)
    doh3_df = df[df['protocol'] == 'doh3'].copy().reset_index(drop=True)
    if doh3_df.empty:
        raise ValueError("No 'doh3' records found in dataset.csv.")
    return doh3_df


def prepare_features(df):
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    return df[feature_cols].fillna(0)


def split_by_repeat(df, target_col='domain'):
    """Train on earlier repeats (0..max-1), test on the held-out repeat (max)."""
    if 'repeat' in df.columns and df['repeat'].nunique() > 1:
        max_rep = df['repeat'].max()
        train_mask = df['repeat'] < max_rep
        test_mask = df['repeat'] == max_rep
        X = prepare_features(df)
        y = df[target_col]
        return X[train_mask], X[test_mask], y[train_mask], y[test_mask]
    else:
        from sklearn.model_selection import train_test_split
        X = prepare_features(df)
        y = df[target_col]
        return train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)


def evaluate(y_true, y_pred, name="Model", n_classes=50):
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average='macro')
    baseline = 1.0 / n_classes if n_classes > 0 else 0.02
    print(f"[{name}] Accuracy: {acc*100:.2f}% | Macro-F1: {macro_f1:.4f} | Random Baseline: {baseline*100:.2f}%")
    return acc, macro_f1


# --- RQ1: DoH/3 Domain Query Identification ---
def run_rq1(df):
    print("\n" + "=" * 60)
    print("RQ1: DoH/3 Domain Query Identification (Fingerprinting)")
    print("=" * 60)
    n_domains = df['domain'].nunique()
    print(f"Total DoH/3 samples: {len(df)} across {n_domains} domains")

    X_train, X_test, y_train, y_test = split_by_repeat(df, target_col='domain')

    # Random Forest
    rf = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')
    rf.fit(X_train, y_train)

    test_mask = y_test.isin(rf.classes_)
    rf_preds = rf.predict(X_test[test_mask])
    y_test_f = y_test[test_mask]

    evaluate(y_test_f, rf_preds, name="DoH/3 Random Forest", n_classes=n_domains)

    # Top-5 Accuracy
    proba = rf.predict_proba(X_test[test_mask])
    top5_hits = 0
    classes = rf.classes_
    for i, true_label in enumerate(y_test_f):
        top5_classes = classes[np.argsort(-proba[i])[:5]]
        if true_label in top5_classes:
            top5_hits += 1
    top5_acc = top5_hits / len(y_test_f)
    print(f"[DoH/3 Random Forest] Top-5 Accuracy: {top5_acc*100:.2f}%")


# --- RQ2: Traffic-Analysis Resistance Across Resolvers ---
def run_rq2(df):
    print("\n" + "=" * 60)
    print("RQ2: DoH/3 Traffic-Analysis Resistance Across Resolvers")
    print("=" * 60)
    resolvers = sorted(df['resolver'].unique())

    for res in resolvers:
        df_res = df[df['resolver'] == res].copy()
        if len(df_res) < 20:
            continue
        n_dom = df_res['domain'].nunique()
        X_train, X_test, y_train, y_test = split_by_repeat(df_res, target_col='domain')

        rf = RandomForestClassifier(n_estimators=200, random_state=42)
        rf.fit(X_train, y_train)
        test_mask = y_test.isin(rf.classes_)
        preds = rf.predict(X_test[test_mask])
        acc, _ = evaluate(y_test[test_mask], preds, name=f"DoH/3 [{res.title():10s}]", n_classes=n_dom)
        resistance = max(0.0, 100.0 * (1.0 - (acc - 1.0/n_dom)/(1.0 - 1.0/n_dom)))
        print(f"  -> Resistance Score: {resistance:.1f}% (Higher = More Private)")


# --- RQ3: Feature Importance & Group Ablation in DoH/3 ---
def run_rq3(df):
    print("\n" + "=" * 60)
    print("RQ3: Traffic Characteristics Driving DoH/3 Leakage")
    print("=" * 60)
    X_train, X_test, y_train, y_test = split_by_repeat(df, target_col='domain')
    n_dom = df['domain'].nunique()

    rf = RandomForestClassifier(n_estimators=200, random_state=42)
    rf.fit(X_train, y_train)
    test_mask = y_test.isin(rf.classes_)
    base_acc, _ = evaluate(y_test[test_mask], rf.predict(X_test[test_mask]), name="Baseline (All Features)", n_classes=n_dom)

    importances = pd.Series(rf.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print("\nTop 10 Most Leaking Features in DoH/3:\n", importances.head(10).round(4))

    ablation_groups = {
        'Packet Sizes': [c for c in X_train.columns if 'bytes' in c or 'up_' in c or 'down_' in c],
        'Timing & IAT': [c for c in X_train.columns if 'iat' in c or 'duration' in c or 't_first_down' in c],
        'Bursts': [c for c in X_train.columns if 'burst' in c],
        'First-20 Packets': [c for c in X_train.columns if c.startswith('pkt_')]
    }

    print("\n--- Feature Group Ablation on DoH/3 ---")
    for group_name, cols in ablation_groups.items():
        rem_cols = [c for c in X_train.columns if c not in cols]
        rf_abl = RandomForestClassifier(n_estimators=200, random_state=42)
        rf_abl.fit(X_train[rem_cols], y_train)
        acc, _ = evaluate(y_test[test_mask], rf_abl.predict(X_test[test_mask][rem_cols]), name=f"Without [{group_name}]", n_classes=n_dom)
        delta = (acc - base_acc) * 100
        print(f"  --> Accuracy Impact: {delta:+.2f}%")


if __name__ == "__main__":
    doh3_df = load_doh3_data()
    run_rq1(doh3_df)
    run_rq2(doh3_df)
    run_rq3(doh3_df)