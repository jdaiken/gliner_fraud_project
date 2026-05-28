"""
Searchable, filterable, human-labeled tables with heatmap styling.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

COLUMN_LABELS: dict[str, str] = {
    "transaction_id": "Transaction ID",
    "risk_score": "Risk score",
    "risk_tier": "Risk tier",
    "anomaly_flag": "Anomaly flag",
    "type": "Transaction type",
    "transaction_type": "Transaction type",
    "amount": "Amount ($)",
    "country": "Country",
    "hour": "Hour of day",
    "balance_drained": "Balance drained",
    "is_late_night": "Late night",
    "is_high_risk_country": "High-risk country",
    "isFraud": "Labeled fraud",
    "nameOrig": "Origin account",
    "nameDest": "Destination account",
    "country_name": "Country name",
    "transactions": "Transaction count",
    "total_volume": "Total volume ($)",
    "avg_amount": "Average amount ($)",
    "fraud_count": "Fraud count",
    "fraud_loss": "Fraud loss ($)",
    "fraud_rate_pct": "Fraud rate (%)",
    "high_risk_count": "HIGH-tier count",
    "high_risk_volume": "HIGH-tier volume ($)",
    "sar_id": "SAR ID",
    "topic_id": "Topic #",
    "topic_label": "Topic theme",
    "top_terms": "Top terms",
    "document_count": "Narratives in topic",
    "share_pct": "Share of corpus (%)",
    "dominant_topic": "Dominant topic #",
    "topic_score": "Topic strength",
    "topic_top_terms": "Topic keywords",
    "word": "Word",
    "count": "Count",
    "z_score": "Z-score",
    "weight": "Weight",
    "extracted_accounts": "Extracted accounts",
    "extracted_amounts": "Extracted amounts",
    "extracted_countries": "Extracted countries",
    "extracted_tx_types": "Extracted transaction types",
    "extracted_time_flags": "Extracted time flags",
    "extracted_risk_factors": "Extracted risk factors",
    "extracted_balances": "Extracted balances",
    "amount_reconciled": "Amount matches source",
    "country_reconciled": "Country matches source",
    "extraction_method": "Extraction method",
    "metric": "Metric",
    "value": "Value",
    "risk_tier": "Risk tier",
    "total_volume": "Total volume ($)",
    "fraud_rate": "Fraud rate",
    "tier": "Risk tier",
    "n_topics": "Number of topics",
    "z_threshold": "Z-score threshold",
    "stop_words": "Stop words",
    "total_outflow": "Total outflow ($)",
    "avg_transaction": "Average transaction ($)",
    "outflow_amount": "Outflow amount ($)",
    "step": "Simulation hour",
    "hour": "Hour",
}


def label_dataframe(df: pd.DataFrame, extra: dict[str, str] | None = None) -> pd.DataFrame:
    mapping = {**COLUMN_LABELS, **(extra or {})}
    return df.rename(columns={c: mapping.get(c, c.replace("_", " ").title()) for c in df.columns})


def _search_mask(df: pd.DataFrame, query: str) -> pd.Series:
    q = query.strip().lower()
    if not q:
        return pd.Series(True, index=df.index)
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        mask |= df[col].fillna("").astype(str).str.lower().str.contains(q, regex=False)
    return mask


def _style_heatmap(
    df: pd.DataFrame,
    numeric_cols: list[str],
    tier_col: str | None = "risk_tier",
) -> pd.io.formats.style.Styler:
    tier_colors = {"HIGH": "#FCEAEA", "MEDIUM": "#FFF4E0", "LOW": "#E6F4F1"}

    def row_style(row):
        styles = [""] * len(row)
        if tier_col and tier_col in row.index:
            bg = tier_colors.get(str(row[tier_col]), "")
            if bg:
                styles = [f"background-color: {bg}"] * len(row)
        return styles

    styled = df.style.apply(row_style, axis=1)
    for col in numeric_cols:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            if col == "risk_score":
                styled = styled.background_gradient(subset=[col], cmap="YlOrRd", vmin=0, vmax=100)
            elif "rate" in col or "pct" in col or col.endswith("%"):
                styled = styled.background_gradient(subset=[col], cmap="YlGnBu", vmin=0)
            elif "amount" in col or "volume" in col or "loss" in col:
                styled = styled.background_gradient(subset=[col], cmap="Blues")
            elif col in ("z_score", "topic_score", "weight", "count"):
                styled = styled.background_gradient(subset=[col], cmap="Oranges")
    return styled


def interactive_table(
    df: pd.DataFrame,
    *,
    key_prefix: str,
    title: str = "",
    help_text: str = "",
    tier_column: str | None = "risk_tier",
    filter_columns: list[str] | None = None,
    default_sort: str | None = None,
    sort_desc: bool = True,
    max_rows: int = 500,
    heatmap_numeric: bool = True,
) -> None:
    """Filter, search, sort, and display a labeled heatmap table."""
    if df is None or df.empty:
        st.info("No rows to display.")
        return

    if title:
        st.markdown(f"##### {title}")
    if help_text:
        st.caption(help_text)

    working = df.copy()
    fcols = filter_columns or [
        c for c in ("risk_tier", "type", "transaction_type", "country", "topic_label")
        if c in working.columns
    ]

    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        search = st.text_input(
            "Search table",
            key=f"{key_prefix}_search",
            placeholder="Text search across all columns…",
        )
    with fc2:
        filters = {}
        if fcols:
            pick = st.multiselect(
                "Filter by column",
                options=fcols,
                default=[],
                key=f"{key_prefix}_filter_cols",
                format_func=lambda c: COLUMN_LABELS.get(c, c.replace("_", " ").title()),
            )
            for col in pick:
                opts = sorted(working[col].dropna().astype(str).unique().tolist())
                filters[col] = st.multiselect(
                    COLUMN_LABELS.get(col, col),
                    options=opts,
                    key=f"{key_prefix}_f_{col}",
                )
    with fc3:
        sort_options = list(working.columns)
        sort_idx = sort_options.index(default_sort) if default_sort in sort_options else 0
        sort_col = st.selectbox(
            "Sort by",
            options=sort_options,
            index=sort_idx,
            format_func=lambda c: COLUMN_LABELS.get(c, c.replace("_", " ").title()),
            key=f"{key_prefix}_sort",
        )
        ascending = st.checkbox("Ascending", value=not sort_desc, key=f"{key_prefix}_asc")

    if search:
        working = working[_search_mask(working, search)]
    for col, vals in filters.items():
        if vals:
            working = working[working[col].astype(str).isin(vals)]

    if working.empty:
        st.warning("No rows match your filters.")
        return

    if sort_col in working.columns:
        working = working.sort_values(sort_col, ascending=ascending, na_position="last")

    st.caption(f"Showing {min(len(working), max_rows):,} of {len(working):,} rows")
    view = label_dataframe(working.head(max_rows))

    numeric = [c for c in view.columns if pd.api.types.is_numeric_dtype(view[c])]
    tier_labeled = COLUMN_LABELS.get(tier_column, tier_column) if tier_column else None

    if heatmap_numeric and numeric:
        try:
            st.dataframe(
                _style_heatmap(view, numeric, tier_col=tier_labeled if tier_labeled in view.columns else None),
                width="stretch",
                hide_index=True,
            )
        except Exception:
            st.dataframe(view, width="stretch", hide_index=True)
    else:
        st.dataframe(view, width="stretch", hide_index=True)
