"""
anomaly_detection.py
--------------------
Scores every transaction for anomaly risk using Isolation Forest,
then assigns each row a normalized 0–100 risk score and a tier label
(HIGH / MEDIUM / LOW).

Risk scores are calibrated using saved percentile bounds so scores stay
comparable across pipeline runs and batch sizes.
"""

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import config


def load_data(path=None):
    """Load transaction CSV and print a quick row count for verification."""
    path = path or config.TRANSACTIONS_CSV
    df = pd.read_csv(path)
    print(f"Loaded {len(df):,} transactions")
    return df


def encode_transaction_type(series):
    """Map transaction type to a fixed integer code (stable across runs)."""
    return series.map(config.TYPE_ENCODING).fillna(config.UNKNOWN_TYPE_CODE).astype(int)


def engineer_features(df):
    """Create risk-relevant features from raw transaction fields."""
    df = df.copy()

    df["balance_delta"] = df["oldbalanceOrg"] - df["newbalanceOrig"]
    df["balance_drained"] = (
        (df["oldbalanceOrg"] > 0) & (df["newbalanceOrig"] == 0)
    ).astype(int)

    df["amount_to_balance_ratio"] = df["amount"] / (df["oldbalanceOrg"] + 1)
    df["amount_to_balance_ratio"] = df["amount_to_balance_ratio"].clip(upper=100)

    df["is_high_risk_type"] = df["type"].isin(config.FRAUD_TYPES).astype(int)
    df["is_late_night"] = df["hour"].isin(config.LATE_NIGHT_HOURS).astype(int)
    df["is_high_risk_country"] = df["country"].isin(config.HIGH_RISK_COUNTRIES).astype(int)
    df["is_large_transaction"] = (
        df["amount"] > config.LARGE_TRANSACTION_THRESHOLD
    ).astype(int)

    df["type_encoded"] = encode_transaction_type(df["type"])
    return df


def _save_type_encoding():
    """Persist type encoding mapping for auditability."""
    config.ensure_dirs()
    with open(config.TYPE_ENCODING_JSON, "w", encoding="utf-8") as f:
        json.dump(config.TYPE_ENCODING, f, indent=2)


def _load_calibration():
    """Load saved risk score calibration if present."""
    if not config.RISK_CALIBRATION_JSON.exists():
        return None
    with open(config.RISK_CALIBRATION_JSON, encoding="utf-8") as f:
        return json.load(f)


def _save_calibration(score_low, score_high):
    """Save percentile bounds used for risk_score normalization."""
    config.ensure_dirs()
    payload = {
        "score_low": float(score_low),
        "score_high": float(score_high),
        "percentiles": list(config.RISK_SCORE_PERCENTILES),
    }
    with open(config.RISK_CALIBRATION_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def decision_to_risk_score(raw_scores, calibration=None):
    """
    Map Isolation Forest decision_function values to 0–100 risk scores.

    Uses saved percentile bounds when provided; otherwise derives bounds from
    the current batch and persists them for subsequent runs.
    """
    if calibration is None:
        p_low, p_high = config.RISK_SCORE_PERCENTILES
        score_low = float(np.percentile(raw_scores, p_low))
        score_high = float(np.percentile(raw_scores, p_high))
        _save_calibration(score_low, score_high)
    else:
        score_low = calibration["score_low"]
        score_high = calibration["score_high"]

    if score_high <= score_low:
        return np.full(len(raw_scores), 50.0)

    clipped = np.clip(raw_scores, score_low, score_high)
    normalized = (clipped - score_low) / (score_high - score_low)
    return np.round(100 * (1 - normalized), 1)


def run_isolation_forest(df, refit_calibration=False):
    """
    Fit Isolation Forest, score transactions, and assign risk columns.

    Adds anomaly_flag and risk_score. Calibration artifacts are written to
    outputs/model_artifacts/ unless refit_calibration is False and artifacts exist.
    """
    X = df[config.FEATURE_COLS].fillna(0)

    print("Running Isolation Forest...")
    clf = IsolationForest(**config.ISOLATION_FOREST)
    clf.fit(X)

    df["anomaly_flag"] = (clf.predict(X) == -1).astype(int)

    raw_scores = clf.decision_function(X)
    calibration = None if refit_calibration else _load_calibration()
    df["risk_score"] = decision_to_risk_score(raw_scores, calibration=calibration)

    _save_type_encoding()
    return df


def assign_risk_tier(score):
    """Map a continuous risk score to HIGH / MEDIUM / LOW."""
    if score >= config.RISK_TIER_HIGH:
        return "HIGH"
    if score >= config.RISK_TIER_MEDIUM:
        return "MEDIUM"
    return "LOW"


def run_detection(path=None, refit_calibration=True):
    """
    Full detection pipeline: load → feature engineering → scoring → save.

    Args:
        path: Path to the input transactions CSV.
        refit_calibration: If True, recompute and save score percentiles from this batch.
                           If False, reuse saved calibration when available.

    Returns:
        pd.DataFrame: Fully scored DataFrame with all feature and score columns.
    """
    path = path or config.TRANSACTIONS_CSV
    df = load_data(path)
    df = engineer_features(df)
    df = run_isolation_forest(df, refit_calibration=refit_calibration)
    df["risk_tier"] = df["risk_score"].apply(assign_risk_tier)

    flagged = df[df["anomaly_flag"] == 1]
    print(f"\nAnomaly Detection Results:")
    print(f"  Total transactions : {len(df):,}")
    print(f"  Flagged anomalies  : {len(flagged):,} ({len(flagged)/len(df):.2%})")
    print(f"  HIGH risk          : {(df['risk_tier']=='HIGH').sum():,}")
    print(f"  MEDIUM risk        : {(df['risk_tier']=='MEDIUM').sum():,}")

    if "isFraud" in df.columns:
        overlap = df[(df["anomaly_flag"] == 1) & (df["isFraud"] == 1)]
        print(f"\n  Labeled fraud captured : {len(overlap)} of {df['isFraud'].sum()}")

    config.ensure_dirs()
    df.to_csv(config.SCORED_CSV, index=False)
    print(f"\nScored transactions saved to {config.SCORED_CSV}")

    return df


if __name__ == "__main__":
    run_detection()
