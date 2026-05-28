"""
Risk assessment report: deposit-placement risk, regulatory alignment, PDF/HTML export.
"""

from __future__ import annotations

import base64
import io
import textwrap
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages

from brand import APP_NAME
from dashboard_cover import compute_brief_stats, _fmt_money, _pct
from dashboard_maps import country_aggregate
from dashboard_theme import (
    INTRAFI_BLUE,
    INTRAFI_CORAL,
    INTRAFI_CYAN,
    INTRAFI_GOLD,
    INTRAFI_NAVY,
    INTRAFI_SLATE,
    INTRAFI_TEAL,
    INTRAFI_WHITE,
    TIER_COLORS,
    apply_plotly_theme,
    tier_color_discrete,
)
from risk_assessment_content import REGULATORY_REFERENCES, RISK_AREA_THEMES

plt.rcParams.update({"figure.facecolor": INTRAFI_WHITE, "font.family": "sans-serif", "font.size": 10})

SECTIONS = [
    ("summary", "Executive summary"),
    ("context", "Industry and product context"),
    ("findings", "Monitoring findings"),
    ("geography", "Geographic risk"),
    ("regulatory", "Regulatory alignment"),
    ("actions", "Recommended actions"),
]


def _no_em(text: str) -> str:
    return text.replace("\u2014", "-").replace("\u2013", "-")


def _fig_to_base64(fig, fmt: str = "png") -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _tier_chart_fig(scored: pd.DataFrame):
    if "risk_tier" not in scored.columns:
        return None
    counts = scored["risk_tier"].value_counts().reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0).reset_index()
    counts.columns = ["tier", "count"]
    fig = px.bar(counts, x="tier", y="count", color="tier", color_discrete_map=tier_color_discrete())
    fig.update_layout(title="Transactions by risk tier", showlegend=False)
    return apply_plotly_theme(fig, hide_legend=True)


def _citation_list() -> list[tuple[str, str]]:
    """Flatten regulatory references into numbered (label, url) pairs."""
    cites = []
    for r in REGULATORY_REFERENCES:
        for lnk in r["links"]:
            cites.append((lnk["label"], lnk["url"]))
    return cites


def _pdf_draw_paragraph(ax, text: str, x: float, y: float, *, width: int = 88, size: int = 10, leading: float = 0.028) -> float:
    for para in text.split("\n\n"):
        for line in textwrap.wrap(_no_em(para), width=width):
            ax.text(x, y, line, fontsize=size, color=INTRAFI_NAVY, va="top", ha="left")
            y -= leading
        y -= leading * 0.35
    return y


def _pdf_page_header(ax, title: str, page_num: int | None = None):
    ax.text(0.05, 0.97, title, fontsize=14, fontweight="bold", color=INTRAFI_NAVY, va="top")
    if page_num is not None:
        ax.text(0.95, 0.03, str(page_num), fontsize=9, color=INTRAFI_SLATE, ha="right", va="bottom")


def _country_chart_fig(scored: pd.DataFrame):
    cdf = country_aggregate(scored)
    if cdf.empty:
        return None
    col = "high_risk_volume" if "high_risk_volume" in cdf.columns else "total_volume"
    top = cdf.nlargest(8, col)
    label = top["country_name"].fillna(top["country"]) if "country_name" in top.columns else top["country"]
    fig = px.bar(top.sort_values(col, ascending=True), y=label, x=col, orientation="h", title="HIGH-tier volume by country")
    fig.update_layout(coloraxis_showscale=False)
    return apply_plotly_theme(fig)


