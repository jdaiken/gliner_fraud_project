"""
Executive brief (cover) for the Risk Analysis Profile dashboard.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from brand import BRIEF_DISCLAIMER
from dashboard_maps import country_aggregate
from dashboard_theme import (
    INTRAFI_BLUE,
    INTRAFI_CORAL,
    INTRAFI_CYAN,
    INTRAFI_GOLD,
    INTRAFI_NAVY,
    INTRAFI_TEAL,
    apply_plotly_theme,
    tier_color_discrete,
)


def _pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _fmt_money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v / 1e6:.2f}M"
    if abs(v) >= 1_000:
        return f"${v / 1e3:.1f}K"
    return f"${v:,.0f}"


def compute_brief_stats(scored: pd.DataFrame, profit_summary: pd.DataFrame | None = None) -> dict:
    n = len(scored)
    n_high = int((scored["risk_tier"] == "HIGH").sum()) if "risk_tier" in scored.columns else 0
    n_med = int((scored["risk_tier"] == "MEDIUM").sum()) if "risk_tier" in scored.columns else 0
    n_low = n - n_high - n_med
    n_flagged = int(scored["anomaly_flag"].sum()) if "anomaly_flag" in scored.columns else 0

    fraud_n = int(scored["isFraud"].sum()) if "isFraud" in scored.columns else 0
    fraud_rate = _pct(fraud_n, n)
    fraud_in_high = 0
    capture_pct = 0.0
    fraud_rate_high = 0.0
    if "isFraud" in scored.columns and "risk_tier" in scored.columns and fraud_n:
        fraud_in_high = int(scored[(scored["isFraud"] == 1) & (scored["risk_tier"] == "HIGH")].shape[0])
        capture_pct = _pct(fraud_in_high, fraud_n)
        if n_high:
            fraud_rate_high = _pct(fraud_in_high, n_high)

    total_vol = scored["amount"].sum() if "amount" in scored.columns else 0
    high_vol = (
        scored.loc[scored["risk_tier"] == "HIGH", "amount"].sum()
        if "amount" in scored.columns and "risk_tier" in scored.columns
        else 0
    )
    high_vol_pct = _pct(high_vol, total_vol)

    avg_score = scored["risk_score"].mean() if "risk_score" in scored.columns else 0
    p90_score = scored["risk_score"].quantile(0.9) if "risk_score" in scored.columns else 0

    top_type = "N/A"
    top_type_rate = 0.0
    if "type" in scored.columns and "isFraud" in scored.columns:
        by_type = scored.groupby("type")["isFraud"].mean().sort_values(ascending=False)
        if len(by_type):
            top_type = str(by_type.index[0])
            top_type_rate = round(100 * by_type.iloc[0], 1)

    top_country = "N/A"
    top_country_high = 0
    if "country" in scored.columns and "risk_tier" in scored.columns:
        high = scored[scored["risk_tier"] == "HIGH"]
        if len(high):
            top_country = str(high.groupby("country").size().idxmax())
            top_country_high = int(high.groupby("country").size().max())

    high_exposure = high_vol
    if profit_summary is not None and not profit_summary.empty:
        row = profit_summary[profit_summary["metric"] == "HIGH risk — dollar exposure ($)"]
        if not row.empty:
            high_exposure = float(row.iloc[0]["value"])

    return {
        "n": n,
        "n_high": n_high,
        "n_med": n_med,
        "n_low": n_low,
        "n_flagged": n_flagged,
        "pct_high": _pct(n_high, n),
        "pct_med": _pct(n_med, n),
        "fraud_n": fraud_n,
        "fraud_rate": fraud_rate,
        "fraud_in_high": fraud_in_high,
        "capture_pct": capture_pct,
        "fraud_rate_high": fraud_rate_high,
        "total_vol": total_vol,
        "high_vol": high_vol,
        "high_vol_pct": high_vol_pct,
        "high_exposure": high_exposure,
        "avg_score": avg_score,
        "p90_score": p90_score,
        "top_type": top_type,
        "top_type_rate": top_type_rate,
        "top_country": top_country,
        "top_country_high": top_country_high,
    }


def _brief_divider():
    st.markdown('<hr class="brief-divider" />', unsafe_allow_html=True)


def _tier_mix_chart(scored: pd.DataFrame):
    if "risk_tier" not in scored.columns:
        return None
    counts = scored["risk_tier"].value_counts().reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0).reset_index()
    counts.columns = ["tier", "count"]
    fig = px.bar(
        counts, x="tier", y="count", title="Review queue composition",
        color="tier", color_discrete_map=tier_color_discrete(), text="count",
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, yaxis_title="Transactions")
    return apply_plotly_theme(fig, hide_legend=True)


def _type_risk_chart(scored: pd.DataFrame):
    if "type" not in scored.columns:
        return None
    g = scored.groupby("type", as_index=False).agg(volume=("amount", "sum"), count=("amount", "count"))
    if "isFraud" in scored.columns:
        fr = scored.groupby("type")["isFraud"].mean() * 100
        g["fraud_rate_pct"] = g["type"].map(fr).fillna(0)
        fig = px.bar(
            g.sort_values("fraud_rate_pct", ascending=True), y="type", x="fraud_rate_pct",
            orientation="h", title="Labeled fraud rate by transaction type",
            color="fraud_rate_pct",
            color_continuous_scale=[[0, INTRAFI_TEAL], [0.5, INTRAFI_GOLD], [1, INTRAFI_CORAL]],
        )
        fig.update_layout(coloraxis_showscale=False, xaxis_title="Fraud rate (%)", yaxis_title="")
    else:
        fig = px.bar(
            g.sort_values("volume", ascending=True), y="type", x="volume", orientation="h",
            title="Volume by transaction type", color_discrete_sequence=[INTRAFI_BLUE],
        )
        fig.update_layout(xaxis_title="Amount ($)", yaxis_title="")
    return apply_plotly_theme(fig, hide_legend=True)


def _country_pressure_chart(scored: pd.DataFrame):
    country_df = country_aggregate(scored)
    if country_df.empty:
        return None
    col = "high_risk_volume" if "high_risk_volume" in country_df.columns else "total_volume"
    top = country_df.nlargest(8, col)
    label_col = "country_name" if "country_name" in top.columns else "country"
    fig = px.bar(
        top.sort_values(col, ascending=True), y=label_col, x=col, orientation="h",
        title="Geographic pressure: HIGH-tier volume", color_discrete_sequence=[INTRAFI_CORAL],
    )
    fig.update_layout(xaxis_title="Amount ($)", yaxis_title="")
    return apply_plotly_theme(fig, hide_legend=True)


def _render_findings_cards(stats: dict) -> None:
    """Key findings using Streamlit columns (reliable rendering)."""
    st.markdown("#### Key findings at a glance")
    items = [
        (INTRAFI_NAVY, f"{stats['n']:,}", "Scored transactions", "Full monitored population"),
        (INTRAFI_CORAL, f"{stats['n_high']:,}", "HIGH-tier queue", f"{stats['pct_high']}% of population"),
        (INTRAFI_GOLD, f"{stats['capture_pct']:.0f}%", "Fraud in HIGH tier", f"{stats['fraud_in_high']:,} of {stats['fraud_n']:,} labeled"),
        (INTRAFI_CYAN, _fmt_money(stats["high_exposure"]), "HIGH exposure", f"{stats['high_vol_pct']}% of volume"),
    ]
    cols = st.columns(4)
    for col, (color, value, label, detail) in zip(cols, items):
        with col:
            col.markdown(
                f"""
                <div style="background:#F4F7FB;border:1px solid #E8EEF4;border-top:4px solid {color};
                     border-radius:8px;padding:0.85rem;text-align:center;">
                  <div style="font-size:1.6rem;font-weight:800;color:{color};">{value}</div>
                  <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;color:#5C6778;margin-top:0.35rem;">{label}</div>
                  <div style="font-size:0.76rem;color:#5C6778;margin-top:0.2rem;">{detail}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_cover_page(scored: pd.DataFrame, profit_summary: pd.DataFrame | None = None) -> None:
    stats = compute_brief_stats(scored, profit_summary)

    st.markdown('<div class="brief-page">', unsafe_allow_html=True)
    st.markdown("#### Executive summary")
    st.markdown(
        f"""
This snapshot covers **{stats['n']:,}** scored transactions. **{stats['n_high']:,}** ({stats['pct_high']}%) are HIGH tier,
with **{_fmt_money(stats['high_exposure'])}** exposure. Where labels exist, **{stats['capture_pct']:.0f}%** of labeled fraud
is in the HIGH queue. See **Risk assessment** in the sidebar for full analysis and regulatory mapping.
        """
    )

    st.markdown("#### Results in brief")
    for b in [
        f"**{stats['n_high']:,}** HIGH-tier and **{stats['n_med']:,}** MEDIUM-tier cases in review queues.",
        f"**{stats['n_flagged']:,}** statistical outliers ({_pct(stats['n_flagged'], stats['n'])}%), separate from tier assignment.",
        f"Highest labeled fraud by type: **{stats['top_type']}** ({stats['top_type_rate']}% rate).",
        f"Top HIGH-tier country: **{stats['top_country']}** ({stats['top_country_high']:,} transactions).",
    ]:
        st.markdown(f"- {b}")

    _render_findings_cards(stats)
    _brief_divider()

    st.markdown("#### Risk concentration")
    left, right = st.columns(2)
    with left:
        fig = _tier_mix_chart(scored)
        if fig:
            st.plotly_chart(fig, width="stretch")
    with right:
        fig = _type_risk_chart(scored)
        if fig:
            st.plotly_chart(fig, width="stretch")
    fig_geo = _country_pressure_chart(scored)
    if fig_geo:
        st.plotly_chart(fig_geo, width="stretch")

    st.markdown(BRIEF_DISCLAIMER)
    st.markdown("</div>", unsafe_allow_html=True)
