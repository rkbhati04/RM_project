#!/usr/bin/env python3
"""
plot_slide_figures.py — Generate high-resolution figures for presentation slides.

Figures produced:
  1. fig1_headline_doh_vs_doh3.png : Airtel DoH vs DoH/3 fingerprinting across 4 resolvers
  2. fig2_cross_network_transfer.png: Within-network vs cross-network transfer collapse
  3. fig3_carrier_quic_blocking.png : Protocol availability (Airtel vs Jio)
  4. fig4_feature_distribution_shift.png: Top 8 features shifting across cellular
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Set global academic plot styling
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "axes.grid": True,
    "grid.alpha": 0.3,
})


def plot_headline_airtel():
    # Data from claims ledger
    resolvers = ["AdGuard", "Cloudflare", "Google", "Quad9"]
    
    # Global workload
    doh_global = [0.262, 0.236, 0.175, 0.342]
    doh3_global = [0.089, 0.060, 0.169, 0.046]
    
    # India workload
    doh_india = [0.233, 0.195, 0.148, 0.310]
    doh3_india = [0.092, 0.053, 0.101, 0.051]
    
    x = np.arange(len(resolvers))
    width = 0.35
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True, constrained_layout=True)
    
    # Global subplot
    axes[0].bar(x - width/2, doh_global, width, label="DoH (HTTP/2)", color="#1f77b4", edgecolor="black", alpha=0.9)
    axes[0].bar(x + width/2, doh3_global, width, label="DoH/3 (QUIC)", color="#ff7f0e", edgecolor="black", alpha=0.9)
    axes[0].axhline(0.010, color="red", linestyle="--", linewidth=1.5, label="Chance (1/100 = 1%)")
    axes[0].set_title("Global Workload (100 domains)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(resolvers)
    axes[0].set_ylabel("Fingerprinting Accuracy")
    axes[0].set_ylim(0, 0.40)
    axes[0].legend(loc="upper left")
    
    # India subplot
    axes[1].bar(x - width/2, doh_india, width, label="DoH (HTTP/2)", color="#1f77b4", edgecolor="black", alpha=0.9)
    axes[1].bar(x + width/2, doh3_india, width, label="DoH/3 (QUIC)", color="#ff7f0e", edgecolor="black", alpha=0.9)
    axes[1].axhline(0.010, color="red", linestyle="--", linewidth=1.5, label="Chance (1/100 = 1%)")
    axes[1].set_title("Indian Regional Workload (100 domains)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(resolvers)
    axes[1].legend(loc="upper left")
    
    fig.suptitle("RQ2: Encrypted DNS Fingerprinting Accuracy (Airtel Broadband, k=10)", weight="bold")
    fig.savefig(OUT_DIR / "fig1_headline_doh_vs_doh3.png", dpi=200)
    plt.close(fig)
    print("Wrote fig1_headline_doh_vs_doh3.png")


def plot_cross_network():
    # Comparing Within-Airtel, Within-Jio, and Cross-Network Transfer
    slices = ["Google\n(Global)", "AdGuard\n(Global)", "Google\n(India)", "AdGuard\n(India)"]
    
    within_airtel = [0.175, 0.262, 0.148, 0.233]
    within_jio = [0.153, 0.041, 0.133, 0.085]
    transfer_airtel_to_jio = [0.017, 0.016, 0.019, 0.020]
    transfer_jio_to_airtel = [0.019, 0.024, 0.018, 0.021]
    
    x = np.arange(len(slices))
    width = 0.20
    
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    
    ax.bar(x - 1.5*width, within_airtel, width, label="Within-Airtel", color="#2ca02c", edgecolor="black")
    ax.bar(x - 0.5*width, within_jio, width, label="Within-Jio", color="#1f77b4", edgecolor="black")
    ax.bar(x + 0.5*width, transfer_airtel_to_jio, width, label="Transfer: Airtel -> Jio", color="#d62728", edgecolor="black", hatch="//")
    ax.bar(x + 1.5*width, transfer_jio_to_airtel, width, label="Transfer: Jio -> Airtel", color="#9467bd", edgecolor="black", hatch="\\\\")
    
    ax.axhline(0.020, color="black", linestyle="--", linewidth=1.5, label="Chance Level (1/50 = 2%)")
    
    ax.set_ylabel("Accuracy")
    ax.set_title("N2: Cross-Network Transfer Collapse (Airtel vs Reliance Jio)", weight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(slices)
    ax.set_ylim(0, 0.35)
    ax.legend(loc="upper right", framealpha=0.95)
    
    fig.savefig(OUT_DIR / "fig2_cross_network_transfer.png", dpi=200)
    plt.close(fig)
    print("Wrote fig2_cross_network_transfer.png")


def plot_carrier_blocking():
    # Comparing protocol reachability on Airtel vs Jio
    categories = ["Airtel DoH\n(TCP 443)", "Airtel DoH/3\n(UDP 443)", "Jio DoH\n(TCP 443)", "Jio DoH/3\n(UDP 443)"]
    success_rates = [98.5, 96.8, 95.3, 0.0]
    colors = ["#2ca02c", "#2ca02c", "#1f77b4", "#d62728"]
    
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    bars = ax.bar(categories, success_rates, color=colors, edgecolor="black", width=0.55)
    
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", weight="bold")
        
    ax.set_ylabel("Query Completion Rate (%)")
    ax.set_title("N8: Transport Protocol Reachability & Carrier Blocking", weight="bold")
    ax.set_ylim(0, 115)
    
    # Text annotation on the zero bar
    ax.text(3, 10, "100% BLOCKED\nby Carrier Gateway", ha="center", color="#d62728", weight="bold", fontsize=11)
    
    fig.savefig(OUT_DIR / "fig3_carrier_quic_blocking.png", dpi=200)
    plt.close(fig)
    print("Wrote fig3_carrier_quic_blocking.png")


def plot_feature_shift():
    # Plot top features shifting between Airtel and Jio from n4_feature_shift.csv
    n4_path = ROOT / "results/jio_analysis_20261113/n4_feature_shift.csv"
    if not n4_path.exists():
        return
    df = pd.read_csv(n4_path).head(8)
    
    features = df["feature"].tolist()
    ks_vals = df["ks_statistic"].tolist()
    
    fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    y_pos = np.arange(len(features))
    ax.barh(y_pos, ks_vals, color="#41b6c4", edgecolor="black")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features)
    ax.invert_yaxis()  # top feature on top
    ax.set_xlabel("Kolmogorov-Smirnov Statistic (D) [0 = identical, 1 = maximum shift]")
    ax.set_title("N4: Top Feature Distribution Shifts (Airtel Broadband vs Jio Cellular)", weight="bold")
    ax.set_xlim(0, 1.1)
    
    for i, v in enumerate(ks_vals):
        ax.text(v + 0.02, i, f"D = {v:.3f}", va="center", fontsize=9, weight="bold")
        
    fig.savefig(OUT_DIR / "fig4_feature_distribution_shift.png", dpi=200)
    plt.close(fig)
    print("Wrote fig4_feature_distribution_shift.png")


def main():
    plot_headline_airtel()
    plot_cross_network()
    plot_carrier_blocking()
    plot_feature_shift()
    print("All slide figures generated successfully!")


if __name__ == "__main__":
    main()
