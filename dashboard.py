"""
Risk Analysis Profile — Streamlit dashboard.

Launch: python launch_dashboard.py
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

for _logger in (
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.runtime.caching.cache_data_api",
):
    logging.getLogger(_logger).setLevel(logging.ERROR)

import config
from brand import PAGE_TITLE, RISK_ASSESSMENT_PAGE
from dashboard_branding import render_site_hero
from dashboard_content import DISCLAIMER, FIELD_GLOSSARY, MAP_HELP, PIPELINE_STEPS, TIER_HELP
from dashboard_cover import render_cover_page
from dashboard_guidance import render_tab_intro
from dashboard_nav import render_sidebar_nav
from dashboard_maps import (
    bar_country_risk,
    choropleth_fraud_rate,
    choropleth_volume,
    country_aggregate,
)
from dashboard_theme import (
    INTRAFI_BLUE,
    INTRAFI_CORAL,
    INTRAFI_CYAN,
    INTRAFI_GOLD,
    INTRAFI_NAVY,
    INTRAFI_SKY,
    INTRAFI_SLATE,
    INTRAFI_TEAL,
    apply_plotly_theme,
    inject_brand_css,
    tier_color_discrete,
)


def _in_streamlit_context() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def load_csv(path: Path):
    if not path.exists():
        return None
    return pd.read_csv(path)


def format_compact_money(value, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    v = float(value)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}${v / 1e9:.{decimals}f}B"
    if v >= 1_000_000:
        return f"{sign}${v / 1e6:.{decimals}f}M"
    if v >= 1_000:
        return f"{sign}${v / 1e3:.{decimals}f}K"
    return f"{sign}${v:,.0f}"


def metric_card(label: str, value: str, help_text: str = "", css_class: str = "", value_class: str = ""):
    tip = f'title="{help_text}"' if help_text else ""
    st.markdown(
        f"""
        <div class="risk-metric {css_class}" {tip}>
            <div class="label">{label}</div>
            <div class="value {value_class}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def explain_box(title: str, body: str):
    st.markdown(
        f'<div class="risk-callout"><strong>{title}</strong><br>{body}</div>',
        unsafe_allow_html=True,
    )


