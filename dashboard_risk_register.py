"""
Risk register tab — SAR review queue with extraction quality and tier views.
"""

from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_tables import COLUMN_LABELS, label_dataframe
from dashboard_theme import (
    INTRAFI_CORAL,
    INTRAFI_GOLD,
    INTRAFI_NAVY,
    INTRAFI_SLATE,
    INTRAFI_TEAL,
    TIER_COLORS,
    TIER_COLORS_LIGHT,
    apply_plotly_theme,
    tier_color_discrete,
)

TIER_ORDER = ["HIGH", "MEDIUM", "LOW"]
TIER_LABEL = {
    "HIGH": "High risk",
    "MEDIUM": "Medium risk",
    "LOW": "Low risk",
}

CHART_REVIEW_REASONS = "Open items by review reason"
CHART_RISK_TIER = "Cases by risk tier"
CHART_TX_TYPE = "Cases by transaction type"
CHART_EXPOSURE = "Exposure by risk tier"

FOCUS_ALL = "All SARs"
FOCUS_EXCEPTIONS = "Extraction exceptions"
FOCUS_HIGH = "High risk tier only"
FOCUS_ALIGNED = "Extraction aligned"

REVIEW_REASON_ORDER = [
    "Amount extraction gap",
    "Jurisdiction extraction gap",
    "Account not captured",
    "Risk indicator not captured",
    "High-risk tier alert",
    "Ready for analyst review",
]

DEFAULT_TABLE_COLS = [
    "sar_id",
    "risk_tier",
    "risk_score",
    "review_reason",
    "amount",
    "country",
    "transaction_type",
    "extracted_accounts",
    "extracted_risk_factors",
    "amount_reconciled",
    "country_reconciled",
]