def build_narrative_blocks(stats: dict) -> dict[str, list[str]]:
    exec_lines = [
        f"This run scores {stats['n']:,} transactions. {stats['n_high']:,} ({stats['pct_high']}%) are HIGH tier "
        f"(score at or above 75), representing {_fmt_money(stats['high_exposure'])} of exposure.",
        f"Labeled fraud (research only) appears in {stats['fraud_in_high']:,} HIGH-tier rows, "
        f"{stats['capture_pct']:.0f}% of all labeled fraud in the file.",
        f"Top typology by labeled fraud rate: {stats['top_type']} ({stats['top_type_rate']}%). "
        f"Top HIGH-tier country code: {stats['top_country']} ({stats['top_country_high']:,} flags).",
    ]
    finding_bullets = [
        f"HIGH queue: {stats['n_high']:,} transactions; MEDIUM: {stats['n_med']:,}.",
        f"Statistical anomaly flags: {stats['n_flagged']:,} ({_pct(stats['n_flagged'], stats['n'])}% of population).",
        f"90th percentile risk score: {stats['p90_score']:.1f}; portfolio fraud rate: {stats['fraud_rate']:.2f}%.",
        f"Total volume {_fmt_money(stats['total_vol'])}; HIGH-tier share of volume: {stats['high_vol_pct']:.1f}%.",
    ]
    action_bullets = [
        "Clear HIGH-tier queue within policy SLA; document escalation for balance-drained and high-risk country flags.",
        "Reconcile geographic concentration to sanctions and policy country lists before SAR decisioning.",
        "Validate model thresholds against FFIEC expectations for risk-based monitoring and lookback.",
        "Maintain workpaper evidence linking alerts, narrative text, and SAR filing decisions per 31 CFR 1020.320.",
    ]
    return {
        "executive": [_no_em(x) for x in exec_lines],
        "findings": [_no_em(x) for x in finding_bullets],
        "actions": [_no_em(x) for x in action_bullets],
    }


def _links_markdown(refs: list[dict]) -> str:
    return " · ".join(f"[{lnk['label']}]({lnk['url']})" for lnk in refs)


def _links_html(refs: list[dict]) -> str:
    return " · ".join(
        f'<a href="{lnk["url"]}" target="_blank" rel="noopener noreferrer">{lnk["label"]}</a>'
        for lnk in refs
    )


def _render_regulatory_section() -> None:
    for r in REGULATORY_REFERENCES:
        st.markdown(f"#### {r['title']}")
        st.markdown(f"**Product line:** {_no_em(r['product_line'])}")
        st.markdown(f"**Monitoring link:** {_no_em(r['summary'])}")
        st.markdown(f"**References:** {_links_markdown(r['links'])}")
        st.markdown("")


def _render_pdf_export_bar(scored: pd.DataFrame, profit_summary: pd.DataFrame | None) -> None:
    export_df = st.session_state.get("ra_filtered_scored", scored)
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Generate risk assessment PDF", type="primary", width="stretch"):
            with st.spinner("Building PDF…"):
                from dashboard_exports import export_risk_assessment_pdf
                data, fname = export_risk_assessment_pdf(export_df, profit_summary)
                st.session_state["risk_assessment_pdf"] = (data, fname)
            st.success("PDF ready.")
    with col2:
        if st.session_state.get("risk_assessment_pdf"):
            data, fname = st.session_state["risk_assessment_pdf"]
            st.download_button(
                "Download PDF report",
                data=data,
                file_name=fname,
                mime="application/pdf",
                width="stretch",
            )
        else:
            st.caption("Click **Generate risk assessment PDF** to download a portable copy.")