def pie_tier_chart(df: pd.DataFrame):
    tier_counts = (
        df["risk_tier"].value_counts().reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0).reset_index()
    )
    tier_counts.columns = ["tier", "count"]
    fig = px.pie(
        tier_counts, names="tier", values="count",
        title="How transactions split across risk tiers",
        color="tier", color_discrete_map=tier_color_discrete(), hole=0.45,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return apply_plotly_theme(fig, hide_legend=True)


def histogram_risk_chart(df: pd.DataFrame):
    fig = px.histogram(
        df, x="risk_score", color="risk_tier", nbins=36,
        title="Risk score distribution (0 = normal, 100 = most unusual)",
        color_discrete_map=tier_color_discrete(), barmode="overlay", opacity=0.85,
    )
    fig.add_vline(x=config.RISK_TIER_MEDIUM, line_dash="dash", line_color=INTRAFI_GOLD, annotation_text="MEDIUM")
    fig.add_vline(x=config.RISK_TIER_HIGH, line_dash="dash", line_color=INTRAFI_CORAL, annotation_text="HIGH")
    return apply_plotly_theme(fig, hide_legend=False)


def bar_fraud_by_tier(df: pd.DataFrame):
    if "isFraud" not in df.columns:
        return None
    rates = []
    for t in ["LOW", "MEDIUM", "HIGH"]:
        sub = df[df["risk_tier"] == t]
        rates.append({"tier": t, "fraud_rate_pct": round(100 * sub["isFraud"].mean(), 1) if len(sub) else 0})
    fig = px.bar(
        pd.DataFrame(rates), x="tier", y="fraud_rate_pct",
        title="Labeled fraud rate by tier (model validation)",
        color="tier", color_discrete_map=tier_color_discrete(), text="fraud_rate_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(yaxis_title="Fraud rate (%)", showlegend=False)
    return apply_plotly_theme(fig, hide_legend=True)


def exposure_by_tier_chart(by_tier: pd.DataFrame):
    dim = "risk_tier" if "risk_tier" in by_tier.columns else by_tier.columns[0]
    plot_df = by_tier.copy()
    plot_df["_vol_label"] = plot_df["total_volume"].apply(format_compact_money)
    fig = px.bar(
        plot_df, x=dim, y="total_volume", title="Dollar volume by risk tier",
        color=dim, color_discrete_map=tier_color_discrete(), text="_vol_label",
    )
    fig.update_traces(textposition="outside", textfont=dict(size=11))
    fig.update_layout(showlegend=False, yaxis_title="Total volume ($)", yaxis_tickformat="$,.2s")
    return apply_plotly_theme(fig, hide_legend=True)


def profit_by_type_chart(by_type: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Total volume", x=by_type["type"], y=by_type["total_volume"], marker_color=INTRAFI_BLUE))
    if "fraud_loss" in by_type.columns:
        fig.add_trace(go.Bar(name="Fraud loss", x=by_type["type"], y=by_type["fraud_loss"], marker_color=INTRAFI_CORAL))
    fig.update_layout(
        title="Volume vs labeled fraud loss by type",
        barmode="group",
        yaxis_title="Amount ($)",
        yaxis_tickformat="$,.2s",
    )
    return apply_plotly_theme(fig)


def _summary_value(summary: pd.DataFrame | None, metric: str, default: str = "N/A") -> str:
    if summary is None:
        return default
    row = summary[summary["metric"] == metric]
    if row.empty:
        return default
    v = row.iloc[0]["value"]
    money = any(k in metric.lower() for k in ("volume", "loss", "outflow", "inflow", "exposure", "size"))
    if isinstance(v, (int, float)) and money:
        return format_compact_money(v)
    if isinstance(v, (int, float)):
        return f"{v:,}"
    return str(v)


def render_data_guide():
    st.markdown("##### What this dashboard shows")
    st.markdown(DISCLAIMER)
    st.markdown("##### How the pipeline builds this view")
    for title, body in PIPELINE_STEPS:
        with st.expander(title, expanded=False):
            st.markdown(body)
    st.markdown("##### Risk tiers")
    st.markdown(TIER_HELP)
    st.markdown("##### Field definitions")
    for key, (title, desc) in FIELD_GLOSSARY.items():
        st.markdown(f"**{title}** (`{key}`) — {desc}")


def render_geography(scored: pd.DataFrame):
    st.markdown(MAP_HELP)
    country_df = country_aggregate(scored)
    if country_df.empty:
        st.warning("No country field available for mapping.")
        return

    metric_options = {
        "total_volume": "Total transaction volume ($)",
        "transactions": "Transaction count",
        "fraud_rate_pct": "Labeled fraud rate (%)",
        "high_risk_volume": "HIGH-risk volume ($)",
    }
    metric_label = st.selectbox("Map metric", list(metric_options.values()))
    col = next(k for k, v in metric_options.items() if v == metric_label)

    try:
        c1, c2 = st.columns([1.4, 1])
        with c1:
            if col == "fraud_rate_pct":
                st.plotly_chart(choropleth_fraud_rate(country_df), width="stretch")
            else:
                st.plotly_chart(choropleth_volume(country_df, column=col), width="stretch")
        with c2:
            st.plotly_chart(bar_country_risk(country_df), width="stretch")
    except Exception as e:
        st.error(f"Could not render map: {e}")

    from dashboard_tables import interactive_table

    table_cols = [
        c for c in [
            "country", "country_name", "transactions", "total_volume",
            "fraud_rate_pct", "high_risk_volume",
        ]
        if c in country_df.columns
    ]
    interactive_table(
        country_df[table_cols].sort_values("total_volume", ascending=False),
        key_prefix="geo_country",
        title="Country detail",
        help_text="Compare volume, fraud rate, and HIGH-tier exposure. Search or filter to focus review.",
        tier_column=None,
        filter_columns=["country"],
        default_sort="total_volume",
        sort_desc=True,
    )


def run_dashboard() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🔷",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_brand_css()

    with st.sidebar:
        page = render_sidebar_nav()
        st.divider()
        st.markdown("**Quick reference**")
        st.markdown(
            f"- **HIGH** — score ≥ {config.RISK_TIER_HIGH}\n"
            f"- **MEDIUM** — score ≥ {config.RISK_TIER_MEDIUM}\n"
            "- **LOW** — below MEDIUM"
        )
        with st.expander("What is risk score?"):
            st.markdown(
                "A 0–100 ranking of how unusual a transaction is versus peers, "
                "using amount, balances, type, time, and country. "
                "It is not proof of fraud."
            )
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M"))
        st.markdown('<div class="sidebar-refresh">', unsafe_allow_html=True)
        if st.button("Refresh data", type="primary", width="stretch", key="sidebar_refresh"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    scored = load_csv(config.SCORED_CSV)
    register = load_csv(config.RISK_REGISTER_CSV)
    narratives = load_csv(config.SAR_NARRATIVES_CSV)
    profit_summary = load_csv(config.PROFIT_SUMMARY_CSV)
    profit_by_tier = load_csv(config.PROFIT_BY_TIER_CSV)
    profit_by_type = load_csv(config.PROFIT_BY_TYPE_CSV)
    profit_accounts = load_csv(config.PROFIT_TOP_ACCOUNTS_CSV)

    if scored is None:
        explain_box(
            "No data loaded",
            "Run <code>python run_pipeline.py</code> to generate scored transactions, then refresh.",
        )
        st.stop()

    render_site_hero()
    render_tab_intro(page)

    if page == "Brief":
        try:
            render_cover_page(scored, profit_summary)
        except Exception as e:
            st.error(f"Brief error: {e}")

    elif page == "Overview":
        left, right = st.columns([1, 1])
        with left:
            st.plotly_chart(pie_tier_chart(scored), width="stretch")
        with right:
            fig = bar_fraud_by_tier(scored)
            st.plotly_chart(fig if fig else pie_tier_chart(scored), width="stretch")
        st.plotly_chart(histogram_risk_chart(scored), width="stretch")

    elif page == "Data guide":
        render_data_guide()

    elif page == "Geography":
        try:
            render_geography(scored)
        except Exception as e:
            st.error(f"Geography error: {e}")

    elif page == "Financial":
        try:
            if profit_summary is None:
                st.info("Run `python profit_analysis.py` to generate financial rollups.")
            else:
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    metric_card(
                        "Total volume",
                        _summary_value(profit_summary, "Total transaction volume ($)"),
                        "Sum of transaction amounts in the scored population.",
                        value_class="value-money",
                    )
                with m2:
                    metric_card(
                        "Fraud loss",
                        _summary_value(profit_summary, "Labeled fraud loss ($)"),
                        "Labeled fraud amounts where available.",
                        value_class="value-money",
                    )
                with m3:
                    metric_card(
                        "HIGH exposure",
                        _summary_value(profit_summary, "HIGH risk — dollar exposure ($)"),
                        "Dollar value in the HIGH risk tier.",
                        value_class="value-money",
                    )
                with m4:
                    metric_card(
                        "Origin outflow",
                        _summary_value(profit_summary, "Total origin outflow ($)"),
                        "Total outflow from origin accounts.",
                        value_class="value-money",
                    )
                c1, c2 = st.columns(2)
                with c1:
                    if profit_by_tier is not None and not profit_by_tier.empty:
                        st.plotly_chart(exposure_by_tier_chart(profit_by_tier), width="stretch")
                with c2:
                    if profit_by_type is not None and not profit_by_type.empty:
                        st.plotly_chart(profit_by_type_chart(profit_by_type), width="stretch")
                if profit_accounts is not None and not profit_accounts.empty:
                    from dashboard_tables import interactive_table
                    interactive_table(
                        profit_accounts,
                        key_prefix="fin_accounts",
                        title="Top accounts by outflow",
                        help_text="Largest origin outflows — candidates for limits or enhanced review.",
                        tier_column=None,
                        default_sort="total_outflow" if "total_outflow" in profit_accounts.columns else profit_accounts.columns[0],
                    )
        except Exception as e:
            st.error(f"Financial error: {e}")

    elif page == "Transactions":
        try:
            from dashboard_transactions import render_transactions_tab
            render_transactions_tab(scored)
        except Exception as e:
            st.error(f"Transactions error: {e}")

    elif page == "SAR narratives":
        try:
            from dashboard_sections import render_sar_narratives
            render_sar_narratives(narratives)
        except Exception as e:
            st.error(f"SAR narratives error: {e}")

    elif page == "Risk register":
        try:
            if register is None:
                st.info("Run GLiNER extraction (`python gliner_extraction.py`) for structured SAR fields.")
            else:
                from dashboard_sections import render_risk_register
                render_risk_register(register)
        except Exception as e:
            st.error(f"Risk register error: {e}")

    elif page == RISK_ASSESSMENT_PAGE:
        try:
            from risk_assessment import render_risk_assessment_interactive
            render_risk_assessment_interactive(scored, profit_summary)
        except Exception as e:
            st.error(f"Risk assessment error: {e}")

    elif page == "Exports":
        try:
            from dashboard_sections import render_exports
            render_exports(scored, profit_summary)
        except Exception as e:
            st.error(f"Exports error: {e}")


if _in_streamlit_context():
    run_dashboard()
elif __name__ == "__main__":
    print("Starting dashboard via Streamlit...\nOpen http://localhost:8501\n")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", __file__, "--server.headless=true"],
        check=False,
    )
