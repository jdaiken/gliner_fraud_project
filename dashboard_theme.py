"""
Dashboard theme — institutional trust palette for deposit-network risk analytics.
"""

# ── Brand palette ─────────────────────────────────────────────────────────────
INTRAFI_NAVY = "#0D2C54"       # primary dark — headers, text emphasis
INTRAFI_BLUE = "#1565C0"       # primary brand blue
INTRAFI_SKY = "#4A9FD4"        # secondary / charts
INTRAFI_CYAN = "#00A9CE"       # accent — network, links
INTRAFI_TEAL = "#00857C"       # positive / low risk
INTRAFI_GOLD = "#F5A623"       # medium risk / attention
INTRAFI_CORAL = "#D64545"      # high risk / fraud
INTRAFI_SLATE = "#5C6778"      # body secondary text
INTRAFI_MIST = "#E8EEF4"       # borders, grid
INTRAFI_CLOUD = "#F4F7FB"    # page background tint
INTRAFI_WHITE = "#FFFFFF"

# Risk tiers
TIER_COLORS = {
    "HIGH": INTRAFI_CORAL,
    "MEDIUM": INTRAFI_GOLD,
    "LOW": INTRAFI_TEAL,
}

TIER_COLORS_LIGHT = {
    "HIGH": "#FCEAEA",
    "MEDIUM": "#FFF4E0",
    "LOW": "#E6F4F1",
}

PLOTLY_SEQUENCE = [
    INTRAFI_NAVY,
    INTRAFI_BLUE,
    INTRAFI_CYAN,
    INTRAFI_SKY,
    INTRAFI_TEAL,
    INTRAFI_GOLD,
]

PLOTLY_LAYOUT = dict(
    font=dict(
        family="Inter,Segoe UI,Helvetica Neue,Arial,sans-serif",
        color=INTRAFI_NAVY,
        size=13,
    ),
    paper_bgcolor=INTRAFI_WHITE,
    plot_bgcolor=INTRAFI_WHITE,
    colorway=PLOTLY_SEQUENCE,
    title=dict(font=dict(size=17, color=INTRAFI_NAVY)),
    margin=dict(l=48, r=24, t=64, b=72),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.18,
        xanchor="center",
        x=0.5,
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=INTRAFI_MIST,
        borderwidth=1,
    ),
)

# Backward compatibility for eda.py imports
CFPB_DARK_NAVY = INTRAFI_NAVY
CFPB_NAVY = INTRAFI_BLUE
CFPB_PACIFIC = INTRAFI_CYAN
CFPB_GREEN = INTRAFI_TEAL
CFPB_RED = INTRAFI_CORAL
CFPB_GOLD = INTRAFI_GOLD
CFPB_GRAY = INTRAFI_SLATE
CFPB_GRAY_LIGHT = INTRAFI_MIST
CFPB_BLACK = INTRAFI_NAVY


def apply_plotly_theme(fig, *, hide_legend: bool = False):
    layout = dict(PLOTLY_LAYOUT)
    if hide_legend:
        layout.pop("legend", None)
        fig.update_layout(**layout, showlegend=False)
    else:
        fig.update_layout(**layout)
        if fig.layout.showlegend is True or (
            fig.data and any(getattr(tr, "showlegend", True) for tr in fig.data)
        ):
            fig.update_layout(
                margin=dict(l=48, r=24, t=64, b=88),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(255,255,255,0.95)",
                    bordercolor=INTRAFI_MIST,
                    borderwidth=1,
                ),
            )
    fig.update_xaxes(gridcolor=INTRAFI_MIST, linecolor=INTRAFI_MIST, zerolinecolor=INTRAFI_MIST)
    fig.update_yaxes(gridcolor=INTRAFI_MIST, linecolor=INTRAFI_MIST, zerolinecolor=INTRAFI_MIST)
    return fig


def tier_color_discrete():
    return dict(TIER_COLORS)


INTRAFI_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', 'Segoe UI', Helvetica, Arial, sans-serif;
    color: {INTRAFI_NAVY};
}}