def render_risk_assessment_interactive(
    scored: pd.DataFrame,
    profit_summary: pd.DataFrame | None = None,
) -> None:
    """Full scrollable risk assessment with filters and typology drill-down."""
    from risk_assessment_ui import render_assessment_controls, render_typology_drilldown

    stamp = datetime.now().strftime("%B %d, %Y")
    st.markdown(f"## {APP_NAME}")
    st.caption(f"Risk assessment · {stamp} · Filter, drill down, then export")

    filtered, settings = render_assessment_controls(scored)
    if filtered.empty:
        return

    _render_pdf_export_bar(scored, profit_summary)
    st.divider()

    stats = compute_brief_stats(filtered, profit_summary)
    blocks = build_narrative_blocks(stats)
    sections = set(settings.get("sections") or [])

    if "Executive summary" in sections:
        st.markdown("## Executive summary")
        for p in blocks["executive"]:
            st.markdown(p)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Transactions in scope", f"{stats['n']:,}")
        c2.metric("High-risk tier", f"{stats['n_high']:,}")
        c3.metric("Fraud capture (labeled)", f"{stats['capture_pct']:.0f}%")
        c4.metric("High-risk exposure", _fmt_money(stats["high_exposure"]))
        st.divider()

    if "Industry context" in sections:
        st.markdown("## Industry and product context")
        st.markdown(
            _no_em(
                "Deposit-placement and reciprocal deposit programs help institutions keep large balances "
                "insured and distributed across the network. Sweep structures move liquidity on short horizons. "
                "This profile connects monitoring output to those operating themes."
            )
        )
        for theme in RISK_AREA_THEMES:
            st.markdown(f"### {theme['title']}")
            st.markdown(_no_em(theme["body"]))
        st.divider()

    if "Monitoring findings" in sections:
        st.markdown("## Monitoring findings")
        for b in blocks["findings"]:
            st.markdown(f"- {b}")
        tier_fig = _tier_chart_fig(filtered)
        if tier_fig:
            st.plotly_chart(tier_fig, width="stretch")
        if "type" in filtered.columns and "isFraud" in filtered.columns:
            g = filtered.groupby("type")["isFraud"].mean().reset_index()
            g.columns = ["type", "fraud_rate"]
            g["fraud_rate_pct"] = 100 * g["fraud_rate"]
            fig = px.bar(
                g.sort_values("fraud_rate_pct"), x="type", y="fraud_rate_pct",
                title="Labeled fraud rate by transaction type (filtered scope)",
                labels={"fraud_rate_pct": "Fraud rate (%)", "type": "Transaction type"},
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(apply_plotly_theme(fig, hide_legend=True), width="stretch")
        st.divider()

    if "Typology drill-down" in sections:
        render_typology_drilldown(filtered)
        st.divider()

    if "Geographic risk" in sections:
        st.markdown("## Geographic risk")
        fig = _country_chart_fig(filtered)
        if fig:
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No country data available for the current filters.")
        st.divider()

    if "Regulatory alignment" in sections:
        st.markdown("## Regulatory alignment")
        st.markdown(
            _no_em(
                "The items below link deposit-network and sweep product themes to U.S. AML and "
                "deposit-insurance rules. Confirm applicability with compliance and counsel."
            )
        )
        _render_regulatory_section()
        st.divider()

    if "Recommended actions" in sections:
        st.markdown("## Recommended actions")
        for b in blocks["actions"]:
            st.markdown(f"- {b}")
        st.markdown("### Source references")
        for r in REGULATORY_REFERENCES:
            st.markdown(f"- **{r['title']}:** {_links_markdown(r['links'])}")
        st.caption("Demonstration data only. Not legal advice or a regulatory filing.")


def _chart_images(scored: pd.DataFrame) -> dict[str, str]:
    images = {}
    if "risk_tier" not in scored.columns:
        return images
    fig, ax = plt.subplots(figsize=(6, 3.5))
    counts = scored["risk_tier"].value_counts().reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0)
    colors = [TIER_COLORS.get(t, INTRAFI_BLUE) for t in counts.index]
    ax.bar(counts.index, counts.values, color=colors)
    ax.set_title("Transactions by risk tier")
    ax.set_ylabel("Count")
    images["tier"] = _fig_to_base64(fig)

    cdf = country_aggregate(scored)
    if not cdf.empty:
        col = "high_risk_volume" if "high_risk_volume" in cdf.columns else "total_volume"
        top = cdf.nlargest(8, col)
        fig, ax = plt.subplots(figsize=(6, 4))
        labels = top["country_name"].fillna(top["country"]) if "country_name" in top.columns else top["country"]
        ax.barh(labels.astype(str), top[col].values, color=INTRAFI_CORAL)
        ax.set_title("Top countries by HIGH-tier volume")
        ax.set_xlabel("Amount ($)")
        images["country"] = _fig_to_base64(fig)
    return images


