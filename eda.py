"""
eda.py
------
Exploratory Data Analysis for the fraud detection pipeline.

Runs after generate_data.py and anomaly_detection.py. Produces a set of
diagnostic charts and summary tables that answer three questions:

  1. DATA QUALITY   — Is the dataset complete and well-formed?
  2. DISTRIBUTIONS  — What does the transaction population look like?
  3. FRAUD SIGNAL   — Do the engineered features actually separate fraud from
                      normal? If not, the model has nothing to learn from.

OUTPUT:
  outputs/eda/eda_summary.csv     — Key statistics table
  outputs/eda/*.png               — All charts (also shown in dashboard)

Run this before the full pipeline to validate data and confirm feature
engineering is working as intended. Especially useful when swapping in
the real PaySim dataset or a new data source.
"""

import os
import warnings

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from anomaly_detection import engineer_features

warnings.filterwarnings("ignore")

# ── Plot styling ──────────────────────────────────────────────────────────────
# A minimal, professional color palette consistent with risk dashboards.
# PRIMARY = flagged/high-risk items; SECONDARY = normal/background items.
PRIMARY   = "#1B2A4A"   # navy — flagged / fraud / primary bars
SECONDARY = "#2E7D8C"   # teal — normal / scored / secondary bars
GOLD      = "#C8972B"   # gold — accent / highlight / threshold lines
RED       = "#C0392B"   # red  — HIGH risk tier
ORANGE    = "#E67E22"   # orange — MEDIUM risk tier
GREEN     = "#27AE60"   # green — LOW risk tier / normal
LIGHT_GRAY = "#F5F5F5"  # background fill
MID_GRAY   = "#888888"  # axis labels and captions

# Apply a clean, minimal matplotlib style globally
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "white",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.grid":        True,
    "grid.alpha":       0.3,
    "grid.linestyle":   "--",
    "font.family":      "sans-serif",
    "font.size":        10,
})

EDA_DIR = str(config.EDA_DIR)
config.ensure_dirs()


# ── Helper utilities ──────────────────────────────────────────────────────────

