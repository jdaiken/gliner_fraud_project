"""
Risk register tab — plain-language review queue for non-technical audiences.
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
TIER_PLAIN = {
    "HIGH": "High priority",
    "MEDIUM": "Medium priority",
    "LOW": "Lower priority",
}
TIER_HINT = {
    "HIGH": "Review first — unusual activity flagged",
    "MEDIUM": "Schedule review when capacity allows",
    "LOW": "Monitor — within normal range for this run",
}

CHART_QUEUE = "How many cases in each priority level?"
CHART_TRUST = "Does the story match the transaction record?"
CHART_MONEY = "How much money is involved by priority?"

FOCUS_ALL = "All cases"
FOCUS_ATTENTION = "Needs a closer look"
FOCUS_HIGH = "High priority only"
FOCUS_READY = "Looks consistent (amount and country match)"

DEFAULT_TABLE_COLS = [
    "sar_id",
    "risk_tier",
    "risk_score",
    "amount",
    "country",
    "transaction_type",
    "amount_reconciled",
    "country_reconciled",
    "extracted_accounts",
    "extracted_risk_factors",
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


def enrich_register(register: pd.DataFrame) -> pd.DataFrame:
    """Add plain-language fields used by charts and filters."""
    df = register.copy()
    if "risk_tier" in df.columns:
        tier = df["risk_tier"].astype(str).str.upper()
        df["priority_label"] = tier.map(TIER_PLAIN).fillna(tier)
    else:
        df["priority_label"] = "Unknown"

    amt_ok = _bool_series(df["amount_reconciled"]) if "amount_reconciled" in df.columns else None
    cty_ok = _bool_series(df["country_reconciled"]) if "country_reconciled" in df.columns else None

    if amt_ok is not None and cty_ok is not None:
        df["story_matches_record"] = amt_ok & cty_ok
        df["needs_closer_look"] = ~df["story_matches_record"]
        df["match_summary"] = df.apply(_match_summary_row, axis=1)
    elif amt_ok is not None:
        df["story_matches_record"] = amt_ok
        df["needs_closer_look"] = ~amt_ok
        df["match_summary"] = df["amount_reconciled"].apply(_recon_label)
    elif cty_ok is not None:
        df["story_matches_record"] = cty_ok
        df["needs_closer_look"] = ~cty_ok
        df["match_summary"] = df["country_reconciled"].apply(_recon_label)
    else:
        df["story_matches_record"] = True
        df["needs_closer_look"] = False
        df["match_summary"] = "Not checked"

    return df


def _recon_label(val) -> str:
    if pd.isna(val):
        return "Not checked"
    return "Matches" if bool(float(val)) else "Needs review"


def _match_summary_row(row: pd.Series) -> str:
    parts = []
    if "amount_reconciled" in row.index:
        parts.append(f"Amount: {_recon_label(row['amount_reconciled'])}")
    if "country_reconciled" in row.index:
        parts.append(f"Country: {_recon_label(row['country_reconciled'])}")
    return " · ".join(parts) if parts else "Not checked"


def _filter_register(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    out = df.copy()
    tiers = settings.get("tiers") or TIER_ORDER
    if "risk_tier" in out.columns and tiers:
        out = out[out["risk_tier"].astype(str).str.upper().isin([t.upper() for t in tiers])]

    min_score = settings.get("min_score", 0)
    if "risk_score" in out.columns and min_score > 0:
        out = out[out["risk_score"] >= min_score]

    focus = settings.get("focus", FOCUS_ALL)
    if focus == FOCUS_ATTENTION and "needs_closer_look" in out.columns:
        out = out[out["needs_closer_look"]]
    elif focus == FOCUS_HIGH and "risk_tier" in out.columns:
        out = out[out["risk_tier"].astype(str).str.upper() == "HIGH"]
    elif focus == FOCUS_READY and "story_matches_record" in out.columns:
        out = out[out["story_matches_record"]]

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
                format_func=lambda t: TIER_PLAIN.get(t, t),
                key="reg_filter_tiers",
            )
            focus = st.radio(
                "Which cases?",
                options=[FOCUS_ALL, FOCUS_ATTENTION, FOCUS_HIGH, FOCUS_READY],
                index=0,
                key="reg_filter_focus",
                help="“Needs a closer look” means the dollar amount or country in the story "
                "did not match the transaction record.",
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
                options=[CHART_QUEUE, CHART_TRUST, CHART_MONEY],
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
            "priority_label", "story_matches_record", "needs_closer_look", "match_summary",
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
            "Needs review first": ("needs_closer_look", False),
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


def _chart_review_queue(df: pd.DataFrame):
    if df.empty or "risk_tier" not in df.columns:
        return None
    counts = (
        df["risk_tier"].astype(str).str.upper()
        .value_counts()
        .reindex(TIER_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["tier", "count"]
    counts["label"] = counts["tier"].map(TIER_PLAIN)
    counts["hint"] = counts["tier"].map(TIER_HINT)
    total = int(counts["count"].sum())

    fig = px.pie(
        counts,
        names="label",
        values="count",
        color="tier",
        color_discrete_map=tier_color_discrete(),
        hole=0.52,
        title="Your review queue — cases by priority",
    )
    fig.update_traces(
        textposition="outside",
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>%{value} cases<br>%{percent}<extra></extra>",
    )
    fig.add_annotation(
        text=f"<b>{total}</b><br>cases",
        x=0.5, y=0.5, font_size=14, showarrow=False, font_color=INTRAFI_NAVY,
    )
    fig.update_layout(showlegend=False)
    return apply_plotly_theme(fig, hide_legend=True)


def _chart_story_trust(df: pd.DataFrame):
    """Stacked bar: narrative vs transaction agreement, by priority."""
    if df.empty or "risk_tier" not in df.columns or "story_matches_record" not in df.columns:
        return None

    rows = []
    for tier in TIER_ORDER:
        sub = df[df["risk_tier"].astype(str).str.upper() == tier]
        if sub.empty:
            continue
        matched = int(sub["story_matches_record"].sum())
        needs = len(sub) - matched
        label = TIER_PLAIN.get(tier, tier)
        rows.append({"priority": label, "tier": tier, "status": "Story matches transaction", "count": matched})
        rows.append({"priority": label, "tier": tier, "status": "Needs a closer look", "count": needs})

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return None

    fig = px.bar(
        plot_df,
        x="priority",
        y="count",
        color="status",
        barmode="stack",
        title="Does the investigation story match the transaction?",
        labels={"priority": "Priority", "count": "Number of cases", "status": ""},
        color_discrete_map={
            "Story matches transaction": INTRAFI_TEAL,
            "Needs a closer look": INTRAFI_CORAL,
        },
        category_orders={"priority": [TIER_PLAIN[t] for t in TIER_ORDER]},
    )
    fig.update_layout(
        legend_title_text="",
        yaxis_title="Number of cases",
        xaxis_title="",
    )
    return apply_plotly_theme(fig)


def _chart_money_by_priority(df: pd.DataFrame):
    if df.empty or "risk_tier" not in df.columns or "amount" not in df.columns:
        return None
    g = (
        df.groupby(df["risk_tier"].astype(str).str.upper(), as_index=False)["amount"]
        .sum()
        .rename(columns={"risk_tier": "tier", "amount": "total_amount"})
    )
    g = g.set_index("tier").reindex(TIER_ORDER, fill_value=0).reset_index()
    g["label"] = g["tier"].map(TIER_PLAIN)
    fig = px.bar(
        g,
        x="label",
        y="total_amount",
        color="tier",
        color_discrete_map=tier_color_discrete(),
        text="total_amount",
        title="Total transaction dollars by priority",
        labels={"label": "Priority", "total_amount": "Dollars ($)"},
    )
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Dollars in flagged transactions")
    return apply_plotly_theme(fig, hide_legend=True)


def _render_summary_strip(df: pd.DataFrame) -> None:
    total = len(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cases in view", f"{total:,}", help="After your filters above")

    if "risk_tier" in df.columns:
        high = (df["risk_tier"].astype(str).str.upper() == "HIGH").sum()
        c2.metric("High priority", f"{high:,}", help="Review these first")

    if "needs_closer_look" in df.columns:
        attn = int(df["needs_closer_look"].sum())
        c3.metric(
            "Needs a closer look",
            f"{attn:,}",
            help="Amount or country in the story did not match the transaction",
        )

    if "amount" in df.columns and total:
        c4.metric(
            "Dollars in view",
            f"${df['amount'].sum():,.0f}",
            help="Sum of transaction amounts for filtered cases",
        )
    elif "story_matches_record" in df.columns and total:
        pct = 100 * df["story_matches_record"].mean()
        c4.metric("Stories that match", f"{pct:.0f}%", help="Amount and country both aligned")


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
            lambda t: TIER_PLAIN.get(str(t).upper(), t)
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
    plain = TIER_PLAIN.get(tier, tier or "Unknown")
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
        cls = "ok" if row.get("story_matches_record") else "warn"
        match_html = f'<p class="reg-status {cls}"><strong>Data check:</strong> {html.escape(str(row["match_summary"]))}</p>'

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
        tier = TIER_PLAIN.get(str(row.get("risk_tier", "")).upper(), "")
        flag = " · ⚠ needs review" if row.get("needs_closer_look") else ""
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

    st.caption("Tip: use **Customize what you see** to filter to “Needs a closer look” and walk cases one by one.")


def render_risk_register(register: pd.DataFrame) -> None:
    _inject_register_css()

    st.markdown(
        '<div class="reg-hero">'
        "<strong>What is this?</strong> Each row is a suspicious-activity case. "
        "The system read the investigation story and pulled out accounts, amounts, and countries. "
        "Your job is to confirm the story matches the transaction, then decide next steps."
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

    chart = settings.get("chart_view", CHART_QUEUE)
    fig = None
    if chart == CHART_TRUST:
        fig = _chart_story_trust(filtered)
    elif chart == CHART_MONEY:
        fig = _chart_money_by_priority(filtered)
    else:
        fig = _chart_review_queue(filtered)

    if fig:
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Not enough data for the selected chart. Try another main chart option.")

    if chart == CHART_QUEUE and "needs_closer_look" in filtered.columns:
        attn = int(filtered["needs_closer_look"].sum())
        if attn:
            st.markdown(
                f'<div class="risk-callout"><strong>{attn:,} cases need a closer look</strong><br>'
                "The dollar amount or country in the story did not match the transaction record. "
                "Open those cases first under <em>Which cases?</em> → Needs a closer look.</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    if settings.get("view_mode") == "One case at a time":
        st.markdown("##### Case review")
        _render_case_browser(filtered)
    else:
        st.markdown("##### Case list")
        st.caption(
            "Plain-language columns where possible. "
            "**Needs review** under amount or country means the story and transaction disagree."
        )
        _display_table(
            filtered,
            settings.get("table_cols") or DEFAULT_TABLE_COLS,
            settings.get("sort_col", "risk_score"),
            settings.get("sort_asc", False),
        )
