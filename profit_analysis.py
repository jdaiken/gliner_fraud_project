"""
profit_analysis.py
------------------
Financial impact / profit-loss style metrics for analyst review.

In PaySim-style data we approximate:
  - Outflow: money leaving origin accounts (balance decrease)
  - Inflow:  money arriving at destination accounts
  - Fraud loss: transaction amounts tied to labeled fraud (research label)
  - At-risk exposure: amounts in HIGH / MEDIUM risk tiers
"""

from __future__ import annotations

import pandas as pd

import config


def add_profit_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-transaction financial impact fields."""
    out = df.copy()
    out["origin_balance_change"] = out["newbalanceOrig"] - out["oldbalanceOrg"]
    out["dest_balance_change"] = out["newbalanceDest"] - out["oldbalanceDest"]
    out["outflow_amount"] = out["origin_balance_change"].clip(upper=0).abs()
    out["inflow_amount"] = out["dest_balance_change"].clip(lower=0)
    out["net_transfer"] = out["amount"]
    return out


def portfolio_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Single-row portfolio financial summary."""
    total_volume = df["amount"].sum()
    total_outflow = df["outflow_amount"].sum() if "outflow_amount" in df.columns else None
    total_inflow = df["inflow_amount"].sum() if "inflow_amount" in df.columns else None

    rows = [
        ("Total transaction volume ($)", round(total_volume, 2)),
        ("Total origin outflow ($)", round(total_outflow, 2) if total_outflow is not None else None),
        ("Total destination inflow ($)", round(total_inflow, 2) if total_inflow is not None else None),
        ("Average transaction size ($)", round(df["amount"].mean(), 2)),
        ("Median transaction size ($)", round(df["amount"].median(), 2)),
    ]

    if "isFraud" in df.columns:
        fraud = df[df["isFraud"] == 1]
        rows.append(("Labeled fraud transaction count", int(len(fraud))))
        rows.append(("Labeled fraud loss ($)", round(fraud["amount"].sum(), 2)))
        rows.append(
            ("Fraud as % of total volume", round(100 * fraud["amount"].sum() / total_volume, 2) if total_volume else 0)
        )

    if "risk_tier" in df.columns:
        for tier in ("HIGH", "MEDIUM", "LOW"):
            sub = df[df["risk_tier"] == tier]
            rows.append((f"{tier} risk — transaction count", int(len(sub))))
            rows.append((f"{tier} risk — dollar exposure ($)", round(sub["amount"].sum(), 2)))

    return pd.DataFrame(rows, columns=["metric", "value"])


def aggregate_dimension(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Summarize volume, outflow, and fraud loss by a dimension (type, country, tier)."""
    if dimension not in df.columns:
        return pd.DataFrame()

    g = df.groupby(dimension, dropna=False)
    result = g.agg(
        transaction_count=("amount", "count"),
        total_volume=("amount", "sum"),
        avg_transaction=("amount", "mean"),
    )
    if "outflow_amount" in df.columns:
        result["total_outflow"] = g["outflow_amount"].sum()
    if "isFraud" in df.columns:
        result["fraud_count"] = g["isFraud"].sum()
        fraud_loss = (
            df[df["isFraud"] == 1].groupby(dimension)["amount"].sum()
        )
        result["fraud_loss"] = fraud_loss.reindex(result.index, fill_value=0)

    result = result.reset_index()
    for col in ("total_volume", "avg_transaction", "total_outflow", "fraud_loss"):
        if col in result.columns:
            result[col] = result[col].round(2)
    return result.sort_values("total_volume", ascending=False)


def top_account_exposure(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    """Accounts with largest origin outflow (potential loss exposure)."""
    if "nameOrig" not in df.columns:
        return pd.DataFrame()

    cols = ["outflow_amount", "amount"]
    if "isFraud" in df.columns:
        cols.append("isFraud")
    if "risk_tier" in df.columns:
        cols.append("risk_tier")

    acct = (
        df.groupby("nameOrig")
        .agg(
            transactions=("amount", "count"),
            total_outflow=("outflow_amount", "sum"),
            total_volume=("amount", "sum"),
            fraud_count=("isFraud", "sum") if "isFraud" in df.columns else ("amount", "count"),
            high_risk_count=("risk_tier", lambda s: (s == "HIGH").sum()) if "risk_tier" in df.columns else ("amount", "count"),
        )
        .reset_index()
        .rename(columns={"nameOrig": "account_id"})
    )
    acct["total_outflow"] = acct["total_outflow"].round(2)
    acct["total_volume"] = acct["total_volume"].round(2)
    return acct.nlargest(n, "total_outflow")


def run_profit_analysis(
    input_path=None,
    detail_path=None,
    summary_path=None,
) -> dict[str, pd.DataFrame]:
    """
    Compute financial impact tables from scored transactions.

    Returns:
        dict of output DataFrames written to CSV.
    """
    input_path = input_path or config.SCORED_CSV
    detail_path = detail_path or config.PROFIT_DETAIL_CSV
    summary_path = summary_path or config.PROFIT_SUMMARY_CSV

    df = pd.read_csv(input_path)
    df = add_profit_columns(df)

    outputs = {
        "summary": portfolio_summary(df),
        "by_tier": aggregate_dimension(df, "risk_tier") if "risk_tier" in df.columns else pd.DataFrame(),
        "by_type": aggregate_dimension(df, "type"),
        "by_country": aggregate_dimension(df, "country") if "country" in df.columns else pd.DataFrame(),
        "top_accounts": top_account_exposure(df),
    }

    config.ensure_dirs()
    detail_cols = [
        c
        for c in [
            "transaction_id",
            "type",
            "amount",
            "risk_score",
            "risk_tier",
            "country",
            "origin_balance_change",
            "dest_balance_change",
            "outflow_amount",
            "inflow_amount",
            "isFraud",
            "nameOrig",
            "nameDest",
        ]
        if c in df.columns
    ]
    df[detail_cols].to_csv(detail_path, index=False)
    outputs["summary"].to_csv(summary_path, index=False)

    for name, path in [
        ("by_tier", config.PROFIT_BY_TIER_CSV),
        ("by_type", config.PROFIT_BY_TYPE_CSV),
        ("by_country", config.PROFIT_BY_COUNTRY_CSV),
        ("top_accounts", config.PROFIT_TOP_ACCOUNTS_CSV),
    ]:
        if not outputs[name].empty:
            outputs[name].to_csv(path, index=False)

    print(f"Profit / financial impact analysis saved:")
    print(f"  {summary_path}")
    print(f"  {detail_path}")
    if not outputs["summary"].empty:
        fraud_row = outputs["summary"][outputs["summary"]["metric"] == "Labeled fraud loss ($)"]
        if not fraud_row.empty:
            print(f"  Labeled fraud loss: ${fraud_row.iloc[0]['value']:,.2f}")

    return outputs


if __name__ == "__main__":
    run_profit_analysis()
