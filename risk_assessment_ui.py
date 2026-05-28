"""
Interactive controls for the Risk Assessment report tab.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_cover import _fmt_money, _pct
from dashboard_tables import interactive_table
from dashboard_theme import apply_plotly_theme, tier_color_discrete

TIER_ORDER = ["HIGH", "MEDIUM", "LOW"]
TIER_LABELS = {"HIGH": "High risk", "MEDIUM": "Medium risk", "LOW": "Low risk"}

SECTION_OPTIONS = [
    "Executive summary",
    "Industry context",
    "Monitoring findings",
    "Typology drill-down",
    "Geographic risk",
    "Regulatory alignment",
    "Recommended actions",
]

DRILLDOWN_COLS = [
    "transaction_id",
    "type",
    "risk_tier",
    "risk_score",
    "amount",
    "country",
    "anomaly_flag",
    "balance_drained",
    "is_high_risk_country",
    "isFraud",
]


def filter_scored_for_assessment(scored: pd.DataFrame, settings: dict) -> pd.DataFrame:
    out = scored.copy()
    tiers = settings.get("tiers") or TIER_ORDER
    if "risk_tier" in out.columns and tiers:
        out = out[out["risk_tier"].astype(str).str.upper().isin([t.upper() for t in tiers])]

    types = settings.get("types") or []
    if types and "type" in out.columns:
        out = out[out["type"].astype(str).isin(types)]

    countries = settings.get("countries") or []
    if countries and "country" in out.columns:
        out = out[out["country"].astype(str).isin(countries)]

    min_score = settings.get("min_score", 0)
    if "risk_score" in out.columns and min_score > 0:
        out = out[out["risk_score"] >= min_score]

    if settings.get("high_risk_country_only") and "is_high_risk_country" in out.columns:
        out = out[out["is_high_risk_country"] == 1]

    if settings.get("anomaly_only") and "anomaly_flag" in out.columns:
        out = out[out["anomaly_flag"] == 1]

    search = (settings.get("search") or "").strip().lower()
    if search and len(search) >= 2:
        mask = pd.Series(False, index=out.index)
        for col in out.columns:
            mask |= out[col].fillna("").astype(str).str.lower().str.contains(search, regex=False)
        out = out[mask]

    return out


def render_assessment_controls(scored: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Filters and section toggles for the live risk assessment report."""
    with st.expander("Customize report view", expanded=True):
        st.caption(
            "Scope the assessment to specific tiers, typologies, or jurisdictions. "
            "Exports use the filtered population shown below."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            tiers = st.multiselect(
                "Risk tiers",
                options=TIER_ORDER,
                default=TIER_ORDER,
                format_func=lambda t: TIER_LABELS.get(t, t),
                key="ra_tiers",
            )
            type_opts = (
                sorted(scored["type"].dropna().astype(str).unique().tolist())
                if "type" in scored.columns
                else []
            )
            types = st.multiselect(
                "Transaction types",
                options=type_opts,
                default=[],
                key="ra_types",
            )
        with c2:
            countries = []
            if "country" in scored.columns:
                country_opts = sorted(scored["country"].dropna().astype(str).unique().tolist())
                countries = st.multiselect(
                    "Countries",
                    options=country_opts,
                    default=[],
                    key="ra_countries",
                )
            min_score = 0
            if "risk_score" in scored.columns:
                min_score = st.slider(
                    "Minimum risk score",
                    0,
                    100,
                    0,
                    5,
                    key="ra_min_score",
                )
        with c3:
            high_risk_country_only = st.checkbox(
                "High-risk jurisdictions only",
                value=False,
                key="ra_hr_country",
            )
            anomaly_only = st.checkbox(
                "Statistical anomalies only",
                value=False,
                key="ra_anomaly",
            )
            sections = st.multiselect(
                "Report sections",
                options=SECTION_OPTIONS,
                default=SECTION_OPTIONS,
                key="ra_sections",
            )

        search = st.text_input(
            "Search transactions",
            placeholder="ID, account, country, tier…",
            key="ra_search",
        )

    settings = {
        "tiers": tiers,
        "types": types,
        "countries": countries,
        "min_score": min_score,
        "high_risk_country_only": high_risk_country_only,
        "anomaly_only": anomaly_only,
        "search": search,
        "sections": sections,
    }
    filtered = filter_scored_for_assessment(scored, settings)
    st.session_state["ra_filtered_scored"] = filtered
    st.session_state["ra_assessment_settings"] = settings

    if filtered.empty:
        st.warning("No transactions match your report filters. Widen tiers or lower the minimum score.")
    else:
        n = len(filtered)
        n_high = int((filtered["risk_tier"] == "HIGH").sum()) if "risk_tier" in filtered.columns else 0
        vol = filtered["amount"].sum() if "amount" in filtered.columns else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("Transactions in scope", f"{n:,}")
        m2.metric("High-risk tier", f"{n_high:,}")
        m3.metric("Exposure in scope", _fmt_money(vol))

    return filtered, settings


def _typology_summary(scored: pd.DataFrame) -> pd.DataFrame:
    if "type" not in scored.columns:
        return pd.DataFrame()
    agg: dict = {"transactions": ("type", "size")}
    if "amount" in scored.columns:
        agg["total_exposure"] = ("amount", "sum")
    if "risk_score" in scored.columns:
        agg["avg_risk_score"] = ("risk_score", "mean")
    g = scored.groupby("type", as_index=False).agg(**agg)
    if "isFraud" in scored.columns:
        fraud = scored.groupby("type")["isFraud"].mean() * 100
        g["labeled_fraud_rate_pct"] = g["type"].map(fraud).round(1)
    if "risk_tier" in scored.columns:
        high = scored[scored["risk_tier"] == "HIGH"].groupby("type").size()
        g["high_risk_count"] = g["type"].map(high).fillna(0).astype(int)
    sort_col = "high_risk_count" if "high_risk_count" in g.columns else "transactions"
    return g.sort_values(sort_col, ascending=False)


def render_typology_drilldown(scored: pd.DataFrame) -> None:
    """Bar chart and searchable queue by transaction type."""
    if "type" not in scored.columns or scored.empty:
        st.info("Transaction type is not available for drill-down.")
        return

    summary = _typology_summary(scored)
    if summary.empty:
        return

    st.markdown("##### Typology drill-down")
    st.caption(
        "Compare exposure and high-risk counts by transaction type, then open the detail queue for one typology."
    )

    metric = st.radio(
        "Chart metric",
        options=["High-risk count", "Total exposure", "Transaction count", "Labeled fraud rate"],
        horizontal=True,
        key="ra_drill_metric",
    )

    y_col = "high_risk_count"
    title = "High-risk alerts by transaction type"
    if metric == "Total exposure" and "total_exposure" in summary.columns:
        y_col, title = "total_exposure", "Exposure ($) by transaction type"
    elif metric == "Transaction count":
        y_col, title = "transactions", "Transactions by type"
    elif metric == "Labeled fraud rate" and "labeled_fraud_rate_pct" in summary.columns:
        y_col, title = "labeled_fraud_rate_pct", "Labeled fraud rate (%) by transaction type"
    elif y_col not in summary.columns:
        y_col, title = "transactions", "Transactions by transaction type"

    plot_df = summary.sort_values(y_col, ascending=True)
    fig = px.bar(
        plot_df,
        x=y_col,
        y="type",
        orientation="h",
        title=title,
        color=y_col,
        color_continuous_scale=[[0, "#00A9CE"], [1, "#D64545"]],
        text=y_col,
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(coloraxis_showscale=False, yaxis_title="", xaxis_title="")
    st.plotly_chart(apply_plotly_theme(fig, hide_legend=True), width="stretch")

    type_opts = summary["type"].tolist()
    pick = st.selectbox(
        "Drill into transaction type",
        options=type_opts,
        key="ra_drill_type",
    )
    subset = scored[scored["type"].astype(str) == str(pick)].copy()
    if subset.empty:
        st.warning("No rows for this typology.")
        return

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Transactions", f"{len(subset):,}")
    if "risk_tier" in subset.columns:
        d2.metric("High-risk tier", f"{(subset['risk_tier'] == 'HIGH').sum():,}")
    if "amount" in subset.columns:
        d3.metric("Exposure", _fmt_money(subset["amount"].sum()))
    if "isFraud" in subset.columns:
        d4.metric("Labeled fraud rate", f"{_pct(subset['isFraud'].sum(), len(subset)):.1f}%")

    show_cols = [c for c in DRILLDOWN_COLS if c in subset.columns]
    interactive_table(
        subset[show_cols],
        key_prefix="ra_drill",
        title=f"{pick} — transaction queue",
        help_text="Search and sort within this typology. Use for report exhibits or escalation packets.",
        tier_column="risk_tier",
        filter_columns=["risk_tier", "country"],
        default_sort="risk_score",
        sort_desc=True,
        max_rows=300,
    )
