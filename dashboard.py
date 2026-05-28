"""
dashboard.py
------------
Streamlit dashboard for scored transactions and the GLiNER risk register.
Run: streamlit run dashboard.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import config

st.set_page_config(
    page_title="Fraud Risk Intelligence",
    page_icon="📊",
    layout="wide",
)

st.title("Fraud Risk Intelligence")
st.caption("Isolation Forest scoring + GLiNER entity extraction")


@st.cache_data
def load_csv(path: Path):
    if not path.exists():
        return None
    return pd.read_csv(path)


scored = load_csv(config.SCORED_CSV)
register = load_csv(config.RISK_REGISTER_CSV)

tab_overview, tab_scored, tab_register, tab_eda = st.tabs(
    ["Overview", "Scored Transactions", "Risk Register", "EDA Charts"]
)

with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    if scored is not None:
        col1.metric("Transactions", f"{len(scored):,}")
        col2.metric("HIGH risk", f"{(scored['risk_tier'] == 'HIGH').sum():,}")
        col3.metric("Flagged anomalies", f"{scored['anomaly_flag'].sum():,}")
        if "isFraud" in scored.columns:
            captured = scored[(scored["isFraud"] == 1) & (scored["risk_tier"] == "HIGH")]
            col4.metric("Fraud in HIGH tier", f"{len(captured):,}")
        else:
            col4.metric("Fraud in HIGH tier", "N/A")
    else:
        st.warning(f"No scored data at `{config.SCORED_CSV}`. Run `python run_pipeline.py`.")

    if scored is not None and "risk_tier" in scored.columns:
        tier_counts = scored["risk_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        fig = px.pie(tier_counts, names="tier", values="count", title="Risk tier distribution")
        st.plotly_chart(fig, use_container_width=True)

with tab_scored:
    if scored is None:
        st.info("Run anomaly detection first.")
    else:
        tiers = st.multiselect(
            "Filter tiers",
            options=["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM"],
        )
        filtered = scored[scored["risk_tier"].isin(tiers)] if tiers else scored
        st.dataframe(
            filtered.sort_values("risk_score", ascending=False).head(500),
            use_container_width=True,
        )
        if "risk_score" in filtered.columns:
            fig = px.histogram(
                filtered, x="risk_score", color="risk_tier", nbins=40,
                title="Risk score distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

with tab_register:
    if register is None:
        st.info(f"No risk register at `{config.RISK_REGISTER_CSV}`. Run GLiNER extraction.")
    else:
        if "amount_reconciled" in register.columns:
            c1, c2 = st.columns(2)
            c1.metric(
                "Amount reconciliation",
                f"{register['amount_reconciled'].mean() * 100:.0f}%",
            )
            c2.metric(
                "Country reconciliation",
                f"{register['country_reconciled'].mean() * 100:.0f}%",
            )
        show_cols = [
            c for c in [
                "sar_id", "risk_score", "risk_tier", "amount", "country",
                "extracted_accounts", "extracted_amounts", "extracted_countries",
                "extracted_risk_factors", "amount_reconciled", "country_reconciled",
            ]
            if c in register.columns
        ]
        st.dataframe(register[show_cols], use_container_width=True)
        if "sar_narrative" in register.columns:
            idx = st.selectbox("View narrative", range(len(register)), format_func=lambda i: register.iloc[i]["sar_id"])
            st.text_area("SAR narrative", register.iloc[idx]["sar_narrative"], height=200)

with tab_eda:
    eda_dir = config.EDA_DIR
    if not eda_dir.exists():
        st.info("Run `python eda.py` to generate charts.")
    else:
        images = sorted(eda_dir.glob("*.png"))
        for img in images:
            st.subheader(img.stem.replace("_", " ").title())
            st.image(str(img), use_container_width=True)
