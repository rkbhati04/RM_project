import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from pathlib import Path

# Styling
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Helvetica, Arial, DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8

OUT = Path("results")
OUT.mkdir(exist_ok=True)

# 1. E1: Confusion Matrix
cm = np.array([[50, 0, 0], [0, 90, 0], [0, 6, 88]])
labels = ['DoH', 'DoH/3', 'DoQ']
fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels, cbar=False, ax=ax, annot_kws={"size": 14, "weight": "bold"})
ax.set_title("E1: Protocol Identification Confusion Matrix\n(Overall Accuracy: 97.44%)", fontsize=12, pad=12, fontweight='bold')
ax.set_xlabel("Predicted Protocol", fontsize=11, labelpad=8)
ax.set_ylabel("True Protocol", fontsize=11, labelpad=8)
plt.tight_layout()
plt.savefig(OUT / "e1_protocol_confusion_matrix.png")
plt.close()

# 2. E2: Domain Fingerprinting per Protocol
protocols = ['DoH (HTTP/2)', 'DoH/3 (QUIC)', 'DoQ (QUIC)']
accs = [6.00, 4.44, 9.57]
baselines = [2.08, 2.00, 2.00]

x = np.arange(len(protocols))
width = 0.35
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
rects1 = ax.bar(x - width/2, accs, width, label='XGBoost Fingerprinting Accuracy (%)', color='#2b5c8f')
rects2 = ax.bar(x + width/2, baselines, width, label='Random Guess Baseline (%)', color='#a0aab2', linestyle='--')

ax.set_ylabel('Accuracy (%)', fontsize=11)
ax.set_title('E2: Website Fingerprinting Vulnerability by Protocol\n(Lower Accuracy = Higher Privacy)', fontsize=12, pad=12, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(protocols, fontsize=11)
ax.legend(frameon=True)
ax.set_ylim(0, 12)

for r in rects1:
    h = r.get_height()
    ax.annotate(f'{h:.2f}%', xy=(r.get_x() + r.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
plt.savefig(OUT / "e2_fingerprinting_accuracy.png")
plt.close()

# 3. E3: Top Feature Importances
feats = [
    ('Median Inter-Arrival Time', 0.0417),
    ('Max Inter-Arrival Time', 0.0371),
    ('Std Inter-Arrival Time', 0.0370),
    ('Mean Inter-Arrival Time', 0.0365),
    ('Down/Up Byte Ratio', 0.0359),
    ('Downstream Std Bytes', 0.0355),
    ('Downstream Mean Bytes', 0.0350),
    ('Upstream Mean Bytes', 0.0346),
    ('Upstream Std Bytes', 0.0338),
    ('Total Duration', 0.0331)
]
df_feats = pd.DataFrame(feats, columns=['Feature', 'Importance']).sort_values('Importance', ascending=True)

fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
ax.barh(df_feats['Feature'], df_feats['Importance'], color='#1f77b4', height=0.6)
ax.set_xlabel('Gini Feature Importance', fontsize=11)
ax.set_title('E3: Top 10 Metadata Features Driving Leakage\n(Timing & Directional Bytes Dominate)', fontsize=12, pad=12, fontweight='bold')
plt.tight_layout()
plt.savefig(OUT / "e3_feature_importance.png")
plt.close()

# 4. E5: Workload Comparison
wl_names = ['Global Workload', 'Indian Workload']
wl_accs = [2.40, 9.17]
wl_base = [4.00, 4.00]

x = np.arange(len(wl_names))
fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
r1 = ax.bar(x - width/2, wl_accs, width, label='Domain Fingerprinting Accuracy (%)', color=['#3b82f6', '#ef4444'])
r2 = ax.bar(x + width/2, wl_base, width, label='Random Baseline (4.0%)', color='#9ca3af')
ax.set_ylabel('Accuracy (%)', fontsize=11)
ax.set_title('E5: Regional Workload Fingerprintability\n(India Workload is 3.8x More Vulnerable)', fontsize=12, pad=12, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(wl_names, fontsize=11)
ax.set_ylim(0, 12)
ax.legend(frameon=True)
for r in r1:
    h = r.get_height()
    ax.annotate(f'{h:.2f}%', xy=(r.get_x() + r.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontweight='bold')
plt.tight_layout()
plt.savefig(OUT / "e5_workload_comparison.png")
plt.close()

print("All publication figures generated in results/ successfully!")