.block-container {{
    padding-top: 0.5rem;
    padding-bottom: 2.5rem;
    max-width: 1280px;
}}

/* Portfolio site hero (Novo-style report banner) */
.site-hero {{
    position: relative;
    background: linear-gradient(105deg, {INTRAFI_NAVY} 0%, #123a6b 45%, {INTRAFI_BLUE} 100%);
    color: {INTRAFI_WHITE};
    margin: -0.5rem -1rem 1.75rem -1rem;
    padding: 0;
    border-radius: 0 0 10px 10px;
    box-shadow: 0 6px 24px rgba(13, 44, 84, 0.18);
    overflow: hidden;
}}
.site-hero-accent {{
    height: 5px;
    background: linear-gradient(90deg, {INTRAFI_TEAL} 0%, {INTRAFI_CYAN} 50%, {INTRAFI_GOLD} 100%);
}}
.site-hero-inner {{
    padding: 1.65rem 2.25rem 1.85rem 2.25rem;
}}
.site-eyebrow {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.82);
    margin: 0 0 0.45rem 0;
}}
.site-kicker {{
    font-size: 0.95rem;
    font-weight: 500;
    color: {INTRAFI_CYAN};
    margin: 0 0 0.35rem 0;
}}
.site-title {{
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.2;
    color: {INTRAFI_WHITE};
    margin: 0 0 0.4rem 0;
    letter-spacing: -0.02em;
}}
.site-tagline {{
    font-size: 1rem;
    font-weight: 400;
    color: rgba(255,255,255,0.88);
    margin: 0 0 0.5rem 0;
    font-style: italic;
}}
.site-meta {{
    font-size: 0.82rem;
    color: rgba(255,255,255,0.7);
    margin: 0;
    border-top: 1px solid rgba(255,255,255,0.15);
    padding-top: 0.65rem;
}}

