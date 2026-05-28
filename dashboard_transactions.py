"""Transactions review tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from dashboard_tables import interactive_table


def render_transactions_tab(scored: pd.DataFrame) -> None:
    st.markdown(
        "Build your review queue step by step. **Risk score** ranks how unusual a transaction is (0–100). "
        "**Risk tier** groups cases for triage. **Anomaly flag** marks the top ~2% statistical outliers, "
        "which is separate from tier assignment."
    )
    st.markdown(
        f"**What to look for:** Start with HIGH tier and scores ≥ {config.RISK_TIER_HIGH}. "
        "Prioritize large amounts, balance drained, late-night activity, and high-risk countries. "
        "Use labeled fraud only to validate the model, not as proof of a filing."
    )

    base = scored.copy()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        tiers = st.multiselect(
            "Risk tier",
            ["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM"],
            key="txn_tiers",
        )
    with c2:
        types = st.multiselect(
            "Transaction type",
            sorted(base["type"].dropna().unique()) if "type" in base.columns else [],
            key="txn_types",
        )
    with c3:
        countries = st.multiselect(
            "Country",
            sorted(base["country"].dropna().unique()) if "country" in base.columns else [],
            key="txn_countries",
        )
    with c4:
        min_score = st.slider(
            "Minimum risk score",
            0.0,
            100.0,
            0.0,
            5.0,
            key="txn_min_score",
        )

    c5, c6, c7 = st.columns(3)
    with c5:
        only_anomaly = st.checkbox("Only anomaly flags", value=False, key="txn_anomaly")
    with c6:
        only_drained = st.checkbox("Only balance drained", value=False, key="txn_drained")
    with c7:
        only_late = st.checkbox("Only late night (0–4)", value=False, key="txn_late")

    filtered = base
    if tiers and "risk_tier" in filtered.columns:
        filtered = filtered[filtered["risk_tier"].isin(tiers)]
    if types and "type" in filtered.columns:
        filtered = filtered[filtered["type"].isin(types)]
    if countries and "country" in filtered.columns:
        filtered = filtered[filtered["country"].isin(countries)]
    if "risk_score" in filtered.columns:
        filtered = filtered[filtered["risk_score"] >= min_score]
    if only_anomaly and "anomaly_flag" in filtered.columns:
        filtered = filtered[filtered["anomaly_flag"] == 1]
    if only_drained and "balance_drained" in filtered.columns:
        filtered = filtered[filtered["balance_drained"] == 1]
    if only_late and "is_late_night" in filtered.columns:
        filtered = filtered[filtered["is_late_night"] == 1]

    m1, m2, m3 = st.columns(3)
    m1.metric("Matching transactions", f"{len(filtered):,}")
    if "amount" in filtered.columns:
        m2.metric("Total amount", f"${filtered['amount'].sum():,.0f}")
    if "isFraud" in filtered.columns and len(filtered):
        m3.metric("Labeled fraud in queue", f"{int(filtered['isFraud'].sum()):,}")

    show_cols = [
        c for c in [
            "transaction_id", "risk_score", "risk_tier", "anomaly_flag", "type",
            "amount", "country", "hour", "balance_drained", "is_late_night",
            "is_high_risk_country", "isFraud",
        ]
        if c in filtered.columns
    ]

    interactive_table(
        filtered[show_cols],
        key_prefix="txn_queue",
        title="Review queue",
        help_text="Search any field, filter tiers or countries, and sort by risk score or amount.",
        tier_column="risk_tier",
        filter_columns=["risk_tier", "type", "country"],
        default_sort="risk_score",
        sort_desc=True,
        max_rows=500,
    )
