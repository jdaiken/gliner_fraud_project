"""
SAR narrative dashboard visuals and keyword highlighting.
"""

from __future__ import annotations

import html
import re

import pandas as pd
import plotly.express as px
import streamlit as st

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

AML_KEYWORDS = [
    "suspicious",
    "layering",
    "structuring",
    "integration",
    "money laundering",
    "anomalous",
    "depleted",
    "high-risk",
    "elevated",
    "flagged",
    "inconsistent",
    "beneficiary",
    "originating",
    "risk indicators",
    "cash-out",
    "cash out",
    "transfer",
    "balance drained",
]

INDICATOR_PHRASES = [
    "account balance fully depleted",
    "exceeds $100,000 threshold",
    "00:00",
    "05:00",
    "high-risk jurisdiction",
    "layering risk",
    "structuring",
    "integration phase",
]


def narrative_highlight_terms(row: pd.Series | None = None) -> list[str]:
    terms = list(AML_KEYWORDS) + list(INDICATOR_PHRASES)
    if row is None:
        return terms
    for col in ("country", "type", "nameOrig", "nameDest"):
        if col in row.index and pd.notna(row[col]):
            terms.append(str(row[col]))
    if "amount" in row.index and pd.notna(row["amount"]):
        amt = float(row["amount"])
        terms.append(f"${amt:,.2f}")
        terms.append(f"${amt:,.0f}")
    return terms


def highlight_narrative_html(
    text: str,
    extra_terms: list[str] | None = None,
    search_query: str = "",
) -> str:
    """Return HTML with marks on AML terms and optional search hits."""
    safe = html.escape(text)
    patterns: list[str] = []
    patterns.append(r"\$[\d,]+(?:\.\d{2})?")
    for term in AML_KEYWORDS + INDICATOR_PHRASES:
        patterns.append(re.escape(term))
    if extra_terms:
        for term in extra_terms:
            if term and len(str(term)) >= 2:
                patterns.append(re.escape(str(term)))
    if search_query and len(search_query.strip()) >= 2:
        patterns.append(re.escape(search_query.strip()))

    combined = "|".join(f"({p})" for p in patterns)
    if not combined:
        return f'<div class="narrative-preview">{safe}</div>'

    def repl(m: re.Match) -> str:
        return f'<mark class="narrative-kw">{m.group(0)}</mark>'

    highlighted = re.sub(combined, repl, safe, flags=re.IGNORECASE)
    return f'<div class="narrative-preview">{highlighted}</div>'


def chart_narratives_by_type(df: pd.DataFrame):
    if "type" not in df.columns:
        return None
    counts = df["type"].value_counts().reset_index()
    counts.columns = ["type", "count"]
    fig = px.pie(
        counts,
        names="type",
        values="count",
        title="SAR queue by transaction type",
        color_discrete_sequence=[INTRAFI_BLUE, INTRAFI_CYAN, INTRAFI_NAVY, INTRAFI_CORAL],
        hole=0.4,
    )
    return apply_plotly_theme(fig)


def chart_amount_by_country(df: pd.DataFrame, top_n: int = 8):
    if "country" not in df.columns or "amount" not in df.columns:
        return None
    g = (
        df.groupby("country", as_index=False)["amount"]
        .sum()
        .nlargest(top_n, "amount")
        .sort_values("amount", ascending=True)
    )
    fig = px.bar(
        g,
        y="country",
        x="amount",
        orientation="h",
        title="Flagged dollars by origin country",
        color_discrete_sequence=[INTRAFI_CORAL],
    )
    fig.update_layout(xaxis_title="Amount ($)", yaxis_title="")
    return apply_plotly_theme(fig)


def chart_risk_score_distribution(df: pd.DataFrame):
    if "risk_score" not in df.columns:
        return None
    color = "risk_tier" if "risk_tier" in df.columns else None
    fig = px.histogram(
        df,
        x="risk_score",
        color=color,
        nbins=24,
        title="Risk score distribution in SAR queue",
        color_discrete_map=tier_color_discrete() if color else None,
        opacity=0.85,
    )
    fig.update_layout(xaxis_title="Risk score", yaxis_title="Narratives")
    return apply_plotly_theme(fig)


def chart_amount_vs_score(df: pd.DataFrame):
    if "amount" not in df.columns or "risk_score" not in df.columns:
        return None
    fig = px.scatter(
        df,
        x="risk_score",
        y="amount",
        color="type" if "type" in df.columns else None,
        hover_data=[c for c in ["sar_id", "country", "risk_tier"] if c in df.columns],
        title="Exposure vs risk score (each point is one SAR)",
        color_discrete_sequence=[INTRAFI_BLUE, INTRAFI_CYAN, INTRAFI_CORAL, INTRAFI_GOLD],
    )
    fig.update_layout(yaxis_type="log", yaxis_title="Amount ($)", xaxis_title="Risk score")
    return apply_plotly_theme(fig)