def _inject_register_css() -> None:
    st.markdown(
        """
        <style>
        .reg-hero { background: #F4F7FB; border-left: 4px solid #00857C; padding: 0.85rem 1rem;
            border-radius: 0 8px 8px 0; margin-bottom: 0.75rem; font-size: 0.95rem; color: #0D2C54; }
        .reg-case { background: #fff; border: 1px solid #E8EEF4; border-radius: 10px;
            padding: 1rem 1.1rem; margin: 0.5rem 0 1rem; }
        .reg-badge { display: inline-block; padding: 0.2rem 0.55rem; border-radius: 999px;
            font-size: 0.78rem; font-weight: 700; margin-right: 0.35rem; }
        .reg-badge.high { background: #FCEAEA; color: #B91C1C; }
        .reg-badge.medium { background: #FFF4E0; color: #B45309; }
        .reg-badge.low { background: #E6F4F1; color: #0F766E; }
        .reg-status { font-size: 0.88rem; margin: 0.25rem 0; }
        .reg-status.ok { color: #0F766E; }
        .reg-status.warn { color: #B45309; }
        .reg-entity { background: #F4F7FB; padding: 0.35rem 0.6rem; border-radius: 6px;
            margin: 0.2rem 0.35rem 0.2rem 0; display: inline-block; font-size: 0.85rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _bool_series(col: pd.Series) -> pd.Series:
    if col.dtype == bool:
        return col.fillna(False)
    return col.fillna(0).astype(float).astype(bool)


def _amount_in_extracted(amount, extracted: str) -> bool:
    if pd.isna(amount) or not str(extracted).strip():
        return False
    amt = float(amount)
    hay = str(extracted).replace(",", "")
    for fmt in (f"{amt:,.2f}", f"{amt:,.0f}", str(int(amt)) if amt == int(amt) else str(amt)):
        if fmt.replace(",", "") in hay.replace(",", ""):
            return True
    return False


def _country_in_extracted(country, extracted: str) -> bool:
    if pd.isna(country) or not str(country).strip() or not str(extracted).strip():
        return False
    c = str(country).strip().upper()
    parts = [p.strip().upper() for p in str(extracted).split("|") if p.strip()]
    return c in parts


def _review_flags_for_row(row: pd.Series) -> list[str]:
    flags: list[str] = []
    if not _amount_in_extracted(row.get("amount"), str(row.get("extracted_amounts", ""))):
        flags.append("Amount extraction gap")
    if not _country_in_extracted(row.get("country"), str(row.get("extracted_countries", ""))):
        flags.append("Jurisdiction extraction gap")
    if not str(row.get("extracted_accounts", "")).strip():
        flags.append("Account not captured")
    if not str(row.get("extracted_risk_factors", "")).strip():
        flags.append("Risk indicator not captured")
    if not flags and str(row.get("risk_tier", "")).upper() == "HIGH":
        flags.append("High-risk tier alert")
    if not flags:
        flags.append("Ready for analyst review")
    return flags


def enrich_register(register: pd.DataFrame) -> pd.DataFrame:
    """Derived review reasons using extracted fields only (not full narrative text)."""
    df = register.copy()
    if "risk_tier" in df.columns:
        tier = df["risk_tier"].astype(str).str.upper()
        df["priority_label"] = tier.map(TIER_LABEL).fillna(tier)
    else:
        df["priority_label"] = "Unknown"

    flag_lists = df.apply(_review_flags_for_row, axis=1)
    df["review_reason"] = flag_lists.apply(lambda xs: xs[0])
    gap_set = {
        "Amount extraction gap",
        "Jurisdiction extraction gap",
        "Account not captured",
        "Risk indicator not captured",
    }
    df["needs_closer_look"] = flag_lists.apply(lambda xs: any(f in gap_set for f in xs))
    df["extraction_aligned"] = ~df["needs_closer_look"]

    if "amount_reconciled" in df.columns:
        df["_pipeline_amount"] = df["amount_reconciled"].apply(_recon_label)
    if "country_reconciled" in df.columns:
        df["_pipeline_country"] = df["country_reconciled"].apply(_recon_label)

    def _match_summary(row: pd.Series) -> str:
        segs = [f"Review: {row['review_reason']}"]
        if "_pipeline_amount" in row.index:
            segs.append(f"Amount check: {row['_pipeline_amount']}")
        if "_pipeline_country" in row.index:
            segs.append(f"Country check: {row['_pipeline_country']}")
        return " · ".join(segs)

    df["match_summary"] = df.apply(_match_summary, axis=1)
    return df


def _recon_label(val) -> str:
    if pd.isna(val):
        return "Not checked"
    return "Aligned" if bool(float(val)) else "Exception"


def _filter_register(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    out = df.copy()
    tiers = settings.get("tiers") or TIER_ORDER
    if "risk_tier" in out.columns and tiers:
        out = out[out["risk_tier"].astype(str).str.upper().isin([t.upper() for t in tiers])]

    min_score = settings.get("min_score", 0)
    if "risk_score" in out.columns and min_score > 0:
        out = out[out["risk_score"] >= min_score]

    focus = settings.get("focus", FOCUS_ALL)
    if focus == FOCUS_EXCEPTIONS and "needs_closer_look" in out.columns:
        out = out[out["needs_closer_look"]]
    elif focus == FOCUS_HIGH and "risk_tier" in out.columns:
        out = out[out["risk_tier"].astype(str).str.upper() == "HIGH"]
    elif focus == FOCUS_ALIGNED and "extraction_aligned" in out.columns:
        out = out[out["extraction_aligned"]]

    if settings.get("countries") and "country" in out.columns:
        out = out[out["country"].astype(str).isin(settings["countries"])]

    if settings.get("types") and "transaction_type" in out.columns:
        out = out[out["transaction_type"].astype(str).isin(settings["types"])]

    search = (settings.get("search") or "").strip().lower()
    if search and len(search) >= 2:
        mask = pd.Series(False, index=out.index)
        for col in out.columns:
            mask |= out[col].fillna("").astype(str).str.lower().str.contains(search, regex=False)
        out = out[mask]

    return out


def _render_customize_panel(register: pd.DataFrame) -> dict:
    """Sidebar-style controls in an expander; returns filter settings."""
    with st.expander("Customize what you see", expanded=True):
        st.caption("Adjust filters and charts without changing the underlying data.")

        c1, c2, c3 = st.columns(3)
        with c1:
            tiers = st.multiselect(
                "Priority levels to show",
                options=TIER_ORDER,
                default=TIER_ORDER,
                format_func=lambda t: TIER_LABEL.get(t, t),
                key="reg_filter_tiers",
            )
            focus = st.radio(
                "Review queue",
                options=[FOCUS_ALL, FOCUS_EXCEPTIONS, FOCUS_HIGH, FOCUS_ALIGNED],
                index=0,
                key="reg_filter_focus",
                help="Extraction exceptions are SARs where NLP fields did not align with "
                "transaction amount, jurisdiction, accounts, or risk indicators.",
            )
        with c2:
            min_score = 0
            if "risk_score" in register.columns:
                min_score = st.slider(
                    "Minimum risk score",
                    min_value=0,
                    max_value=100,
                    value=0,
                    step=5,
                    key="reg_min_score",
                    help="Higher scores mean more unusual activity in this dataset.",
                )
            chart_view = st.radio(
                "Main chart",
                options=[CHART_REVIEW_REASONS, CHART_RISK_TIER, CHART_TX_TYPE, CHART_EXPOSURE],
                index=0,
                key="reg_chart_view",
            )
        with c3:
            countries = []
            if "country" in register.columns:
                country_opts = sorted(register["country"].dropna().astype(str).unique().tolist())
                countries = st.multiselect(
                    "Countries (optional)",
                    options=country_opts,
                    default=[],
                    key="reg_filter_countries",
                )
            types = []
            if "transaction_type" in register.columns:
                type_opts = sorted(register["transaction_type"].dropna().astype(str).unique().tolist())
                types = st.multiselect(
                    "Transaction types (optional)",
                    options=type_opts,
                    default=[],
                    key="reg_filter_types",
                )

        search = st.text_input(
            "Search cases",
            placeholder="SAR ID, country, account, or words from the story…",
            key="reg_search",
        )

        view_mode = st.radio(
            "How to browse cases",
            options=["Summary table", "One case at a time"],
            horizontal=True,
            key="reg_view_mode",
        )

        avail_cols = [c for c in register.columns if not c.startswith("_") and c not in (
            "priority_label", "extraction_aligned", "needs_closer_look", "match_summary",
        )]
        default_cols = [c for c in DEFAULT_TABLE_COLS if c in avail_cols]
        table_cols = st.multiselect(
            "Columns in the summary table",
            options=avail_cols,
            default=default_cols or avail_cols[:8],
            format_func=lambda c: COLUMN_LABELS.get(c, c.replace("_", " ").title()),
            key="reg_table_cols",
        )

        sort_options = {
            "Highest risk score first": ("risk_score", False),
            "Largest dollar amount first": ("amount", False),
            "Extraction exceptions first": ("needs_closer_look", False),
            "SAR ID (A to Z)": ("sar_id", True),
        }
        if "risk_score" not in register.columns:
            sort_options = {k: v for k, v in sort_options.items() if v[0] != "risk_score"}
        if "amount" not in register.columns:
            sort_options = {k: v for k, v in sort_options.items() if v[0] != "amount"}

        sort_label = st.selectbox(
            "Sort order",
            options=list(sort_options.keys()),
            key="reg_sort_label",
        )
        sort_col, sort_asc = sort_options[sort_label]

    return {
        "tiers": tiers,
        "focus": focus,
        "min_score": min_score,
        "chart_view": chart_view,
        "countries": countries,
        "types": types,
        "search": search,
        "view_mode": view_mode,
        "table_cols": table_cols,
        "sort_col": sort_col,
        "sort_asc": sort_asc,
    }


def _chart_review_reasons(df: pd.DataFrame):
    """Horizontal bar: count of SARs by primary review reason."""
    if df.empty or "review_reason" not in df.columns:
        return None
    rows = []
    for _, row in df.iterrows():
        for reason in _review_flags_for_row(row):
            rows.append({"reason": reason})
    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return None
    counts = (
        plot_df["reason"]
        .value_counts()
        .reindex(REVIEW_REASON_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["reason", "count"]
    counts = counts[counts["count"] > 0].sort_values("count", ascending=True)
    if counts.empty:
        return None

    reason_colors = {
        "Amount extraction gap": INTRAFI_CORAL,
        "Jurisdiction extraction gap": INTRAFI_CORAL,
        "Account not captured": INTRAFI_GOLD,
        "Risk indicator not captured": INTRAFI_GOLD,
        "High-risk tier alert": INTRAFI_NAVY,
        "Ready for analyst review": INTRAFI_TEAL,
    }
    fig = px.bar(
        counts,
        x="count",
        y="reason",
        orientation="h",
        color="reason",
        color_discrete_map=reason_colors,
        text="count",
        title="SAR review queue by reason",
        labels={"reason": "Review reason", "count": "Number of SARs"},
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_title="Number of SARs", yaxis_title="")
    return apply_plotly_theme(fig, hide_legend=True)


def _chart_risk_tier_bar(df: pd.DataFrame):
    if df.empty or "risk_tier" not in df.columns:
        return None
    counts = (
        df["risk_tier"].astype(str).str.upper()
        .value_counts()
        .reindex(TIER_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["tier", "count"]
    counts["label"] = counts["tier"].map(TIER_LABEL)
    fig = px.bar(
        counts,
        x="label",
        y="count",
        color="tier",
        color_discrete_map=tier_color_discrete(),
        text="count",
        title="SAR count by risk tier",
        labels={"label": "Risk tier", "count": "Number of SARs"},
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Number of SARs",
        xaxis=dict(categoryorder="array", categoryarray=[TIER_LABEL[t] for t in TIER_ORDER]),
    )
    return apply_plotly_theme(fig, hide_legend=True)


def _chart_by_transaction_type(df: pd.DataFrame):
    col = "transaction_type" if "transaction_type" in df.columns else "type" if "type" in df.columns else None
    if not col or df.empty:
        return None
    counts = df[col].astype(str).value_counts().reset_index()
    counts.columns = ["transaction_type", "count"]
    counts = counts.sort_values("count", ascending=True).tail(12)
    fig = px.bar(
        counts,
        x="count",
        y="transaction_type",
        orientation="h",
        color_discrete_sequence=[INTRAFI_BLUE],
        text="count",
        title="SAR count by transaction type",
        labels={"transaction_type": "Transaction type", "count": "Number of SARs"},
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_title="Number of SARs", yaxis_title="")
    return apply_plotly_theme(fig, hide_legend=True)


def _chart_exposure_by_tier(df: pd.DataFrame):
    if df.empty or "risk_tier" not in df.columns or "amount" not in df.columns:
        return None
    g = (
        df.groupby(df["risk_tier"].astype(str).str.upper(), as_index=False)["amount"]
        .sum()
        .rename(columns={"risk_tier": "tier", "amount": "total_amount"})
    )
    g = g.set_index("tier").reindex(TIER_ORDER, fill_value=0).reset_index()
    g["label"] = g["tier"].map(TIER_LABEL)
    fig = px.bar(
        g,
        x="label",
        y="total_amount",
        color="tier",
        color_discrete_map=tier_color_discrete(),
        text="total_amount",
        title="Transaction exposure by risk tier",
        labels={"label": "Risk tier", "total_amount": "Dollars ($)"},
    )
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Exposure ($)",
        xaxis=dict(categoryorder="array", categoryarray=[TIER_LABEL[t] for t in TIER_ORDER]),
    )
    return apply_plotly_theme(fig, hide_legend=True)


def _render_summary_strip(df: pd.DataFrame) -> None:
    total = len(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cases in view", f"{total:,}", help="After your filters above")

    if "risk_tier" in df.columns:
        high = (df["risk_tier"].astype(str).str.upper() == "HIGH").sum()
        c2.metric("High risk tier", f"{high:,}", help="SARs in the HIGH risk tier")

    if "needs_closer_look" in df.columns:
        attn = int(df["needs_closer_look"].sum())
        c3.metric(
            "Extraction exceptions",
            f"{attn:,}",
            help="Missing or misaligned NLP extractions vs transaction fields",
        )

    if "amount" in df.columns and total:
        c4.metric(
            "Exposure in view",
            f"${df['amount'].sum():,.0f}",
            help="Sum of transaction amounts for filtered SARs",
        )
    elif "extraction_aligned" in df.columns and total:
        pct = 100 * df["extraction_aligned"].mean()
        c4.metric("Extraction aligned", f"{pct:.0f}%", help="Share with complete NLP alignment")


def _display_table(df: pd.DataFrame, columns: list[str], sort_col: str, sort_asc: bool) -> None:
    if df.empty:
        st.warning("No cases match your filters. Try widening priority levels or lowering the minimum score.")
        return

    view = df.copy()
    if sort_col in view.columns:
        view = view.sort_values(sort_col, ascending=sort_asc, na_position="last")

    show = [c for c in columns if c in view.columns]
    if "match_summary" in view.columns and "match_summary" not in show:
        show = show + ["match_summary"]

    display = view[show].head(500).copy()
    for col in ("amount_reconciled", "country_reconciled"):
        if col in display.columns:
            display[col] = display[col].apply(_recon_label)

    if "risk_tier" in display.columns:
        display["risk_tier"] = display["risk_tier"].map(
            lambda t: TIER_LABEL.get(str(t).upper(), t)
        )

    st.caption(f"Showing {len(display):,} of {len(view):,} cases")
    st.dataframe(label_dataframe(display), width="stretch", hide_index=True)


def _tier_badge_class(tier: str) -> str:
    t = str(tier).upper()
    if t == "HIGH":
        return "high"
    if t == "MEDIUM":
        return "medium"
    return "low"


def _render_case_card(row: pd.Series) -> None:
    tier = str(row.get("risk_tier", "")).upper()
    plain = TIER_LABEL.get(tier, tier or "Unknown")
    badge_cls = _tier_badge_class(tier)
    sid = html.escape(str(row.get("sar_id", "Case")))
    score = row.get("risk_score")
    score_txt = f" · Risk score {float(score):.0f}" if pd.notna(score) else ""

    amt = row.get("amount")
    amt_txt = f"${float(amt):,.0f}" if pd.notna(amt) else "—"
    country = html.escape(str(row.get("country", "—")))
    tx_type = html.escape(str(row.get("transaction_type", row.get("type", "—"))))

    match_html = ""
    if "match_summary" in row.index:
        cls = "ok" if not row.get("needs_closer_look") else "warn"
        match_html = f'<p class="reg-status {cls}"><strong>Review status:</strong> {html.escape(str(row["match_summary"]))}</p>'

    entities = []
    for col, label in (
        ("extracted_accounts", "Accounts mentioned"),
        ("extracted_amounts", "Amounts mentioned"),
        ("extracted_countries", "Countries mentioned"),
        ("extracted_risk_factors", "Risk flags in story"),
        ("extracted_tx_types", "Transaction types mentioned"),
    ):
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
            entities.append(
                f'<div><strong>{label}:</strong> '
                f'<span class="reg-entity">{html.escape(str(row[col]))}</span></div>'
            )

    entity_block = "".join(entities) if entities else "<p class=\"reg-status\">No extracted details for this case.</p>"

    st.markdown(
        f"""
        <div class="reg-case">
          <span class="reg-badge {badge_cls}">{html.escape(plain)}</span>
          <strong>{sid}</strong>{html.escape(score_txt)}
          <p style="margin:0.5rem 0 0.25rem;color:#5C6778;">
            {tx_type} · {amt_txt} · Origin: {country}
          </p>
          {match_html}
          <div style="margin-top:0.65rem;">{entity_block}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "sar_narrative" in row.index and pd.notna(row["sar_narrative"]):
        with st.expander("Read full investigation story", expanded=False):
            st.markdown(str(row["sar_narrative"]))


def _render_case_browser(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("No cases match your filters.")
        return

    sort_df = df.sort_values("risk_score", ascending=False) if "risk_score" in df.columns else df
    options = sort_df["sar_id"].tolist() if "sar_id" in sort_df.columns else list(range(len(sort_df)))

    def _label(sid):
        row = sort_df.loc[sort_df["sar_id"] == sid].iloc[0] if "sar_id" in sort_df.columns else sort_df.iloc[sid]
        tier = TIER_LABEL.get(str(row.get("risk_tier", "")).upper(), "")
        flag = " · Extraction exception" if row.get("needs_closer_look") else ""
        return f"{sid} — {tier}{flag}"

    pick = st.selectbox(
        "Choose a case to review",
        options=options,
        format_func=_label if "sar_id" in sort_df.columns else None,
        key="reg_case_pick",
    )

    if "sar_id" in sort_df.columns:
        row = sort_df.loc[sort_df["sar_id"] == pick].iloc[0]
    else:
        row = sort_df.iloc[int(pick)]

    _render_case_card(row)

    st.caption("Tip: filter to **Extraction exceptions** in Customize to walk the exception queue.")


def render_risk_register(register: pd.DataFrame) -> None:
    _inject_register_css()

    st.markdown(
        '<div class="reg-hero">'
        "<strong>Risk register.</strong> Each SAR links a scored transaction to NLP-extracted "
        "accounts, amounts, jurisdictions, and risk indicators. Use review reasons and tier "
        "filters to prioritize escalation and quality checks before filing."
        "</div>",
        unsafe_allow_html=True,
    )

    enriched = enrich_register(register)
    settings = _render_customize_panel(enriched)
    filtered = _filter_register(enriched, settings)

    if filtered.empty and len(enriched) > 0:
        st.warning("No cases match your filters. Adjust **Customize what you see** above.")
        return

    _render_summary_strip(filtered)

    chart = settings.get("chart_view", CHART_REVIEW_REASONS)
    fig = None
    if chart == CHART_RISK_TIER:
        fig = _chart_risk_tier_bar(filtered)
    elif chart == CHART_TX_TYPE:
        fig = _chart_by_transaction_type(filtered)
    elif chart == CHART_EXPOSURE:
        fig = _chart_exposure_by_tier(filtered)
    else:
        fig = _chart_review_reasons(filtered)

    if fig:
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Not enough data for the selected chart. Try another main chart option.")

    if "needs_closer_look" in filtered.columns:
        attn = int(filtered["needs_closer_look"].sum())
        if attn:
            st.markdown(
                f"<div class='risk-callout'><strong>{attn:,} extraction exceptions</strong><br>"
                "NLP fields did not fully align with transaction amount, jurisdiction, accounts, "
                "or risk indicators. Filter to <em>Extraction exceptions</em> to work that queue.</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    if settings.get("view_mode") == "One case at a time":
        st.markdown("##### Case review")
        _render_case_browser(filtered)
    else:
        st.markdown("##### Case list")
        st.caption(
            "Review reason shows why the SAR is in queue. "
            "Pipeline amount/country checks reflect the saved reconciliation flags."
        )
        _display_table(
            filtered,
            settings.get("table_cols") or DEFAULT_TABLE_COLS,
            settings.get("sort_col", "risk_score"),
            settings.get("sort_asc", False),
        )