def build_risk_assessment_html(
    scored: pd.DataFrame,
    profit_summary: pd.DataFrame | None = None,
) -> str:
    stats = compute_brief_stats(scored, profit_summary)
    blocks = build_narrative_blocks(stats)
    images = _chart_images(scored)
    stamp = datetime.now().strftime("%B %d, %Y %H:%M")

    exec_html = "".join(f"<p>{p}</p>" for p in blocks["executive"])
    findings_html = "".join(f"<li>{b}</li>" for b in blocks["findings"])
    actions_html = "".join(f"<li>{b}</li>" for b in blocks["actions"])
    themes_html = "".join(
        f'<div class="reg-block"><h3>{t["title"]}</h3><p>{_no_em(t["body"])}</p></div>'
        for t in RISK_AREA_THEMES
    )
    toc_links = " · ".join(f'<a href="#{sid}">{label}</a>' for sid, label in SECTIONS)
    reg_blocks = ""
    for r in REGULATORY_REFERENCES:
        reg_blocks += f"""
        <div class="reg-card">
          <h3>{r['title']}</h3>
          <p><strong>Product line:</strong> {_no_em(r['product_line'])}</p>
          <p><strong>Monitoring link:</strong> {_no_em(r['summary'])}</p>
          <p class="cite"><strong>References:</strong> {_links_html(r['links'])}</p>
        </div>
        """
    tier_img = f'<img src="data:image/png;base64,{images["tier"]}" alt="Tier chart"/>' if "tier" in images else ""
    country_img = (
        f'<img src="data:image/png;base64,{images["country"]}" alt="Country chart"/>' if "country" in images else ""
    )

    kpi = f"""
    <div class="kpi-row">
      <div class="kpi"><span class="kpi-num">{stats['n']:,}</span><span class="kpi-lbl">Scored</span></div>
      <div class="kpi"><span class="kpi-num">{stats['n_high']:,}</span><span class="kpi-lbl">HIGH tier</span></div>
      <div class="kpi"><span class="kpi-num">{stats['capture_pct']:.0f}%</span><span class="kpi-lbl">Fraud in HIGH</span></div>
      <div class="kpi"><span class="kpi-num">{_fmt_money(stats['high_exposure'])}</span><span class="kpi-lbl">Exposure</span></div>
    </div>
    """

    cites = _citation_list()
    refs_html = "".join(
        f'<p class="ref" id="ref-{i}">[{i}] {lbl}. <a href="{url}">{url}</a></p>'
        for i, (lbl, url) in enumerate(cites, 1)
    )
    intro = _no_em(
        "This risk assessment summarizes transaction-monitoring results for a deposit-placement "
        "and sweep-style network using synthetic PaySim-style data. The analysis is illustrative "
        "and supports analyst workflow design, not regulatory filing."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{APP_NAME} — Risk Assessment</title>
<style>
  @page {{ size: letter portrait; margin: 1in; }}
  body {{
    margin: 0 auto;
    max-width: 7.5in;
    padding: 0.75in 0.65in 1.25in;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1a1a1a;
    background: #fff;
  }}
  .title-page {{
    text-align: center;
    padding: 2.5rem 0 3rem;
    border-bottom: 2px solid #00857C;
    margin-bottom: 2rem;
  }}
  .title-page h1 {{ font-size: 22pt; margin: 0.5rem 0; color: #0D2C54; font-weight: 700; }}
  .title-page .subtitle {{ font-size: 13pt; color: #1565C0; margin: 0.25rem 0; }}
  .title-page .meta {{ font-size: 10pt; color: #5C6778; margin-top: 1rem; }}
  h2 {{ font-size: 14pt; color: #0D2C54; margin: 1.75rem 0 0.5rem; border-bottom: 1px solid #E8EEF4; padding-bottom: 0.25rem; }}
  h3 {{ font-size: 12pt; color: #1565C0; margin: 1.25rem 0 0.35rem; }}
  p {{ margin: 0 0 0.85rem; text-align: justify; }}
  .abstract {{ font-style: italic; background: #F4F7FB; padding: 1rem 1.1rem; border-left: 4px solid #00A9CE; margin: 1rem 0 1.5rem; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin: 1rem 0; font-family: Inter, sans-serif; font-size: 9pt; }}
  .kpi {{ border: 1px solid #E8EEF4; padding: 0.5rem; text-align: center; }}
  .kpi-num {{ font-weight: 800; font-size: 12pt; color: #0D2C54; display: block; }}
  figure {{ margin: 1.25rem 0; text-align: center; }}
  figcaption {{ font-size: 9pt; color: #5C6778; margin-top: 0.35rem; font-style: italic; }}
  img {{ max-width: 100%; height: auto; border: 1px solid #E8EEF4; }}
  ul {{ margin: 0 0 1rem; padding-left: 1.25rem; }}
  li {{ margin-bottom: 0.35rem; }}
  .reg-block {{ margin: 1rem 0; padding: 0.75rem 0; border-top: 1px solid #eee; }}
  .cite-inline {{ font-size: 9pt; vertical-align: super; color: #1565C0; }}
  .references {{ font-size: 9pt; margin-top: 2rem; }}
  .ref {{ margin: 0.35rem 0; text-align: left; }}
  a {{ color: #1565C0; }}
  .toc {{ font-family: Inter, sans-serif; font-size: 10pt; margin: 1rem 0 2rem; }}
  .toc a {{ text-decoration: none; }}
  .disclaimer {{ font-size: 9pt; color: #5C6778; margin-top: 2rem; border-top: 1px solid #E8EEF4; padding-top: 0.75rem; }}
</style>
</head>
<body>
  <div class="title-page">
    <p class="subtitle">Risk Assessment</p>
    <h1>{APP_NAME}</h1>
    <p class="subtitle">Deposit placement risk and AML transaction monitoring</p>
    <p class="meta">{stamp}</p>
  </div>

  <p class="toc"><strong>Contents:</strong> {toc_links}</p>

  <section id="summary">
    <h2>Abstract</h2>
    <div class="abstract">{exec_html}</div>
    {kpi}
  </section>

  <section id="context">
    <h2>1. Introduction and industry context</h2>
    <p>{intro}</p>
    {themes_html}
  </section>

  <section id="findings">
    <h2>2. Monitoring findings</h2>
    <p>The scoring model assigns each transaction a risk score from 0 to 100 and a triage tier. Key patterns from this run include the following.</p>
    <ul>{findings_html}</ul>
    <figure>{tier_img}<figcaption>Figure 1. Distribution of scored transactions across risk tiers.</figcaption></figure>
  </section>

  <section id="geography">
    <h2>3. Geographic risk</h2>
    <p>Origin-country concentration informs jurisdictional review priorities and enhanced due diligence triggers.</p>
    <figure>{country_img}<figcaption>Figure 2. HIGH-tier transaction volume by country (top jurisdictions).</figcaption></figure>
  </section>

  <section id="regulatory">
    <h2>4. Regulatory alignment</h2>
    <p>Monitoring themes below are mapped to public AML and deposit-insurance sources. Confirm applicability with compliance and counsel.</p>
    {reg_blocks}
  </section>

  <section id="actions">
    <h2>5. Recommended actions</h2>
    <ul>{actions_html}</ul>
  </section>

  <section class="references">
    <h2>References</h2>
    {refs_html}
    <p class="disclaimer">Demonstration data only. This document is not legal advice or a regulatory filing.</p>
  </section>
</body>
</html>"""


def build_risk_assessment_pdf(
    scored: pd.DataFrame,
    profit_summary: pd.DataFrame | None = None,
) -> bytes:
    stats = compute_brief_stats(scored, profit_summary)
    blocks = build_narrative_blocks(stats)
    images = _chart_images(scored)
    stamp = datetime.now().strftime("%B %d, %Y")
    cites = _citation_list()
    buf = io.BytesIO()
    page_no = 1

    with PdfPages(buf) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0.82), 1, 0.18, color=INTRAFI_NAVY))
        ax.text(0.5, 0.9, APP_NAME, ha="center", fontsize=20, fontweight="bold", color="white")
        ax.text(0.5, 0.84, "Risk Assessment", ha="center", fontsize=13, color=INTRAFI_CYAN)
        ax.text(0.5, 0.76, "Deposit placement risk and AML transaction monitoring", ha="center", fontsize=11, color=INTRAFI_SLATE)
        ax.text(0.5, 0.68, stamp, ha="center", fontsize=10, color=INTRAFI_SLATE)
        ax.text(
            0.5, 0.12,
            "Portrait risk assessment generated from the Risk Analysis Profile pipeline.",
            ha="center", fontsize=9, color=INTRAFI_SLATE, style="italic",
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_no += 1

        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        _pdf_page_header(ax, "Abstract", page_no)
        y = 0.9
        y = _pdf_draw_paragraph(ax, " ".join(blocks["executive"]), 0.08, y, width=92, size=11)
        y -= 0.04
        ax.text(0.08, y, f"Scored transactions: {stats['n']:,}  |  HIGH tier: {stats['n_high']:,}  |  "
                f"Fraud in HIGH: {stats['capture_pct']:.0f}%  |  Exposure: {_fmt_money(stats['high_exposure'])}",
                fontsize=9, color=INTRAFI_SLATE)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_no += 1

        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        _pdf_page_header(ax, "1. Introduction", page_no)
        y = 0.9
        intro = (
            "This report documents monitoring results for a deposit-placement style network. "
            "Data are synthetic and intended to demonstrate analyst workflow, threshold design, "
            "and regulatory mapping rather than to support a filing decision."
        )
        y = _pdf_draw_paragraph(ax, intro, 0.08, y)
        for theme in RISK_AREA_THEMES[:3]:
            y = _pdf_draw_paragraph(ax, f"{theme['title']}. {_no_em(theme['body'])}", 0.08, y, size=10)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_no += 1

        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        _pdf_page_header(ax, "2. Monitoring findings", page_no)
        y = 0.9
        y = _pdf_draw_paragraph(
            ax,
            "The isolation-forest score ranks unusual behavior. Tier cutoffs group cases for triage. "
            "Findings below summarize this run.",
            0.08, y, size=10,
        )
        for b in blocks["findings"]:
            y = _pdf_draw_paragraph(ax, f"• {b}", 0.1, y, width=90, size=10, leading=0.026)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_no += 1

        if "tier" in images and "risk_tier" in scored.columns:
            fig, ax = plt.subplots(figsize=(8.5, 6))
            counts = scored["risk_tier"].value_counts().reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0)
            ax.bar(counts.index, counts.values, color=[TIER_COLORS.get(t, INTRAFI_BLUE) for t in counts.index])
            ax.set_title("Figure 1. Transactions by risk tier", fontsize=12, color=INTRAFI_NAVY)
            ax.set_ylabel("Count")
            fig.text(0.5, 0.02, f"Page {page_no}", ha="center", fontsize=8, color=INTRAFI_SLATE)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            page_no += 1

        if "country" in images:
            fig, ax = plt.subplots(figsize=(8.5, 6))
            cdf = country_aggregate(scored)
            col = "high_risk_volume" if "high_risk_volume" in cdf.columns else "total_volume"
            top = cdf.nlargest(8, col)
            labels = top["country_name"].fillna(top["country"]) if "country_name" in top.columns else top["country"]
            ax.barh(labels.astype(str), top[col].values, color=INTRAFI_CORAL)
            ax.set_title("Figure 2. HIGH-tier volume by country", fontsize=12, color=INTRAFI_NAVY)
            ax.set_xlabel("Amount ($)")
            fig.text(0.5, 0.02, f"Page {page_no}", ha="center", fontsize=8, color=INTRAFI_SLATE)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            page_no += 1

        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        _pdf_page_header(ax, "3. Regulatory alignment", page_no)
        y = 0.9
        for i, r in enumerate(REGULATORY_REFERENCES, 1):
            y = _pdf_draw_paragraph(ax, f"{r['title']}. {_no_em(r['summary'])} [{i}]", 0.08, y, size=10, leading=0.026)
            if y < 0.12:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                page_no += 1
                fig = plt.figure(figsize=(8.5, 11))
                ax = fig.add_axes([0, 0, 1, 1])
                ax.axis("off")
                _pdf_page_header(ax, "3. Regulatory alignment (continued)", page_no)
                y = 0.9
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_no += 1

        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        _pdf_page_header(ax, "4. Recommended actions", page_no)
        y = 0.9
        for b in blocks["actions"]:
            y = _pdf_draw_paragraph(ax, f"• {b}", 0.1, y, width=90, size=10, leading=0.026)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_no += 1

        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        _pdf_page_header(ax, "References", page_no)
        y = 0.9
        for i, (lbl, url) in enumerate(cites, 1):
            y = _pdf_draw_paragraph(ax, f"[{i}] {lbl}. {url}", 0.08, y, width=95, size=8, leading=0.022)
        ax.text(0.08, 0.06, "Demonstration data only. Not legal advice or a regulatory filing.", fontsize=8, color=INTRAFI_SLATE)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    buf.seek(0)
    return buf.read()


def risk_assessment_filenames() -> tuple[str, str]:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return f"risk_assessment_{ts}.html", f"risk_assessment_{ts}.pdf"
