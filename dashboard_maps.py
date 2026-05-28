"""
Geographic visualizations for the fraud risk dashboard.
"""

import pandas as pd
import plotly.express as px

from dashboard_theme import (
    INTRAFI_BLUE,
    INTRAFI_CLOUD,
    INTRAFI_CORAL,
    INTRAFI_CYAN,
    INTRAFI_GOLD,
    INTRAFI_NAVY,
    INTRAFI_SKY,
    INTRAFI_TEAL,
    apply_plotly_theme,
)

# ISO-3166 alpha-2 (PaySim country codes) → alpha-3 for Plotly choropleth
COUNTRY_ISO3 = {
    "US": "USA",
    "NG": "NGA",
    "RU": "RUS",
    "CN": "CHN",
    "BR": "BRA",
    "MX": "MEX",
    "GB": "GBR",
    "DE": "DEU",
    "UA": "UKR",
    "KE": "KEN",
}

COUNTRY_NAMES = {
    "US": "United States",
    "NG": "Nigeria",
    "RU": "Russia",
    "CN": "China",
    "BR": "Brazil",
    "MX": "Mexico",
    "GB": "United Kingdom",
    "DE": "Germany",
    "UA": "Ukraine",
    "KE": "Kenya",
}


def country_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Build country-level stats for mapping."""
    if "country" not in df.columns:
        return pd.DataFrame()

    g = df.groupby("country", dropna=False)
    out = g.agg(
        transactions=("amount", "count"),
        total_volume=("amount", "sum"),
        avg_amount=("amount", "mean"),
    ).reset_index()

    if "isFraud" in df.columns:
        fraud = (
            df[df["isFraud"] == 1]
            .groupby("country")
            .agg(fraud_count=("isFraud", "count"), fraud_loss=("amount", "sum"))
            .reset_index()
        )
        out = out.merge(fraud, on="country", how="left")
        out["fraud_count"] = out["fraud_count"].fillna(0).astype(int)
        out["fraud_loss"] = out["fraud_loss"].fillna(0)
        out["fraud_rate_pct"] = (100 * out["fraud_count"] / out["transactions"]).round(2)
    else:
        out["fraud_rate_pct"] = 0.0

    if "risk_tier" in df.columns:
        high = (
            df[df["risk_tier"] == "HIGH"]
            .groupby("country")
            .agg(high_risk_count=("risk_tier", "count"), high_risk_volume=("amount", "sum"))
            .reset_index()
        )
        out = out.merge(high, on="country", how="left")
        out["high_risk_count"] = out["high_risk_count"].fillna(0).astype(int)
        out["high_risk_volume"] = out["high_risk_volume"].fillna(0)

    out["iso_alpha"] = out["country"].map(COUNTRY_ISO3)
    out["country_name"] = out["country"].map(COUNTRY_NAMES).fillna(out["country"])
    out = out.dropna(subset=["iso_alpha"])
    return out


def choropleth_volume(country_df: pd.DataFrame, column: str = "total_volume"):
    """World map colored by selected metric."""
    fig = px.choropleth(
        country_df,
        locations="iso_alpha",
        color=column,
        hover_name="country_name",
        color_continuous_scale=[
            [0, INTRAFI_CYAN],
            [0.5, INTRAFI_BLUE],
            [1, INTRAFI_NAVY],
        ],
        labels={column: column.replace("_", " ").title()},
        title=f"Geographic distribution — {column.replace('_', ' ')}",
    )
    fig.update_geos(
        showcoastlines=True,
        coastlinecolor=INTRAFI_NAVY,
        showland=True,
        landcolor="#f8fafc",
        showocean=True,
        oceancolor=INTRAFI_CLOUD,
        projection_type="natural earth",
    )
    fig.update_layout(coloraxis_colorbar_title=column.replace("_", " ").title())
    return apply_plotly_theme(fig)


def choropleth_fraud_rate(country_df: pd.DataFrame):
    """World map of labeled fraud rate (%)."""
    fig = px.choropleth(
        country_df,
        locations="iso_alpha",
        color="fraud_rate_pct",
        hover_name="country_name",
        color_continuous_scale=[
            [0, INTRAFI_TEAL],
            [0.5, INTRAFI_GOLD],
            [1, INTRAFI_CORAL],
        ],
        labels={"fraud_rate_pct": "Fraud rate (%)"},
        title="Labeled fraud rate by country (research labels)",
        range_color=[0, max(country_df["fraud_rate_pct"].max() * 1.1, 1)],
    )
    fig.update_geos(
        showcoastlines=True,
        coastlinecolor=INTRAFI_NAVY,
        projection_type="natural earth",
    )
    return apply_plotly_theme(fig)


def bar_country_risk(country_df: pd.DataFrame):
    """Horizontal bar chart — HIGH-risk volume by country."""
    if "high_risk_volume" not in country_df.columns:
        country_df = country_df.copy()
        country_df["high_risk_volume"] = 0

    plot_df = country_df.sort_values("high_risk_volume", ascending=True).tail(10)
    fig = px.bar(
        plot_df,
        x="high_risk_volume",
        y="country_name",
        orientation="h",
        title="HIGH-risk dollar exposure by country",
        color="high_risk_volume",
        color_continuous_scale=[INTRAFI_SKY, INTRAFI_CORAL],
        labels={"high_risk_volume": "HIGH tier volume ($)", "country_name": ""},
    )
    fig.update_layout(showlegend=False, coloraxis_showscale=False)
    return apply_plotly_theme(fig)