/* Sidebar brand + nav */
.sidebar-brand-block {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    padding-bottom: 0.85rem;
    border-bottom: 2px solid {INTRAFI_CYAN};
}}
.sidebar-brand-mark {{
    width: 42px;
    height: 42px;
    border-radius: 8px;
    background: {INTRAFI_NAVY};
    color: {INTRAFI_WHITE};
    font-size: 0.95rem;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    letter-spacing: -0.03em;
    flex-shrink: 0;
}}
.sidebar-brand-text {{
    line-height: 1.25;
}}
.sidebar-brand-text strong {{
    display: block;
    font-size: 0.95rem;
    color: {INTRAFI_NAVY};
}}
.sidebar-brand-text span {{
    font-size: 0.72rem;
    color: {INTRAFI_SLATE};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
.sidebar-nav-heading {{
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {INTRAFI_SLATE};
    margin: 0 0 0.5rem 0;
}}
.sidebar-nav-active {{
    font-size: 0.78rem;
    color: {INTRAFI_SLATE};
    margin: 0.75rem 0 0 0;
    padding-top: 0.65rem;
    border-top: 1px solid {INTRAFI_MIST};
}}
[data-testid="stSidebar"] [data-testid="stButton"] button {{
    justify-content: flex-start;
    font-weight: 600;
    font-size: 0.88rem;
    border-radius: 6px;
    padding: 0.45rem 0.75rem;
    margin-bottom: 0.2rem;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
    background: {INTRAFI_NAVY} !important;
    border-color: {INTRAFI_NAVY} !important;
    color: {INTRAFI_WHITE} !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {{
    background: {INTRAFI_WHITE} !important;
    color: {INTRAFI_NAVY} !important;
    border: 1px solid {INTRAFI_MIST} !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover {{
    border-color: {INTRAFI_CYAN} !important;
    color: {INTRAFI_BLUE} !important;
}}

/* Keep sidebar open — wider min width */
[data-testid="stSidebar"][aria-expanded="true"] {{
    min-width: 18rem;
    max-width: 18rem;
}}

.risk-header, .intrafi-header {{
    background: linear-gradient(120deg, {INTRAFI_NAVY} 0%, {INTRAFI_BLUE} 55%, {INTRAFI_CYAN} 100%);
    color: {INTRAFI_WHITE};
    padding: 1.75rem 2rem;
    border-radius: 8px;
    margin-bottom: 1.25rem;
    box-shadow: 0 4px 14px rgba(13, 44, 84, 0.15);
}}
.risk-header h1, .intrafi-header h1 {{
    color: {INTRAFI_WHITE};
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.25rem 0;
}}
.risk-header .tagline, .intrafi-header .tagline {{
    color: rgba(255,255,255,0.92);
    font-size: 1rem;
    font-weight: 500;
    margin: 0 0 0.5rem 0;
}}
.risk-header .sub, .intrafi-header .sub {{
    color: rgba(255,255,255,0.78);
    font-size: 0.88rem;
    margin: 0;
}}

.risk-metric, .intrafi-metric {{
    background: {INTRAFI_WHITE};
    border: 1px solid {INTRAFI_MIST};
    border-top: 4px solid {INTRAFI_CYAN};
    border-radius: 8px;
    padding: 1rem 1.1rem;
    min-height: 5.75rem;
    box-shadow: 0 1px 3px rgba(13,44,84,0.06);
}}
.risk-metric .label, .intrafi-metric .label {{
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {INTRAFI_SLATE};
}}
.risk-metric .value, .intrafi-metric .value {{
    font-size: 1.5rem;
    font-weight: 700;
    color: {INTRAFI_NAVY};
}}
.risk-metric .value.value-money, .intrafi-metric .value.value-money {{
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}}
.risk-metric.high, .intrafi-metric.high {{ border-top-color: {INTRAFI_CORAL}; }}
.risk-metric.medium, .intrafi-metric.medium {{ border-top-color: {INTRAFI_GOLD}; }}
.risk-metric.low, .intrafi-metric.low {{ border-top-color: {INTRAFI_TEAL}; }}

.risk-callout, .intrafi-callout {{
    background: {INTRAFI_CLOUD};
    border-left: 4px solid {INTRAFI_CYAN};
    padding: 0.85rem 1.1rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.92rem;
    line-height: 1.5;
    margin: 0.75rem 0 1rem 0;
}}

.tab-intro {{
    color: {INTRAFI_SLATE};
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0 0 1.1rem 0;
    padding: 0.65rem 0 0.25rem 0;
    border-bottom: 1px solid {INTRAFI_MIST};
}}

.narrative-preview {{
    font-size: 0.9rem;
    line-height: 1.6;
    color: {INTRAFI_NAVY};
    white-space: pre-wrap;
}}
mark.narrative-kw {{
    background: #FFF4E0;
    color: {INTRAFI_NAVY};
    padding: 0.05rem 0.2rem;
    border-radius: 3px;
    font-weight: 600;
}}

.narrative-card {{
    background: {INTRAFI_WHITE};
    border-radius: 6px;
}}

.risk-glossary, .intrafi-glossary {{
    background: {INTRAFI_WHITE};
    border: 1px solid {INTRAFI_MIST};
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}}
.risk-glossary dt, .intrafi-glossary dt {{
    font-weight: 600;
    color: {INTRAFI_BLUE};
    margin-top: 0.5rem;
}}
.risk-glossary dd, .intrafi-glossary dd {{
    margin-left: 0;
    color: {INTRAFI_SLATE};
    font-size: 0.9rem;
}}

[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {INTRAFI_CLOUD} 0%, {INTRAFI_WHITE} 100%);
    border-right: 1px solid {INTRAFI_MIST};
}}
[data-testid="stSidebar"] .sidebar-refresh button {{
    background: {INTRAFI_TEAL} !important;
    color: {INTRAFI_WHITE} !important;
    border: none !important;
    font-weight: 700 !important;
}}
[data-testid="stSidebar"] .sidebar-refresh button:hover {{
    background: {INTRAFI_NAVY} !important;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    color: {INTRAFI_NAVY};
}}

/* Executive brief (EWS-style document layout) */
.brief-section-label {{
    font-size: 1.35rem;
    font-weight: 700;
    color: {INTRAFI_NAVY};
    margin: 0 0 0.25rem 0;
}}
.brief-doc-title {{
    font-size: 1.85rem;
    font-weight: 800;
    color: {INTRAFI_NAVY};
    margin: 0 0 0.25rem 0;
    line-height: 1.2;
}}
.brief-doc-subtitle {{
    font-size: 1.05rem;
    font-weight: 500;
    color: {INTRAFI_BLUE};
    margin: 0 0 0.35rem 0;
}}
.brief-doc-date {{
    font-size: 0.9rem;
    color: {INTRAFI_SLATE};
    margin: 0 0 0.5rem 0;
}}
.brief-divider {{
    border: none;
    border-top: 3px solid {INTRAFI_TEAL};
    margin: 1rem 0 1.25rem 0;
}}
.brief-stat-card {{
    background: {INTRAFI_WHITE};
    border: 1px solid {INTRAFI_MIST};
    border-radius: 8px;
    padding: 0.85rem 1rem 1rem;
    min-height: 6.5rem;
    box-shadow: 0 1px 3px rgba(13,44,84,0.05);
}}
.brief-stat-accent {{
    height: 4px;
    border-radius: 2px;
    margin: -0.85rem -1rem 0.65rem -1rem;
    width: calc(100% + 2rem);
}}
.brief-stat-number {{
    font-size: 1.65rem;
    font-weight: 700;
    color: {INTRAFI_NAVY};
    line-height: 1.1;
}}
.brief-stat-label {{
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: {INTRAFI_SLATE};
    margin-top: 0.35rem;
}}
.brief-stat-sub {{
    font-size: 0.8rem;
    color: {INTRAFI_SLATE};
    margin-top: 0.2rem;
    line-height: 1.3;
}}
.brief-network-stat {{
    background: {INTRAFI_CLOUD};
    border-left: 4px solid {INTRAFI_CYAN};
    padding: 1rem 1.1rem;
    border-radius: 0 8px 8px 0;
    min-height: 5.5rem;
}}
.brief-network-num {{
    display: block;
    font-size: 1.75rem;
    font-weight: 800;
    color: {INTRAFI_NAVY};
    line-height: 1.1;
}}
.brief-network-desc {{
    display: block;
    font-size: 0.82rem;
    color: {INTRAFI_SLATE};
    line-height: 1.4;
    margin-top: 0.35rem;
}}
div[data-testid="stMarkdownContainer"] h4 {{
    color: {INTRAFI_NAVY};
    font-weight: 700;
    margin-top: 1.25rem;
}}

/* Key findings cards with tinted icons */
.findings-heading {{
    font-size: 1rem;
    font-weight: 700;
    color: {INTRAFI_NAVY};
    margin: 0.5rem 0 0.85rem 0;
}}
.findings-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.85rem;
    margin-bottom: 1.25rem;
    background: {INTRAFI_CLOUD};
    padding: 1rem;
    border-radius: 10px;
}}
.finding-card {{
    background: {INTRAFI_WHITE};
    border: 1px solid {INTRAFI_MIST};
    border-radius: 8px;
    padding: 0.85rem 0.75rem 1rem;
    text-align: center;
    box-shadow: 0 2px 6px rgba(13,44,84,0.06);
    position: relative;
}}
.finding-card-top {{
    height: 4px;
    background: var(--accent);
    border-radius: 8px 8px 0 0;
    margin: -0.85rem -0.75rem 0.65rem -0.75rem;
}}
.finding-icon-wrap {{
    display: flex;
    justify-content: center;
    margin-bottom: 0.35rem;
}}
.finding-icon-svg {{
    display: block;
}}
.finding-stat {{
    font-size: 1.55rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 0.25rem;
}}
.finding-title {{
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: {INTRAFI_NAVY};
    margin-bottom: 0.2rem;
}}
.finding-detail {{
    font-size: 0.76rem;
    color: {INTRAFI_SLATE};
    line-height: 1.3;
}}
@media (max-width: 900px) {{
    .findings-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}

#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
</style>
"""


def inject_brand_css():
    import streamlit as st
    st.markdown(INTRAFI_CSS, unsafe_allow_html=True)


# Legacy alias
inject_cfpb_css = inject_brand_css