def chart_activity_by_hour(df: pd.DataFrame):
    if "hour" not in df.columns:
        return None
    g = df.groupby("hour", as_index=False).size()
    g.columns = ["hour", "count"]
    fig = px.bar(
        g,
        x="hour",
        y="count",
        title="When flagged activity occurred (hour of day)",
        color_discrete_sequence=[INTRAFI_NAVY],
    )
    fig.update_layout(xaxis_title="Hour", yaxis_title="Narratives")
    return apply_plotly_theme(fig)


def chart_topic_distribution(topics_df: pd.DataFrame):
    if topics_df.empty or "document_count" not in topics_df.columns:
        return None
    plot_df = topics_df.copy()
    plot_df["label"] = plot_df.apply(
        lambda r: f"Topic {int(r['topic_id'])}: {str(r['topic_label'])[:32]}",
        axis=1,
    )
    fig = px.bar(
        plot_df,
        x="document_count",
        y="label",
        orientation="h",
        title="Narrative themes (topic model)",
        color="document_count",
        color_continuous_scale=[[0, INTRAFI_CYAN], [1, INTRAFI_CORAL]],
    )
    fig.update_layout(coloraxis_showscale=False, xaxis_title="Narratives", yaxis_title="", showlegend=False)
    return apply_plotly_theme(fig, hide_legend=True)


def chart_word_treemap(word_df: pd.DataFrame):
    if word_df is None or word_df.empty:
        return None
    plot_df = word_df.copy()
    fig = px.treemap(
        plot_df,
        path=["word"],
        values="weight",
        color="z_score",
        color_continuous_scale=[[0, INTRAFI_CYAN], [0.5, INTRAFI_GOLD], [1, INTRAFI_CORAL]],
        title="Word tree (double-click a word to add as stop word)",
        custom_data=["word", "z_score", "count"],
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Count: %{customdata[2]}<br>Z-score: %{customdata[1]:.2f}<extra></extra>",
    )
    fig.update_layout(margin=dict(t=64, l=8, r=8, b=24), coloraxis_colorbar_title="Z-score")
    return apply_plotly_theme(fig, hide_legend=True)


def filter_narratives_df(
    df: pd.DataFrame,
    search_query: str,
) -> pd.DataFrame:
    if not search_query or len(search_query.strip()) < 2:
        return df
    q = search_query.strip().lower()
    if "sar_narrative" not in df.columns:
        return df.iloc[0:0]
    mask = df["sar_narrative"].fillna("").str.lower().str.contains(q, regex=False)
    for col in ("sar_id", "country", "type"):
        if col in df.columns:
            mask |= df[col].fillna("").astype(str).str.lower().str.contains(q, regex=False)
    return df[mask]


def render_narrative_previews(
    df: pd.DataFrame,
    n: int = 5,
    *,
    search_query: str = "",
    expanded_all: bool = True,
    max_show: int = 20,
) -> None:
    """Render narrative text in expanders (all expanded by default)."""
    if "sar_narrative" not in df.columns:
        return

    filtered = filter_narratives_df(df, search_query)
    if filtered.empty:
        st.warning("No narratives match your search.")
        return

    if search_query:
        st.markdown(f"##### Matching narratives ({len(filtered):,})")
        subset = filtered.head(max_show)
    else:
        st.markdown("##### Sample narratives (top risk scores)")
        subset = (
            filtered.sort_values("risk_score", ascending=False).head(n)
            if "risk_score" in filtered.columns
            else filtered.head(n)
        )

    for _, row in subset.iterrows():
        sid = row.get("sar_id", "SAR")
        meta_parts = []
        if "risk_score" in row.index and pd.notna(row["risk_score"]):
            meta_parts.append(f"Score {float(row['risk_score']):.0f}")
        if "risk_tier" in row.index and pd.notna(row["risk_tier"]):
            meta_parts.append(str(row["risk_tier"]))
        if "type" in row.index:
            meta_parts.append(str(row["type"]))
        if "amount" in row.index and pd.notna(row["amount"]):
            meta_parts.append(f"${float(row['amount']):,.0f}")
        if "country" in row.index:
            meta_parts.append(str(row["country"]))
        if "topic_label" in row.index and pd.notna(row.get("topic_label")):
            meta_parts.append(f"Theme: {row['topic_label']}")

        title = f"{sid} · " + " · ".join(meta_parts)
        text = str(row["sar_narrative"])
        body = highlight_narrative_html(
            text,
            narrative_highlight_terms(row),
            search_query=search_query,
        )
        with st.expander(title, expanded=expanded_all):
            st.markdown(body, unsafe_allow_html=True)
