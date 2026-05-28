"""Site hero banner."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from brand import APP_NAME, TAGLINE


def render_site_hero(timestamp: str | None = None) -> None:
    ts = timestamp or datetime.now().strftime("%B %d, %Y · %H:%M")
    st.markdown(
        f"""
        <header class="site-hero">
          <div class="site-hero-accent"></div>
          <div class="site-hero-inner">
            <p class="site-eyebrow">AML &amp; Transaction Monitoring · Portfolio Demonstration</p>
            <p class="site-kicker">Research and risk reporting</p>
            <h1 class="site-title">{APP_NAME}</h1>
            <p class="site-tagline">{TAGLINE}</p>
            <p class="site-meta">Run snapshot · {ts}</p>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.markdown(
        f"""
        <div class="sidebar-brand-block">
          <div class="sidebar-brand-mark">RA</div>
          <div class="sidebar-brand-text">
            <strong>{APP_NAME}</strong>
            <span>Sections</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
