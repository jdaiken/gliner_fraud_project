"""Sidebar navigation."""

from __future__ import annotations

import streamlit as st

from brand import CHART_INSIGHTS_PAGE, RISK_ASSESSMENT_PAGE
from dashboard_branding import render_sidebar_brand

NAV_PAGES: list[str] = [
    "Brief",
    "Overview",
    "Geography",
    "Financial",
    "Transactions",
    "SAR narratives",
    "Risk register",
    RISK_ASSESSMENT_PAGE,
    "Exports",
    "Data guide",
]

SESSION_KEY = "dashboard_page"


def _init_page() -> None:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = NAV_PAGES[0]
    elif st.session_state[SESSION_KEY] not in NAV_PAGES:
        legacy = st.session_state[SESSION_KEY]
        if legacy in ("EDA", CHART_INSIGHTS_PAGE, "Research brief", "Volume monitor"):
            st.session_state[SESSION_KEY] = RISK_ASSESSMENT_PAGE
        else:
            st.session_state[SESSION_KEY] = NAV_PAGES[0]


def render_sidebar_nav() -> str:
    _init_page()
    render_sidebar_brand()
    st.markdown('<p class="sidebar-nav-heading">Sections</p>', unsafe_allow_html=True)

    current = st.session_state[SESSION_KEY]
    for label in NAV_PAGES:
        if st.button(
            label,
            key=f"nav_btn_{label}",
            width="stretch",
            type="primary" if label == current else "secondary",
        ):
            st.session_state[SESSION_KEY] = label
            st.rerun()

    st.markdown(
        f'<p class="sidebar-nav-active">Viewing: <strong>{current}</strong></p>',
        unsafe_allow_html=True,
    )
    return st.session_state[SESSION_KEY]