def save_fig(fig, name):
    """
    Save a matplotlib figure to the EDA output directory and close it.

    Closing immediately frees memory — important when generating many
    charts in sequence.

    Args:
        fig:  matplotlib Figure object.
        name: Filename without extension (e.g., "01_transaction_types").
    """
    path = os.path.join(EDA_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def section(title):
    """Print a formatted section header to the console for easy log scanning."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Data loading ──────────────────────────────────────────────────────────────

def load_pipeline_data():
    """
    Load both pipeline outputs needed for EDA:
      - raw transactions  (from generate_data.py)
      - scored transactions (from anomaly_detection.py, includes risk scores)

    Returns raw if scored is not yet available (allows partial pipeline runs).

    Returns:
        tuple: (raw_df, scored_df)
               raw_df    — original transactions without model scores
               scored_df — transactions with risk_score, risk_tier, anomaly_flag,
                           and all engineered feature columns
    """
    raw_path = config.TRANSACTIONS_CSV
    scored_path = config.SCORED_CSV

    if not raw_path.exists():
        raise FileNotFoundError(
            f"transactions.csv not found at {raw_path}. "
            "Run generate_data.py first."
        )

    raw = pd.read_csv(raw_path)

    if scored_path.exists():
        scored = pd.read_csv(scored_path)
        print(f"Loaded {len(raw):,} raw + {len(scored):,} scored transactions")
    else:
        scored = engineer_features(raw.copy())
        print(
            f"Loaded {len(raw):,} raw transactions "
            "(no scored file — run anomaly_detection.py for risk charts)"
        )

    return raw, scored


# ── Section 1: Data Quality ───────────────────────────────────────────────────

def plot_data_quality(df):
    """
    Produce a data quality summary: missing values, data types, and row counts.

    A clean pipeline should have zero missing values in key fields. Any gaps
    in amount, type, or account IDs would break downstream processing and
    should be caught here before the model runs.

    Outputs:
      - Console table of field completeness
      - outputs/eda/01_data_quality.png — horizontal bar chart of % complete
    """
    section("1. Data Quality")

    # Check completeness of all columns in the dataset
    quality = pd.DataFrame({
        "Field":    df.columns,
        "Non-Null": df.notnull().sum().values,
        "Missing":  df.isnull().sum().values,
        "% Complete": (df.notnull().sum() / len(df) * 100).round(1).values,
        "Dtype":    [str(df[c].dtype) for c in df.columns],
    })

    print(quality.to_string(index=False))

    # Chart: completeness percentage per field
    fig, ax = plt.subplots(figsize=(8, max(4, len(df.columns) * 0.35)))

    colors = [GREEN if p == 100 else GOLD if p >= 95 else RED
              for p in quality["% Complete"]]

    bars = ax.barh(quality["Field"], quality["% Complete"],
                   color=colors, alpha=0.85, edgecolor="white")

    # Add percentage labels to the right of each bar
    for bar, pct in zip(bars, quality["% Complete"]):
        ax.text(min(pct + 0.5, 101), bar.get_y() + bar.get_height() / 2,
                f"{pct:.0f}%", va="center", ha="left", fontsize=9, color=MID_GRAY)

    ax.set_xlim(0, 108)
    ax.set_xlabel("% Complete", color=MID_GRAY)
    ax.set_title("Data Completeness by Field", fontweight="bold", pad=12)
    ax.axvline(100, color=MID_GRAY, linestyle="--", alpha=0.4, linewidth=1)

    # Legend for color coding
    legend_elements = [
        mpatches.Patch(color=GREEN, label="100% complete"),
        mpatches.Patch(color=GOLD,  label="95–99% complete"),
        mpatches.Patch(color=RED,   label="<95% complete"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)

    fig.tight_layout()
    save_fig(fig, "01_data_quality")

    # Also save quality table as CSV for reference
    quality.to_csv(os.path.join(EDA_DIR, "eda_quality.csv"), index=False)

    return quality


# ── Section 2: Transaction Distributions ─────────────────────────────────────

def plot_transaction_type_distribution(df):
    """
    Bar chart of transaction counts by type.

    Confirms the synthetic generation weights are working correctly.
    In production data, this reveals whether the transaction mix matches
    expectations — unexpected dominance of CASH_OUT, for example, might
    indicate a data pipeline issue or a genuinely unusual customer segment.

    Outputs:
      outputs/eda/02_transaction_types.png
    """
    section("2. Transaction Type Distribution")

    type_counts = df["type"].value_counts().reset_index()
    type_counts.columns = ["Type", "Count"]
    type_counts["Pct"] = (type_counts["Count"] / len(df) * 100).round(1)

    # Color TRANSFER and CASH_OUT differently — these are the fraud-eligible types
    colors = [RED if t in ("TRANSFER", "CASH_OUT") else SECONDARY
              for t in type_counts["Type"]]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(type_counts["Type"], type_counts["Count"],
                  color=colors, alpha=0.85, edgecolor="white", width=0.6)

    # Add count and percentage labels above each bar
    for bar, (_, row) in zip(bars, type_counts.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + len(df) * 0.005,
                f"{row['Count']:,}\n({row['Pct']}%)",
                ha="center", va="bottom", fontsize=9, color=MID_GRAY)

    ax.set_ylabel("Transaction Count")
    ax.set_title("Transaction Volume by Type", fontweight="bold", pad=12)
    ax.set_ylim(0, type_counts["Count"].max() * 1.2)

    # Annotation explaining color coding
    ax.annotate("Red = fraud-eligible types (TRANSFER, CASH_OUT)",
                xy=(0.02, 0.97), xycoords="axes fraction",
                fontsize=8, color=RED, va="top")

    fig.tight_layout()
    save_fig(fig, "02_transaction_types")

    print(type_counts.to_string(index=False))


def plot_amount_distribution(df):
    """
    Log-scale histogram of transaction amounts, split by fraud label.

    Amount is the single most important feature for fraud detection.
    This chart verifies the lognormal distribution is working correctly
    and shows whether fraudulent transactions cluster at higher amounts
    — which they should, given the generation logic.

    Using log scale on the x-axis is essential: transaction amounts span
    several orders of magnitude ($1 to $2M), which makes a linear scale
    unreadable.

    Outputs:
      outputs/eda/03_amount_distribution.png
    """
    section("3. Amount Distribution")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Left panel: full distribution on log scale
    ax = axes[0]
    ax.hist(np.log10(df["amount"].clip(lower=1)), bins=50,
            color=SECONDARY, alpha=0.8, edgecolor="white")
    ax.set_xlabel("log₁₀(Amount in $)")
    ax.set_ylabel("Count")
    ax.set_title("Amount Distribution (Log Scale)", fontweight="bold")

    # Add reference lines for key thresholds used in feature engineering
    for val, label, color in [
        (np.log10(100_000), "$100K threshold\n(is_large_transaction)", RED),
        (np.log10(200_000), "$200K threshold\n(fraud uplift)", GOLD),
    ]:
        ax.axvline(val, color=color, linestyle="--", alpha=0.7, linewidth=1.5)
        ax.text(val + 0.05, ax.get_ylim()[1] * 0.85, label,
                color=color, fontsize=7, va="top")

    # Right panel: fraud vs. normal amount distributions overlaid
    ax = axes[1]
    if "isFraud" in df.columns and df["isFraud"].sum() > 0:
        # Separate fraud and normal for overlay comparison
        normal_amounts = np.log10(df[df["isFraud"] == 0]["amount"].clip(lower=1))
        fraud_amounts  = np.log10(df[df["isFraud"] == 1]["amount"].clip(lower=1))

        ax.hist(normal_amounts, bins=40, color=SECONDARY, alpha=0.6,
                label="Normal", edgecolor="white", density=True)
        ax.hist(fraud_amounts,  bins=20, color=RED, alpha=0.7,
                label="Fraud",  edgecolor="white", density=True)

        ax.set_xlabel("log₁₀(Amount in $)")
        ax.set_ylabel("Density")
        ax.set_title("Amount: Fraud vs. Normal (Density)", fontweight="bold")
        ax.legend()
    else:
        # Fallback if no fraud labels available
        ax.text(0.5, 0.5, "No fraud labels\navailable",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=12, color=MID_GRAY)
        ax.set_title("Amount: Fraud vs. Normal", fontweight="bold")

    fig.tight_layout()
    save_fig(fig, "03_amount_distribution")

    # Print summary statistics for the amount field
    print(df["amount"].describe().apply(lambda x: f"${x:,.2f}").to_string())


def plot_hourly_activity(df):
    """
    Bar chart of transaction volume by hour of day.

    The is_late_night feature flags hours 0–4 as elevated risk. This chart
    validates that off-hours activity is a genuine signal — if fraud
    concentrates in those hours, the feature is earning its place in the model.

    Outputs:
      outputs/eda/04_hourly_activity.png
    """
    section("4. Hourly Activity Pattern")

    # Aggregate counts by hour for all transactions and fraud subset
    hourly_all   = df.groupby("hour").size().reindex(range(24), fill_value=0)
    hourly_fraud = (df[df["isFraud"] == 1].groupby("hour").size().reindex(range(24), fill_value=0)
                    if "isFraud" in df.columns else pd.Series(0, index=range(24)))

    fig, ax = plt.subplots(figsize=(12, 4))

    # Color bars: red for late-night hours (0–4), teal for all others
    bar_colors = [RED if h <= 4 else SECONDARY for h in range(24)]
    ax.bar(range(24), hourly_all.values, color=bar_colors,
           alpha=0.75, edgecolor="white", label="All transactions")

    # Overlay fraud counts as a separate bar series if labels are available
    if hourly_fraud.sum() > 0:
        ax2 = ax.twinx()  # secondary y-axis for fraud counts (different scale)
        ax2.plot(range(24), hourly_fraud.values, color=GOLD,
                 linewidth=2, marker="o", markersize=5, label="Fraud count")
        ax2.set_ylabel("Fraud Count", color=GOLD)
        ax2.tick_params(axis="y", labelcolor=GOLD)
        ax2.legend(loc="upper right", fontsize=9)

    # Shade the late-night risk window
    ax.axvspan(-0.5, 4.5, alpha=0.08, color=RED, label="Late-night window (0–4)")
    ax.set_xlabel("Hour of Day (0 = midnight)")
    ax.set_ylabel("Transaction Count")
    ax.set_title("Transaction Volume by Hour of Day", fontweight="bold", pad=12)
    ax.set_xticks(range(24))
    ax.legend(loc="upper left", fontsize=9)

    fig.tight_layout()
    save_fig(fig, "04_hourly_activity")


def plot_country_distribution(df):
    """
    Horizontal bar chart of transaction volume by country.

    Validates that high-risk countries (NG, RU, UA, KE) have elevated
    fraud rates relative to their transaction volume. If they don't, the
    is_high_risk_country feature isn't providing real signal.

    Outputs:
      outputs/eda/05_country_distribution.png
    """
    section("5. Country Distribution")

    # Compute total transactions, fraud count, and fraud rate per country
    country_stats = (
        df.groupby("country")
        .agg(
            total=("amount", "count"),
            fraud=("isFraud", "sum") if "isFraud" in df.columns else ("amount", lambda x: 0),
        )
        .reset_index()
        .sort_values("total", ascending=True)  # horizontal bar: ascending = top-to-bottom sorted
    )
    country_stats["fraud_rate"] = (
        country_stats["fraud"] / country_stats["total"] * 100
    ).round(1)

    # High-risk countries get a distinct color
    HIGH_RISK = set(config.HIGH_RISK_COUNTRIES)
    bar_colors = [RED if c in HIGH_RISK else SECONDARY
                  for c in country_stats["country"]]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left panel: transaction volume by country
    ax = axes[0]
    ax.barh(country_stats["country"], country_stats["total"],
            color=bar_colors, alpha=0.85, edgecolor="white")
    ax.set_xlabel("Transaction Count")
    ax.set_title("Transaction Volume by Country", fontweight="bold")

    legend_elements = [
        mpatches.Patch(color=RED,       label="High-risk jurisdiction"),
        mpatches.Patch(color=SECONDARY, label="Standard jurisdiction"),
    ]
    ax.legend(handles=legend_elements, fontsize=8)

    # Right panel: fraud rate (%) by country — the key diagnostic
    ax = axes[1]
    ax.barh(country_stats["country"], country_stats["fraud_rate"],
            color=bar_colors, alpha=0.85, edgecolor="white")
    ax.set_xlabel("Fraud Rate (%)")
    ax.set_title("Fraud Rate by Country", fontweight="bold")

    # Add rate labels to bars
    for i, (_, row) in enumerate(country_stats.iterrows()):
        if row["fraud_rate"] > 0:
            ax.text(row["fraud_rate"] + 0.05, i, f"{row['fraud_rate']}%",
                    va="center", fontsize=8, color=MID_GRAY)

    fig.tight_layout()
    save_fig(fig, "05_country_distribution")


# ── Section 3: Feature Signal Analysis ───────────────────────────────────────

def plot_feature_signal(df):
    """
    For each binary risk flag, compare fraud rate in flagged vs. unflagged transactions.

    This is the most important EDA chart for validating feature engineering.
    If a feature flag has the same fraud rate in both groups, it's not
    providing useful signal to the model. Features should show a clear
    lift in fraud rate when the flag is 1.

    Outputs:
      outputs/eda/06_feature_signal.png
    """
    section("6. Feature Signal Analysis")

    if "isFraud" not in df.columns:
        print("  Skipped: no isFraud labels in dataset")
        return

    # Binary features to evaluate — must already be in the DataFrame
    binary_features = [
        "balance_drained",
        "is_large_transaction",
        "is_late_night",
        "is_high_risk_country",
        "is_high_risk_type",
    ]

    # Only include features that actually exist in this DataFrame
    binary_features = [f for f in binary_features if f in df.columns]

    results = []
    for feat in binary_features:
        # Fraud rate when feature = 1 vs. feature = 0
        rate_flagged  = df[df[feat] == 1]["isFraud"].mean() * 100
        rate_baseline = df[df[feat] == 0]["isFraud"].mean() * 100
        lift = rate_flagged / rate_baseline if rate_baseline > 0 else 0

        results.append({
            "Feature":         feat,
            "Fraud Rate (flag=1)": round(rate_flagged, 2),
            "Fraud Rate (flag=0)": round(rate_baseline, 2),
            "Lift":            round(lift, 1),
        })
        print(f"  {feat:30s} flagged={rate_flagged:.2f}%  baseline={rate_baseline:.2f}%  lift={lift:.1f}x")

    results_df = pd.DataFrame(results)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Left panel: fraud rate comparison (flagged vs. not flagged)
    ax = axes[0]
    x = np.arange(len(results_df))
    width = 0.35

    bars1 = ax.bar(x - width / 2, results_df["Fraud Rate (flag=0)"],
                   width, label="Feature = 0 (not flagged)", color=SECONDARY, alpha=0.8)
    bars2 = ax.bar(x + width / 2, results_df["Fraud Rate (flag=1)"],
                   width, label="Feature = 1 (flagged)", color=RED, alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(results_df["Feature"], rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Fraud Rate (%)")
    ax.set_title("Fraud Rate by Feature Flag", fontweight="bold")
    ax.legend(fontsize=8)

    # Right panel: lift ratio (how much more likely to be fraud when flagged)
    ax = axes[1]
    lift_colors = [GREEN if l >= 3 else GOLD if l >= 1.5 else RED
                   for l in results_df["Lift"]]
    ax.bar(results_df["Feature"], results_df["Lift"],
           color=lift_colors, alpha=0.85, edgecolor="white")

    # Reference line at lift = 1.0 (no signal)
    ax.axhline(1.0, color=MID_GRAY, linestyle="--", alpha=0.7, linewidth=1.5,
               label="Lift = 1.0 (no signal)")

    ax.set_xticklabels(results_df["Feature"], rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Lift (fraud rate when flagged / baseline)")
    ax.set_title("Feature Lift Ratio\n(higher = stronger fraud signal)", fontweight="bold")
    ax.legend(fontsize=8)

    # Add lift value labels on bars
    for bar, lift in zip(ax.patches, results_df["Lift"]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.05,
                f"{lift:.1f}x", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    save_fig(fig, "06_feature_signal")

    return results_df


# ── Section 4: Risk Score Distribution ───────────────────────────────────────

def plot_risk_score_distribution(scored):
    """
    Histogram of Isolation Forest risk scores, colored by risk tier.

    Validates that the model is producing a meaningful spread of scores
    rather than clustering everything at one end. Also shows whether the
    HIGH/MEDIUM/LOW tier thresholds are splitting the population sensibly.

    If all scores pile up near 0 or 100, the contamination parameter
    may need recalibration.

    Outputs:
      outputs/eda/07_risk_score_distribution.png
    """
    section("7. Risk Score Distribution")

    if "risk_score" not in scored.columns:
        print("  Skipped: risk_score column not found (run anomaly_detection.py first)")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Left panel: full risk score histogram colored by tier
    ax = axes[0]
    # Color each bar segment by which tier it falls in
    bins = np.linspace(0, 100, 41)  # 40 bins across 0–100
    for tier, color, lo, hi in [
        ("LOW",    GREEN,  0,  45),
        ("MEDIUM", GOLD,  45,  75),
        ("HIGH",   RED,   75, 100),
    ]:
        mask = (scored["risk_score"] >= lo) & (scored["risk_score"] < hi)
        ax.hist(scored.loc[mask, "risk_score"], bins=bins,
                color=color, alpha=0.75, label=f"{tier} ({mask.sum():,})", edgecolor="white")

    # Threshold reference lines
    ax.axvline(45, color=GOLD, linestyle="--", alpha=0.8, linewidth=1.5, label="MEDIUM threshold (45)")
    ax.axvline(75, color=RED,  linestyle="--", alpha=0.8, linewidth=1.5, label="HIGH threshold (75)")

    ax.set_xlabel("Risk Score (0 = normal, 100 = most anomalous)")
    ax.set_ylabel("Transaction Count")
    ax.set_title("Risk Score Distribution by Tier", fontweight="bold")
    ax.legend(fontsize=8)

    # Right panel: fraud label overlap with risk tiers (if labels available)
    ax = axes[1]
    if "isFraud" in scored.columns:
        tier_order = ["LOW", "MEDIUM", "HIGH"]
        tier_totals = scored["risk_tier"].value_counts().reindex(tier_order, fill_value=0)
        tier_fraud  = (scored[scored["isFraud"] == 1]["risk_tier"]
                       .value_counts().reindex(tier_order, fill_value=0))
        fraud_rates = (tier_fraud / tier_totals * 100).fillna(0).round(1)

        colors = [GREEN, GOLD, RED]
        bars = ax.bar(tier_order, fraud_rates.values, color=colors,
                      alpha=0.85, edgecolor="white", width=0.5)

        for bar, rate in zip(bars, fraud_rates.values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.1,
                    f"{rate:.1f}%", ha="center", va="bottom", fontsize=10,
                    fontweight="bold")

        ax.set_ylabel("Fraud Rate (%)")
        ax.set_title("Fraud Rate by Risk Tier\n(validates tier calibration)", fontweight="bold")
        ax.set_xlabel("Risk Tier")
    else:
        # No fraud labels — show tier counts instead
        tier_counts = scored["risk_tier"].value_counts().reindex(
            ["LOW", "MEDIUM", "HIGH"], fill_value=0)
        ax.bar(["LOW", "MEDIUM", "HIGH"], tier_counts.values,
               color=[GREEN, GOLD, RED], alpha=0.85, edgecolor="white", width=0.5)
        ax.set_ylabel("Transaction Count")
        ax.set_title("Transaction Count by Risk Tier", fontweight="bold")

    fig.tight_layout()
    save_fig(fig, "07_risk_score_distribution")

    # Print tier summary stats
    tier_summary = scored.groupby("risk_tier")["risk_score"].describe()[
        ["count", "mean", "min", "max"]].round(1)
    print(tier_summary.to_string())


# ── Section 5: Summary Statistics Table ──────────────────────────────────────

def generate_summary_table(raw, scored):
    """
    Produce a concise summary statistics table and save it as CSV.

    This table is the EDA's "executive summary" — the 10–15 numbers an
    analyst or reviewer needs to understand the dataset at a glance before
    diving into individual charts.

    Args:
        raw:    Raw transaction DataFrame.
        scored: Scored transaction DataFrame with model outputs.

    Returns:
        pd.DataFrame: Summary statistics table.
    """
    section("Summary Statistics Table")

    n_fraud   = int(raw["isFraud"].sum()) if "isFraud" in raw.columns else 0
    n_total   = len(raw)
    fraud_rate = n_fraud / n_total * 100 if n_total > 0 else 0

    # Scored-data stats (may not exist if anomaly_detection hasn't run)
    n_flagged  = int(scored["anomaly_flag"].sum()) if "anomaly_flag" in scored.columns else "N/A"
    n_high     = int((scored["risk_tier"] == "HIGH").sum()) if "risk_tier" in scored.columns else "N/A"
    n_medium   = int((scored["risk_tier"] == "MEDIUM").sum()) if "risk_tier" in scored.columns else "N/A"
    avg_score  = round(scored["risk_score"].mean(), 1) if "risk_score" in scored.columns else "N/A"

    # Fraud captured: labeled fraud in the HIGH-risk tier
    if "isFraud" in scored.columns and "risk_tier" in scored.columns:
        captured = int(scored[(scored["isFraud"] == 1) & (scored["risk_tier"] == "HIGH")].shape[0])
        capture_rate = f"{captured / max(n_fraud, 1) * 100:.1f}%"
    else:
        captured, capture_rate = "N/A", "N/A"

    summary = pd.DataFrame({
        "Metric": [
            "Total transactions",
            "Labeled fraud cases",
            "Overall fraud rate",
            "Flagged by Isolation Forest",
            "HIGH risk tier",
            "MEDIUM risk tier",
            "Average risk score",
            "Labeled fraud in HIGH tier",
            "Fraud capture rate (HIGH tier)",
            "Unique transaction types",
            "Unique countries",
            "Median transaction amount",
            "Max transaction amount",
            "Late-night transactions (0–4AM)",
            "High-risk country transactions",
        ],
        "Value": [
            f"{n_total:,}",
            f"{n_fraud:,}",
            f"{fraud_rate:.2f}%",
            f"{n_flagged:,}" if isinstance(n_flagged, int) else n_flagged,
            f"{n_high:,}"    if isinstance(n_high, int)    else n_high,
            f"{n_medium:,}"  if isinstance(n_medium, int)  else n_medium,
            str(avg_score),
            f"{captured:,}"  if isinstance(captured, int)  else captured,
            capture_rate,
            str(raw["type"].nunique()),
            str(raw["country"].nunique()),
            f"${raw['amount'].median():,.2f}",
            f"${raw['amount'].max():,.2f}",
            f"{raw['hour'].between(0,4).sum():,}",
            (f"{raw['country'].isin(config.HIGH_RISK_COUNTRIES).sum():,}"
             if "country" in raw.columns else "N/A"),
        ]
    })

    print(summary.to_string(index=False))
    summary.to_csv(os.path.join(EDA_DIR, "eda_summary.csv"), index=False)
    print(f"\nSummary saved to {EDA_DIR}/eda_summary.csv")

    return summary


# ── Main orchestration ────────────────────────────────────────────────────────

def run_eda():
    """
    Run the full EDA pipeline in sequence.

    Loads both raw and scored data, then generates all charts and tables.
    Safe to run with only raw data available (scored-data charts are skipped
    with a warning rather than crashing).

    All outputs are written to outputs/eda/.
    """
    print("\n" + "="*60)
    print("  FRAUD PIPELINE — EXPLORATORY DATA ANALYSIS")
    print("="*60)

    # Load both data sources
    raw, scored = load_pipeline_data()

    # ── Section 1: Data quality ──────────────────────────────────────────────
    plot_data_quality(raw)

    # ── Section 2: Distributions ─────────────────────────────────────────────
    plot_transaction_type_distribution(raw)
    plot_amount_distribution(raw)
    plot_hourly_activity(raw)
    plot_country_distribution(raw)

    # ── Section 3: Feature signal (requires engineered features in scored) ───
    plot_feature_signal(scored)

    # ── Section 4: Model output ───────────────────────────────────────────────
    plot_risk_score_distribution(scored)

    # ── Section 5: Summary table ──────────────────────────────────────────────
    generate_summary_table(raw, scored)

    print(f"\n{'='*60}")
    print(f"  EDA COMPLETE — outputs saved to {EDA_DIR}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_eda()
